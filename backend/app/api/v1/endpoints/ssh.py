"""
CWatcher SSH 管理 API 端點

提供 SSH 連接測試、管理和監控的 RESTful API
支援伺服器連接驗證、憑證管理和連接狀態查詢
"""

from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from pydantic import BaseModel, Field, validator
import asyncio
import logging

from core.deps import get_db
from models.server import Server
from services.ssh_manager import ssh_manager, SSHConnectionConfig
from services.auth_service import auth_service, AuthenticationError
from services.security_service import security_service, check_connection_security
from schemas.server import ServerCreate, ServerUpdate, ServerResponse
from utils.encryption import EncryptionError


logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic 模型
class ConnectionTestRequest(BaseModel):
    """連接測試請求"""
    host: str = Field(..., description="伺服器 IP 位址或主機名")
    port: int = Field(22, ge=1, le=65535, description="SSH 端口")
    username: str = Field(..., min_length=1, max_length=32, description="使用者名稱")
    password: Optional[str] = Field(None, min_length=1, description="密碼")
    private_key: Optional[str] = Field(None, min_length=1, description="私鑰內容")
    key_passphrase: Optional[str] = Field(None, description="私鑰密碼")
    timeout: int = Field(10, ge=5, le=60, description="連接超時時間")
    
    @validator('host')
    def validate_host(cls, v):
        if not v or not v.strip():
            raise ValueError('主機地址不能為空')
        return v.strip()
    
    @validator('username')
    def validate_username(cls, v):
        if not auth_service.validate_username(v):
            raise ValueError('使用者名稱格式無效')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "host": "192.168.1.100",
                "port": 22,
                "username": "admin",
                "password": "SecurePassword123",
                "timeout": 10
            }
        }


class ConnectionTestResponse(BaseModel):
    """連接測試回應"""
    success: bool = Field(..., description="連接是否成功")
    message: str = Field(..., description="連接結果訊息")
    duration: float = Field(..., description="連接耗時（秒）")
    host: str = Field(..., description="目標主機")
    port: int = Field(..., description="目標端口")
    username: str = Field(..., description="使用者名稱")
    details: Optional[Dict[str, Any]] = Field(None, description="詳細資訊")


class SSHCommandRequest(BaseModel):
    """SSH 指令執行請求"""
    server_id: int = Field(..., description="伺服器 ID")
    command: str = Field(..., min_length=1, max_length=1000, description="要執行的指令")
    timeout: Optional[int] = Field(30, ge=5, le=300, description="指令超時時間")
    
    @validator('command')
    def validate_command(cls, v):
        if not v or not v.strip():
            raise ValueError('指令不能為空')
        return v.strip()


class SSHCommandResponse(BaseModel):
    """SSH 指令執行回應"""
    success: bool = Field(..., description="執行是否成功")
    stdout: str = Field(..., description="標準輸出")
    stderr: str = Field(..., description="錯誤輸出")
    exit_code: int = Field(..., description="退出碼")
    duration: float = Field(..., description="執行時間（秒）")
    command: str = Field(..., description="執行的指令")


class ConnectionStatusResponse(BaseModel):
    """連接狀態回應"""
    server_id: int = Field(..., description="伺服器 ID")
    status: str = Field(..., description="連接狀態")
    last_connected: Optional[str] = Field(None, description="最後連接時間")
    connection_pool: Dict[str, Any] = Field(..., description="連接池狀態")


@router.post("/test-connection", response_model=ConnectionTestResponse)
async def test_ssh_connection(
    request: ConnectionTestRequest,
    background_tasks: BackgroundTasks
) -> ConnectionTestResponse:
    """
    測試 SSH 連接
    
    驗證伺服器的 SSH 連接可用性和認證資訊正確性
    """
    try:
        # 安全性檢查
        allowed, reason = check_connection_security("127.0.0.1", request.host, request.username)
        if not allowed:
            raise HTTPException(
                status_code=403,
                detail=f"連接被安全策略拒絕: {reason}"
            )
        
        # 建立連接配置
        config = SSHConnectionConfig(
            host=request.host,
            port=request.port,
            username=request.username,
            password=request.password,
            private_key=request.private_key,
            key_passphrase=request.key_passphrase,
            timeout=request.timeout
        )
        
        # 執行連接測試
        logger.info(f"測試 SSH 連接: {request.username}@{request.host}:{request.port}")
        result = ssh_manager.test_connection(config)
        
        # 背景記錄安全事件
        background_tasks.add_task(
            security_service.record_connection_attempt,
            "127.0.0.1",
            request.host,
            request.username,
            result["success"],
            result.get("message") if not result["success"] else None
        )
        
        return ConnectionTestResponse(
            success=result["success"],
            message=result["message"],
            duration=result["duration"],
            host=result["host"],
            port=result["port"],
            username=result["username"],
            details=result if result["success"] else None
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"SSH 連接測試失敗: {e}")
        raise HTTPException(status_code=500, detail=f"連接測試失敗: {str(e)}")


