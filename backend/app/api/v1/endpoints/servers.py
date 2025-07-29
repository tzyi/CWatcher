"""
CWatcher 伺服器管理 API 端點

提供伺服器的增加、刪除、查詢和狀態管理功能
整合 WebSocket 推送服務管理
"""

import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends, Query, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.services.websocket_push_service import (
    push_service, add_server_to_push_list, remove_server_from_push_list,
    push_server_monitoring_data, get_push_service_stats
)
from app.services.monitoring_collector import monitoring_service
from app.services.ssh_manager import ssh_manager, SSHConnectionConfig
from app.core.config import settings

# 設定日誌
logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== Pydantic 模型 ====================

class ServerCreate(BaseModel):
    """建立伺服器請求"""
    name: str = Field(..., min_length=1, max_length=100, description="伺服器名稱")
    description: Optional[str] = Field(None, max_length=500, description="伺服器描述")
    host: str = Field(..., description="伺服器 IP 或主機名")
    port: int = Field(default=22, ge=1, le=65535, description="SSH 連接埠")
    username: str = Field(..., min_length=1, description="SSH 使用者名稱")
    password: Optional[str] = Field(None, description="SSH 密碼")
    ssh_key: Optional[str] = Field(None, description="SSH 私鑰")
    push_interval: int = Field(default=30, ge=10, le=300, description="推送間隔（秒）")
    auto_start_monitoring: bool = Field(default=True, description="自動開始監控")


