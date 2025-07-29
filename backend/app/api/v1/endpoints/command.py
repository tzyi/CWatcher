"""
CWatcher 指令執行 API 端點

提供 SSH 指令執行和系統資訊收集的 RESTful API
"""

import logging
import time
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Path, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_server
from app.models.server import Server
from app.schemas.command import (
    CommandExecuteRequest, CommandExecuteResponse,
    PredefinedCommandRequest, PredefinedCommandsResponse,
    SystemInfoRequest, SystemInfoResponse,
    CommandStatisticsResponse, ErrorResponse,
    CommandResult, CompleteSystemInfo, BasicSystemInfo,
    validate_server_id, validate_timeout
)
from app.services.command_executor import command_executor, execute_system_command, execute_custom_command
from app.services.system_collector import system_collector, collect_server_system_info, collect_server_basic_info
from app.services.ssh_manager import ssh_manager
from app.utils.exceptions import SSHConnectionError, CommandExecutionError, SecurityError


# 設定日誌
logger = logging.getLogger(__name__)

# 建立路由器
router = APIRouter()


@router.post(
    "/servers/{server_id}/execute",
    response_model=CommandExecuteResponse,
    summary="執行自訂指令",
    description="在指定伺服器上執行自訂指令",
    responses={
        400: {"model": ErrorResponse, "description": "請求參數錯誤"},
        404: {"model": ErrorResponse, "description": "伺服器不存在"},
        403: {"model": ErrorResponse, "description": "安全檢查失敗"},
        500: {"model": ErrorResponse, "description": "執行失敗"}
    }
)
async def execute_custom_command_endpoint(
    server_id: int = Path(..., description="伺服器ID", ge=1),
    request: CommandExecuteRequest = ...,
    background_tasks: BackgroundTasks = ...,
    db: Session = Depends(get_db)
):
    """執行自訂指令"""
    try:
        # 驗證參數
        server_id = validate_server_id(server_id)
        if request.timeout:
            request.timeout = validate_timeout(request.timeout)
        
        # 獲取伺服器資訊
        server = get_current_server(db, server_id)
        if not server:
            raise HTTPException(status_code=404, detail="伺服器不存在")
        
        # 檢查伺服器狀態
        if not server.is_active:
            raise HTTPException(status_code=400, detail="伺服器未啟用")
        
        # 準備伺服器資料
        server_data = {
            "ip_address": server.ip_address,
            "ssh_port": server.ssh_port,
            "username": server.username,
            "password_encrypted": server.password_encrypted,
            "private_key_encrypted": server.private_key_encrypted,
            "key_passphrase_encrypted": server.key_passphrase_encrypted,
            "connection_timeout": server.connection_timeout
        }
        
        # 執行指令
        logger.info(f"執行自訂指令: {request.command} on server {server_id}")
        result = await execute_custom_command(
            server_data=server_data,
            command=request.command,
            timeout=request.timeout
        )
        
        # 記錄執行歷史（背景任務）
        background_tasks.add_task(
            log_command_execution,
            server_id=server_id,
            command=request.command,
            result=result
        )
        
        return CommandExecuteResponse(
            success=True,
            message="指令執行完成" if result.status.value == "success" else f"指令執行失敗: {result.error_message}",
            result=result,
            execution_id=f"{server_id}_{int(time.time())}"
        )
        
    except HTTPException:
        raise
    except SecurityError as e:
        logger.warning(f"安全檢查失敗: {e}")
        raise HTTPException(status_code=403, detail=f"安全檢查失敗: {str(e)}")
    except SSHConnectionError as e:
        logger.error(f"SSH 連接失敗: {e}")
        raise HTTPException(status_code=500, detail=f"SSH 連接失敗: {str(e)}")
    except CommandExecutionError as e:
        logger.error(f"指令執行失敗: {e}")
        raise HTTPException(status_code=500, detail=f"指令執行失敗: {str(e)}")
    except ValueError as e:
        logger.warning(f"參數驗證失敗: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"執行自訂指令時發生未預期錯誤: {e}")
        raise HTTPException(status_code=500, detail="內部伺服器錯誤")


@router.post(
    "/servers/{server_id}/execute/predefined",
    response_model=CommandExecuteResponse,
    summary="執行預定義指令",
    description="在指定伺服器上執行預定義的系統指令",
    responses={
        400: {"model": ErrorResponse, "description": "請求參數錯誤"},
        404: {"model": ErrorResponse, "description": "伺服器或指令不存在"},
        500: {"model": ErrorResponse, "description": "執行失敗"}
    }
)
async def execute_predefined_command_endpoint(
    server_id: int = Path(..., description="伺服器ID", ge=1),
    request: PredefinedCommandRequest = ...,
    background_tasks: BackgroundTasks = ...,
    db: Session = Depends(get_db)
):
    """執行預定義指令"""
    try:
        # 驗證參數
        server_id = validate_server_id(server_id)
        
        # 獲取伺服器資訊
        server = get_current_server(db, server_id)
        if not server:
            raise HTTPException(status_code=404, detail="伺服器不存在")
        
        # 檢查指令是否存在
        predefined_commands = command_executor.get_predefined_commands()
        if request.command_name not in predefined_commands:
            raise HTTPException(status_code=404, detail=f"預定義指令不存在: {request.command_name}")
        
        # 準備伺服器資料
        server_data = {
            "ip_address": server.ip_address,
            "ssh_port": server.ssh_port,
            "username": server.username,
            "password_encrypted": server.password_encrypted,
            "private_key_encrypted": server.private_key_encrypted,
            "key_passphrase_encrypted": server.key_passphrase_encrypted,
            "connection_timeout": server.connection_timeout
        }
        
        # 執行預定義指令
        logger.info(f"執行預定義指令: {request.command_name} on server {server_id}")
        result = await execute_system_command(
            server_data=server_data,
            command_name=request.command_name,
            use_cache=request.use_cache
        )
        
        # 記錄執行歷史（背景任務）
        background_tasks.add_task(
            log_command_execution,
            server_id=server_id,
            command=predefined_commands[request.command_name]["command"],
            result=result
        )
        
        return CommandExecuteResponse(
            success=True,
            message="預定義指令執行完成" if result.status.value == "success" else f"預定義指令執行失敗: {result.error_message}",
            result=result,
            execution_id=f"{server_id}_{request.command_name}_{int(time.time())}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"執行預定義指令時發生未預期錯誤: {e}")
        raise HTTPException(status_code=500, detail="內部伺服器錯誤")


@router.get(
    "/commands/predefined",
    response_model=PredefinedCommandsResponse,
    summary="獲取預定義指令列表",
    description="獲取所有可用的預定義系統指令"
)
async def get_predefined_commands():
    """獲取預定義指令列表"""
    try:
        commands = command_executor.get_predefined_commands()
        
        return PredefinedCommandsResponse(
            success=True,
            message="成功獲取預定義指令列表",
            commands=commands,
            total_count=len(commands)
        )
        
    except Exception as e:
        logger.error(f"獲取預定義指令列表時發生錯誤: {e}")
        raise HTTPException(status_code=500, detail="內部伺服器錯誤")


@router.post(
    "/servers/{server_id}/system-info",
    response_model=SystemInfoResponse,
    summary="收集系統資訊",
    description="收集指定伺服器的完整系統資訊",
    responses={
        400: {"model": ErrorResponse, "description": "請求參數錯誤"},
        404: {"model": ErrorResponse, "description": "伺服器不存在"},
        500: {"model": ErrorResponse, "description": "收集失敗"}
    }
)
async def collect_system_info_endpoint(
    server_id: int = Path(..., description="伺服器ID", ge=1),
    request: SystemInfoRequest = ...,
    background_tasks: BackgroundTasks = ...,
    db: Session = Depends(get_db)
):
    """收集系統資訊"""
    try:
        # 驗證參數
        server_id = validate_server_id(server_id)
        
        # 獲取伺服器資訊
        server = get_current_server(db, server_id)
        if not server:
            raise HTTPException(status_code=404, detail="伺服器不存在")
        
        # 準備伺服器資料
        server_data = {
            "ip_address": server.ip_address,
            "ssh_port": server.ssh_port,
            "username": server.username,
            "password_encrypted": server.password_encrypted,
            "private_key_encrypted": server.private_key_encrypted,
            "key_passphrase_encrypted": server.key_passphrase_encrypted,
            "connection_timeout": server.connection_timeout
        }
        
        start_time = time.time()
        
        # 收集系統資訊
        logger.info(f"開始收集伺服器 {server_id} 的系統資訊")
        
        if request.include_details:
            # 收集完整資訊
            system_info = await collect_server_system_info(server_data)
            
            # 轉換為回應格式
            response_data = CompleteSystemInfo()
            collection_summary = {
                "total_categories": len(system_info),
                "successful_categories": 0,
                "failed_categories": 0,
                "collection_times": {}
            }
            
            for info_type, info in system_info.items():
                # 轉換為 Pydantic 模型
                system_info_data = {
                    "info_type": info_type.value,
                    "data": info.data,
                    "timestamp": info.timestamp,
                    "collection_time": info.collection_time,
                    "server_info": info.server_info
                }
                
                # 設定對應的屬性
                setattr(response_data, info_type.value, system_info_data)
                
                # 更新摘要
                if info.data.get("collection_status") == "success":
                    collection_summary["successful_categories"] += 1
                else:
                    collection_summary["failed_categories"] += 1
                
                collection_summary["collection_times"][info_type.value] = info.collection_time
            
            response_data.collection_summary = collection_summary
        else:
            # 收集基本資訊
            basic_info = await collect_server_basic_info(server_data)
            response_data = BasicSystemInfo(**basic_info)
        
        total_time = time.time() - start_time
        
        # 更新伺服器最後檢查時間（背景任務）
        background_tasks.add_task(
            update_server_last_check,
            server_id=server_id,
            db=db
        )
        
        return SystemInfoResponse(
            success=True,
            message="系統資訊收集完成",
            data=response_data,
            collection_time=total_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"收集系統資訊時發生未預期錯誤: {e}")
        raise HTTPException(status_code=500, detail="內部伺服器錯誤")


@router.get(
    "/servers/{server_id}/system-info/basic",
    response_model=SystemInfoResponse,
    summary="獲取基本系統資訊",
    description="快速獲取指定伺服器的基本系統資訊",
    responses={
        400: {"model": ErrorResponse, "description": "請求參數錯誤"},
        404: {"model": ErrorResponse, "description": "伺服器不存在"},
        500: {"model": ErrorResponse, "description": "收集失敗"}
    }
)
async def get_basic_system_info_endpoint(
    server_id: int = Path(..., description="伺服器ID", ge=1),
    use_cache: bool = Query(default=True, description="是否使用快取"),
    db: Session = Depends(get_db)
):
    """獲取基本系統資訊"""
    try:
        # 驗證參數
        server_id = validate_server_id(server_id)
        
        # 獲取伺服器資訊
        server = get_current_server(db, server_id)
        if not server:
            raise HTTPException(status_code=404, detail="伺服器不存在")
        
        # 準備伺服器資料
        server_data = {
            "ip_address": server.ip_address,
            "ssh_port": server.ssh_port,
            "username": server.username,
            "password_encrypted": server.password_encrypted,
            "private_key_encrypted": server.private_key_encrypted,
            "key_passphrase_encrypted": server.key_passphrase_encrypted,
            "connection_timeout": server.connection_timeout
        }
        
        start_time = time.time()
        
        # 收集基本資訊
        logger.info(f"收集伺服器 {server_id} 的基本系統資訊")
        basic_info = await collect_server_basic_info(server_data)
        
        total_time = time.time() - start_time
        
        return SystemInfoResponse(
            success=True,
            message="基本系統資訊收集完成",
            data=BasicSystemInfo(**basic_info),
            collection_time=total_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取基本系統資訊時發生未預期錯誤: {e}")
        raise HTTPException(status_code=500, detail="內部伺服器錯誤")


@router.get(
    "/statistics",
    response_model=CommandStatisticsResponse,
    summary="獲取指令執行統計",
    description="獲取指令執行引擎的統計資訊"
)
async def get_command_statistics():
    """獲取指令執行統計"""
    try:
        stats = command_executor.get_statistics()
        
        return CommandStatisticsResponse(
            success=True,
            message="成功獲取指令執行統計",
            statistics=stats
        )
        
    except Exception as e:
        logger.error(f"獲取指令統計時發生錯誤: {e}")
        raise HTTPException(status_code=500, detail="內部伺服器錯誤")


@router.delete(
    "/cache",
    summary="清理指令快取",
    description="清理指令執行結果的快取"
)
async def clear_command_cache():
    """清理指令快取"""
    try:
        command_executor.clear_cache()
        
        return {
            "success": True,
            "message": "指令快取已清理"
        }
        
    except Exception as e:
        logger.error(f"清理指令快取時發生錯誤: {e}")
        raise HTTPException(status_code=500, detail="內部伺服器錯誤")


@router.get(
    "/servers/{server_id}/connection/test",
    summary="測試伺服器連接",
    description="測試指定伺服器的 SSH 連接狀態",
    responses={
        400: {"model": ErrorResponse, "description": "請求參數錯誤"},
        404: {"model": ErrorResponse, "description": "伺服器不存在"},
        500: {"model": ErrorResponse, "description": "測試失敗"}
    }
)
async def test_server_connection_endpoint(
    server_id: int = Path(..., description="伺服器ID", ge=1),
    db: Session = Depends(get_db)
):
    """測試伺服器連接"""
    try:
        # 驗證參數
        server_id = validate_server_id(server_id)
        
        # 獲取伺服器資訊
        server = get_current_server(db, server_id)
        if not server:
            raise HTTPException(status_code=404, detail="伺服器不存在")
        
        # 準備伺服器資料
        server_data = {
            "ip_address": server.ip_address,
            "ssh_port": server.ssh_port,
            "username": server.username,
            "password_encrypted": server.password_encrypted,
            "private_key_encrypted": server.private_key_encrypted,
            "key_passphrase_encrypted": server.key_passphrase_encrypted,
            "connection_timeout": server.connection_timeout
        }
        
        # 測試連接
        logger.info(f"測試伺服器 {server_id} 的連接")
        config = ssh_manager.decrypt_server_credentials(server_data)
        test_result = ssh_manager.test_connection(config)
        
        return {
            "success": test_result["success"],
            "message": test_result["message"],
            "connection_info": {
                "host": test_result["host"],
                "port": test_result["port"],
                "username": test_result["username"],
                "duration": test_result["duration"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"測試伺服器連接時發生未預期錯誤: {e}")
        raise HTTPException(status_code=500, detail="內部伺服器錯誤")


# 背景任務函數
async def log_command_execution(server_id: int, command: str, result: Any):
    """記錄指令執行歷史"""
    try:
        # 這裡可以將執行歷史記錄到資料庫
        logger.info(f"記錄指令執行: server={server_id}, command={command}, status={result.status.value}")
    except Exception as e:
        logger.error(f"記錄指令執行歷史失敗: {e}")


async def update_server_last_check(server_id: int, db: Session):
    """更新伺服器最後檢查時間"""
    try:
        server = db.query(Server).filter(Server.id == server_id).first()
        if server:
            from datetime import datetime
            server.last_check_time = datetime.now()
            db.commit()
    except Exception as e:
        logger.error(f"更新伺服器最後檢查時間失敗: {e}")
        db.rollback()


# 異常處理器
@router.exception_handler(SecurityError)
async def security_error_handler(request, exc):
    """安全錯誤處理器"""
    return ErrorResponse(
        success=False,
        message=f"安全檢查失敗: {str(exc)}",
        error_code="SECURITY_ERROR",
        timestamp=datetime.now()
    )


@router.exception_handler(SSHConnectionError)
async def ssh_connection_error_handler(request, exc):
    """SSH 連接錯誤處理器"""
    return ErrorResponse(
        success=False,
        message=f"SSH 連接失敗: {str(exc)}",
        error_code="SSH_CONNECTION_ERROR",
        timestamp=datetime.now()
    )


@router.exception_handler(CommandExecutionError)
async def command_execution_error_handler(request, exc):
    """指令執行錯誤處理器"""
    return ErrorResponse(
        success=False,
        message=f"指令執行失敗: {str(exc)}",
        error_code="COMMAND_EXECUTION_ERROR",
        timestamp=datetime.now()
    )