@router.post("/servers/{server_id}/execute", response_model=SSHCommandResponse)
async def execute_ssh_command(
    server_id: int,
    request: SSHCommandRequest,
    db: AsyncSession = Depends(get_db)
) -> SSHCommandResponse:
    """
    在指定伺服器上執行 SSH 指令
    
    支援安全的遠程指令執行和結果回傳
    """
    try:
        # 查詢伺服器資訊
        result = await db.execute(select(Server).where(Server.id == server_id))
        server = result.scalar_one_or_none()
        
        if not server:
            raise HTTPException(status_code=404, detail="伺服器不存在")
        
        if not server.monitoring_enabled:
            raise HTTPException(status_code=403, detail="伺服器監控已停用")
        
        # 指令安全檢查
        safe, reason = security_service.validate_command(
            request.command, 
            server.username, 
            server.ip_address
        )
        
        if not safe:
            raise HTTPException(
                status_code=403,
                detail=f"指令被安全策略拒絕: {reason}"
            )
        
        # 解密伺服器憑證
        server_data = {
            "ip_address": server.ip_address,
            "ssh_port": server.ssh_port,
            "username": server.username,
            "password_encrypted": server.password_encrypted,
            "private_key_encrypted": server.private_key_encrypted,
            "connection_timeout": server.connection_timeout,
            "max_connections": server.max_connections
        }
        
        config = ssh_manager.decrypt_server_credentials(server_data)
        
        # 執行指令
        import time
        start_time = time.time()
        
        logger.info(f"執行 SSH 指令: {request.command} on {server.name}")
        stdout, stderr, exit_code = await ssh_manager.execute_command(
            config, 
            request.command, 
            request.timeout
        )
        
        duration = time.time() - start_time
        
        # 更新伺服器最後連接時間
        await db.execute(
            update(Server)
            .where(Server.id == server_id)
            .values(
                last_connected_at=asyncio.get_event_loop().time(),
                status='online',
                connection_attempts=0,
                last_error=None
            )
        )
        await db.commit()
        
        return SSHCommandResponse(
            success=exit_code == 0,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            duration=round(duration, 3),
            command=request.command
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SSH 指令執行失敗: {e}")
        
        # 更新伺服器錯誤狀態
        try:
            await db.execute(
                update(Server)
                .where(Server.id == server_id)
                .values(
                    status='error',
                    last_error=str(e),
                    connection_attempts=Server.connection_attempts + 1
                )
            )
            await db.commit()
        except Exception as db_error:
            logger.error(f"更新伺服器狀態失敗: {db_error}")
        
        raise HTTPException(status_code=500, detail=f"指令執行失敗: {str(e)}")


@router.get("/servers/{server_id}/status", response_model=ConnectionStatusResponse)
async def get_server_connection_status(
    server_id: int,
    db: AsyncSession = Depends(get_db)
) -> ConnectionStatusResponse:
    """
    獲取伺服器連接狀態
    
    返回伺服器的當前連接狀態和連接池資訊
    """
    try:
        # 查詢伺服器資訊
        result = await db.execute(select(Server).where(Server.id == server_id))
        server = result.scalar_one_or_none()
        
        if not server:
            raise HTTPException(status_code=404, detail="伺服器不存在")
        
        # 獲取連接池狀態
        pool_status = ssh_manager.get_server_status(
            server.ip_address,
            server.ssh_port,
            server.username
        )
        
        return ConnectionStatusResponse(
            server_id=server_id,
            status=server.status,
            last_connected=server.last_connected_at.isoformat() if server.last_connected_at else None,
            connection_pool=pool_status
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取伺服器連接狀態失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取狀態失敗: {str(e)}")


@router.get("/manager/statistics")
async def get_ssh_manager_statistics() -> Dict[str, Any]:
    """
    獲取 SSH 管理器統計資訊
    
    返回連接池、指令執行等統計數據
    """
    try:
        stats = ssh_manager.get_statistics()
        return {
            "success": True,
            "data": stats,
            "timestamp": asyncio.get_event_loop().time()
        }
        
    except Exception as e:
        logger.error(f"獲取 SSH 管理器統計失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取統計失敗: {str(e)}")


@router.post("/manager/cleanup")
async def cleanup_ssh_connections() -> Dict[str, Any]:
    """
    清理 SSH 連接
    
    關閉所有空閒的 SSH 連接，釋放資源
    """
    try:
        ssh_manager.close_all_connections()
        
        return {
            "success": True,
            "message": "所有 SSH 連接已清理",
            "timestamp": asyncio.get_event_loop().time()
        }
        
    except Exception as e:
        logger.error(f"清理 SSH 連接失敗: {e}")
        raise HTTPException(status_code=500, detail=f"清理失敗: {str(e)}")


@router.get("/security/summary")
async def get_security_summary() -> Dict[str, Any]:
    """
    獲取安全摘要
    
    返回安全事件統計和威脅情報
    """
    try:
        summary = security_service.get_security_summary()
        return {
            "success": True,
            "data": summary,
            "timestamp": asyncio.get_event_loop().time()
        }
        
    except Exception as e:
        logger.error(f"獲取安全摘要失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取摘要失敗: {str(e)}")


@router.get("/security/events")
async def get_security_events(
    limit: int = 50,
    severity: Optional[str] = None
) -> Dict[str, Any]:
    """
    獲取安全事件列表
    
    返回最近的安全事件和威脅檢測記錄
    """
    try:
        from app.services.security_service import SecurityLevel
        
        severity_filter = None
        if severity:
            try:
                severity_filter = SecurityLevel(severity.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail="無效的嚴重程度")
        
        events = security_service.get_recent_events(
            limit=min(limit, 100),  # 限制最大數量
            severity_filter=severity_filter
        )
        
        return {
            "success": True,
            "data": events,
            "count": len(events),
            "timestamp": asyncio.get_event_loop().time()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取安全事件失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取事件失敗: {str(e)}")


@router.post("/security/whitelist")
async def add_to_security_whitelist(
    item_type: str,
    item: str
) -> Dict[str, Any]:
    """
    添加項目到安全白名單
    
    支援 IP、主機、使用者白名單管理
    """
    try:
        if item_type not in ["ip", "host", "user"]:
            raise HTTPException(
                status_code=400, 
                detail="無效的項目類型，支援: ip, host, user"
            )
        
        success = security_service.add_to_whitelist(item_type, item)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"添加白名單項目失敗: {item_type}={item}"
            )
        
        return {
            "success": True,
            "message": f"成功添加到白名單: {item_type}={item}",
            "timestamp": asyncio.get_event_loop().time()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加白名單項目失敗: {e}")
        raise HTTPException(status_code=500, detail=f"操作失敗: {str(e)}")


@router.delete("/security/whitelist")
async def remove_from_security_whitelist(
    item_type: str,
    item: str
) -> Dict[str, Any]:
    """
    從安全白名單移除項目
    """
    try:
        if item_type not in ["ip", "host", "user"]:
            raise HTTPException(
                status_code=400,
                detail="無效的項目類型，支援: ip, host, user"
            )
        
        success = security_service.remove_from_whitelist(item_type, item)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"移除白名單項目失敗: {item_type}={item}"
            )
        
        return {
            "success": True,
            "message": f"成功從白名單移除: {item_type}={item}",
            "timestamp": asyncio.get_event_loop().time()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"移除白名單項目失敗: {e}")
        raise HTTPException(status_code=500, detail=f"操作失敗: {str(e)}")


# 錯誤處理
@router.exception_handler(AuthenticationError)
async def auth_error_handler(request, exc):
    return JSONResponse(
        status_code=401,
        content={"detail": f"認證錯誤: {str(exc)}"}
    )


@router.exception_handler(EncryptionError)
async def encryption_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": f"加密錯誤: {str(exc)}"}
    )