class ServerUpdate(BaseModel):
    """更新伺服器請求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="伺服器名稱")
    description: Optional[str] = Field(None, max_length=500, description="伺服器描述")
    host: Optional[str] = Field(None, description="伺服器 IP 或主機名")
    port: Optional[int] = Field(None, ge=1, le=65535, description="SSH 連接埠")
    username: Optional[str] = Field(None, min_length=1, description="SSH 使用者名稱")
    password: Optional[str] = Field(None, description="SSH 密碼")
    ssh_key: Optional[str] = Field(None, description="SSH 私鑰")
    push_interval: Optional[int] = Field(None, ge=10, le=300, description="推送間隔（秒）")


class ServerInfo(BaseModel):
    """伺服器資訊回應"""
    id: int
    name: str
    description: Optional[str]
    host: str
    port: int
    username: str
    status: str
    push_interval: int
    is_monitoring: bool
    last_seen: Optional[str]
    created_at: str
    updated_at: str


class MonitoringControl(BaseModel):
    """監控控制請求"""
    action: str = Field(..., regex="^(start|stop|restart)$", description="控制動作")
    push_interval: Optional[int] = Field(None, ge=10, le=300, description="推送間隔（秒）")


# ==================== 伺服器 CRUD 操作 ====================

@router.post("/", response_model=Dict[str, Any])
async def create_server(server_data: ServerCreate):
    """
    建立新伺服器
    
    添加新的監控伺服器到系統中
    自動加入 WebSocket 推送列表
    """
    try:
        # 驗證 SSH 連接
        config = SSHConnectionConfig(
            host=server_data.host,
            port=server_data.port,
            username=server_data.username,
            password=server_data.password,
            ssh_key=server_data.ssh_key
        )
        
        # 測試連接
        connection_test = await monitoring_service.test_connection_and_collect(config, None)
        
        if connection_test.get("connection_status") != "success":
            raise HTTPException(
                status_code=400, 
                detail=f"SSH 連接測試失敗: {connection_test.get('error', '未知錯誤')}"
            )
        
        # 這裡應該將伺服器資訊存儲到數據庫
        # 暫時使用模擬 ID
        server_id = hash(f"{server_data.host}:{server_data.port}:{server_data.username}") % 10000
        
        # 加入推送列表
        if server_data.auto_start_monitoring:
            await add_server_to_push_list(server_id, server_data.push_interval)
            logger.info(f"伺服器 {server_id} 已加入監控推送列表")
        
        return JSONResponse(content={
            "success": True,
            "data": {
                "server_id": server_id,
                "name": server_data.name,
                "host": server_data.host,
                "port": server_data.port,
                "status": "online",
                "monitoring_started": server_data.auto_start_monitoring,
                "connection_test": connection_test
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"建立伺服器失敗: {e}")
        raise HTTPException(status_code=500, detail=f"建立伺服器失敗: {str(e)}")


@router.get("/", response_model=Dict[str, Any])
async def list_servers(
    limit: int = Query(default=50, ge=1, le=100, description="返回數量限制"),
    offset: int = Query(default=0, ge=0, description="分頁偏移"),
    status_filter: Optional[str] = Query(None, description="狀態過濾")
):
    """
    取得伺服器列表
    
    支援分頁和狀態過濾
    """
    try:
        # 取得推送服務狀態
        server_states = push_service.get_server_states()
        
        # 構建伺服器列表（這裡應該從數據庫查詢）
        servers = []
        for server_id, state in server_states.items():
            server_info = {
                "id": server_id,
                "name": f"Server {server_id}",
                "description": f"監控伺服器 {server_id}",
                "host": "localhost",  # 這裡應該從數據庫取得
                "port": 22,
                "username": "test",
                "status": state["last_status"],
                "push_interval": state["push_interval"],
                "is_monitoring": state["is_active"],
                "last_seen": state["last_push_time"],
                "total_pushes": state["total_pushes"],
                "consecutive_failures": state["consecutive_failures"]
            }
            
            # 狀態過濾
            if status_filter and server_info["status"] != status_filter:
                continue
                
            servers.append(server_info)
        
        # 分頁
        total_count = len(servers)
        servers = servers[offset:offset + limit]
        
        return JSONResponse(content={
            "success": True,
            "data": {
                "servers": servers,
                "total_count": total_count,
                "limit": limit,
                "offset": offset
            }
        })
        
    except Exception as e:
        logger.error(f"取得伺服器列表失敗: {e}")
        raise HTTPException(status_code=500, detail=f"取得伺服器列表失敗: {str(e)}")


@router.get("/{server_id}", response_model=Dict[str, Any])
async def get_server(server_id: int = Path(..., description="伺服器 ID")):
    """
    取得特定伺服器詳細資訊
    
    包括當前狀態、監控統計和最新數據
    """
    try:
        # 取得伺服器狀態
        server_states = push_service.get_server_states()
        
        if server_id not in server_states:
            raise HTTPException(status_code=404, detail="伺服器不存在")
        
        state = server_states[server_id]
        
        # 構建詳細資訊
        server_detail = {
            "id": server_id,
            "name": f"Server {server_id}",
            "description": f"監控伺服器 {server_id}",
            "host": "localhost",  # 這裡應該從數據庫取得
            "port": 22,
            "username": "test",
            "status": state["last_status"],
            "push_interval": state["push_interval"],
            "is_monitoring": state["is_active"],
            "last_push_time": state["last_push_time"],
            "total_pushes": state["total_pushes"],
            "consecutive_failures": state["consecutive_failures"],
            "should_push": state["should_push"]
        }
        
        return JSONResponse(content={
            "success": True,
            "data": server_detail
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得伺服器詳細資訊失敗: {e}")
        raise HTTPException(status_code=500, detail=f"取得伺服器資訊失敗: {str(e)}")


@router.put("/{server_id}", response_model=Dict[str, Any])
async def update_server(
    server_id: int = Path(..., description="伺服器 ID"),
    update_data: ServerUpdate = None
):
    """
    更新伺服器設定
    
    可更新基本資訊和監控設定
    """
    try:
        # 檢查伺服器是否存在
        server_states = push_service.get_server_states()
        
        if server_id not in server_states:
            raise HTTPException(status_code=404, detail="伺服器不存在")
        
        # 更新推送間隔
        if update_data and update_data.push_interval:
            push_service.update_server_interval(server_id, update_data.push_interval)
        
        # 這裡應該更新數據庫中的伺服器資訊
        
        return JSONResponse(content={
            "success": True,
            "data": {
                "server_id": server_id,
                "updated": True,
                "message": "伺服器設定已更新"
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新伺服器設定失敗: {e}")
        raise HTTPException(status_code=500, detail=f"更新伺服器失敗: {str(e)}")


@router.delete("/{server_id}", response_model=Dict[str, Any])
async def delete_server(server_id: int = Path(..., description="伺服器 ID")):
    """
    刪除伺服器
    
    從監控列表和推送服務中移除伺服器
    """
    try:
        # 檢查伺服器是否存在
        server_states = push_service.get_server_states()
        
        if server_id not in server_states:
            raise HTTPException(status_code=404, detail="伺服器不存在")
        
        # 從推送列表移除
        await remove_server_from_push_list(server_id)
        
        # 這裡應該從數據庫刪除伺服器記錄
        
        return JSONResponse(content={
            "success": True,
            "data": {
                "server_id": server_id,
                "deleted": True,
                "message": "伺服器已刪除"
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"刪除伺服器失敗: {e}")
        raise HTTPException(status_code=500, detail=f"刪除伺服器失敗: {str(e)}")


# ==================== 監控控制 ====================

@router.post("/{server_id}/monitoring", response_model=Dict[str, Any])
async def control_monitoring(
    server_id: int = Path(..., description="伺服器 ID"),
    control: MonitoringControl = None
):
    """
    控制伺服器監控
    
    支援啟動、停止、重啟監控
    """
    try:
        # 檢查伺服器是否存在
        server_states = push_service.get_server_states()
        
        if server_id not in server_states:
            raise HTTPException(status_code=404, detail="伺服器不存在")
        
        action = control.action if control else "start"
        
        if action == "start":
            push_service.activate_server(server_id)
            if control and control.push_interval:
                push_service.update_server_interval(server_id, control.push_interval)
            message = "監控已啟動"
            
        elif action == "stop":
            push_service.deactivate_server(server_id)
            message = "監控已停止"
            
        elif action == "restart":
            push_service.deactivate_server(server_id)
            await asyncio.sleep(1)  # 短暫停頓
            push_service.activate_server(server_id)
            if control and control.push_interval:
                push_service.update_server_interval(server_id, control.push_interval)
            message = "監控已重啟"
        
        else:
            raise HTTPException(status_code=400, detail="不支援的控制動作")
        
        return JSONResponse(content={
            "success": True,
            "data": {
                "server_id": server_id,
                "action": action,
                "message": message
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"控制監控失敗: {e}")
        raise HTTPException(status_code=500, detail=f"控制監控失敗: {str(e)}")


@router.post("/{server_id}/push-now", response_model=Dict[str, Any])
async def push_server_data_now(server_id: int = Path(..., description="伺服器 ID")):
    """
    立即推送伺服器監控數據
    
    手動觸發數據收集和推送
    """
    try:
        # 檢查伺服器是否存在
        server_states = push_service.get_server_states()
        
        if server_id not in server_states:
            raise HTTPException(status_code=404, detail="伺服器不存在")
        
        # 立即推送數據
        success = await push_server_monitoring_data(server_id)
        
        return JSONResponse(content={
            "success": True,
            "data": {
                "server_id": server_id,
                "push_successful": success,
                "message": "數據推送完成" if success else "數據推送失敗"
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"立即推送數據失敗: {e}")
        raise HTTPException(status_code=500, detail=f"推送數據失敗: {str(e)}")


@router.get("/{server_id}/status", response_model=Dict[str, Any])
async def get_server_status(server_id: int = Path(..., description="伺服器 ID")):
    """
    取得伺服器即時狀態
    
    包括連接狀態、監控數據和統計資訊
    """
    try:
        # 檢查伺服器是否存在
        server_states = push_service.get_server_states()
        
        if server_id not in server_states:
            raise HTTPException(status_code=404, detail="伺服器不存在")
        
        state = server_states[server_id]
        
        # 嘗試收集最新數據
        try:
            # 這裡應該從實際的伺服器數據取得配置
            config = SSHConnectionConfig(
                host="localhost",
                port=22,
                username="test",
                password="test123"
            )
            
            latest_data = await monitoring_service.test_connection_and_collect(config, server_id)
        except Exception as e:
            latest_data = {"connection_status": "failed", "error": str(e)}
        
        status_info = {
            "server_id": server_id,
            "push_state": state,
            "latest_data": latest_data,
            "timestamp": datetime.now().isoformat()
        }
        
        return JSONResponse(content={
            "success": True,
            "data": status_info
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得伺服器狀態失敗: {e}")
        raise HTTPException(status_code=500, detail=f"取得狀態失敗: {str(e)}")


# ==================== 批量操作 ====================

@router.post("/batch/monitoring", response_model=Dict[str, Any])
async def batch_control_monitoring(
    action: str = Query(..., regex="^(start|stop|restart)$", description="批量操作"),
    server_ids: Optional[List[int]] = Query(None, description="伺服器 ID 列表，為空則操作全部")
):
    """
    批量控制監控
    
    對多個伺服器執行監控控制操作
    """
    try:
        # 取得目標伺服器列表
        if server_ids:
            target_servers = server_ids
        else:
            server_states = push_service.get_server_states()
            target_servers = list(server_states.keys())
        
        results = []
        
        for server_id in target_servers:
            try:
                if action == "start":
                    push_service.activate_server(server_id)
                elif action == "stop":
                    push_service.deactivate_server(server_id)
                elif action == "restart":
                    push_service.deactivate_server(server_id)
                    await asyncio.sleep(0.5)
                    push_service.activate_server(server_id)
                
                results.append({
                    "server_id": server_id,
                    "success": True,
                    "action": action
                })
                
            except Exception as e:
                results.append({
                    "server_id": server_id,
                    "success": False,
                    "error": str(e)
                })
        
        successful_count = sum(1 for r in results if r["success"])
        
        return JSONResponse(content={
            "success": True,
            "data": {
                "action": action,
                "total_servers": len(target_servers),
                "successful_count": successful_count,
                "failed_count": len(target_servers) - successful_count,
                "results": results
            }
        })
        
    except Exception as e:
        logger.error(f"批量控制監控失敗: {e}")
        raise HTTPException(status_code=500, detail=f"批量操作失敗: {str(e)}")


@router.post("/batch/push-now", response_model=Dict[str, Any])
async def batch_push_data_now(
    server_ids: Optional[List[int]] = Query(None, description="伺服器 ID 列表，為空則推送全部")
):
    """
    批量立即推送數據
    
    對多個伺服器立即執行數據推送
    """
    try:
        if server_ids:
            # 推送指定伺服器
            successful_count = 0
            results = []
            
            for server_id in server_ids:
                try:
                    success = await push_server_monitoring_data(server_id)
                    results.append({
                        "server_id": server_id,
                        "success": success
                    })
                    if success:
                        successful_count += 1
                except Exception as e:
                    results.append({
                        "server_id": server_id,
                        "success": False,
                        "error": str(e)
                    })
        else:
            # 推送所有伺服器
            successful_count = await push_service.push_all_servers_immediately()
            results = []
        
        return JSONResponse(content={
            "success": True,
            "data": {
                "total_servers": len(server_ids) if server_ids else successful_count,
                "successful_count": successful_count,
                "results": results
            }
        })
        
    except Exception as e:
        logger.error(f"批量推送數據失敗: {e}")
        raise HTTPException(status_code=500, detail=f"批量推送失敗: {str(e)}")


# ==================== 統計資訊 ====================

@router.get("/stats/overview", response_model=Dict[str, Any])
async def get_servers_overview():
    """
    取得伺服器概覽統計
    
    包括總數、狀態分佈、推送統計等
    """
    try:
        # 取得推送服務統計
        push_stats = await get_push_service_stats()
        
        # 取得伺服器狀態分佈
        server_states = push_service.get_server_states()
        status_distribution = {}
        
        for state in server_states.values():
            status = state["last_status"]
            status_distribution[status] = status_distribution.get(status, 0) + 1
        
        overview = {
            "total_servers": len(server_states),
            "active_monitoring": sum(1 for s in server_states.values() if s["is_active"]),
            "status_distribution": status_distribution,
            "push_statistics": push_stats,
            "timestamp": datetime.now().isoformat()
        }
        
        return JSONResponse(content={
            "success": True,
            "data": overview
        })
        
    except Exception as e:
        logger.error(f"取得伺服器概覽失敗: {e}")
        raise HTTPException(status_code=500, detail=f"取得概覽失敗: {str(e)}")


# 需要的導入
import asyncio
from datetime import datetime