"""
CWatcher WebSocket API 端點

提供 WebSocket 連接端點和管理功能
支援即時監控數據推送、訂閱管理和連接狀態查詢
"""

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.services.websocket_manager import websocket_manager, WebSocketManager
from app.core.deps import get_current_user  # 如果需要身份驗證
from app.core.config import settings

# 設定日誌
logger = logging.getLogger(__name__)

router = APIRouter()


def get_client_info(websocket: WebSocket) -> tuple[str, str]:
    """取得客戶端資訊"""
    # 取得客戶端 IP
    client_ip = "unknown"
    if websocket.client:
        client_ip = websocket.client.host
    
    # 從 headers 中取得更多資訊
    headers = dict(websocket.headers)
    
    # 檢查是否有代理 IP
    forwarded_for = headers.get("x-forwarded-for")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    
    real_ip = headers.get("x-real-ip")
    if real_ip:
        client_ip = real_ip
    
    # 取得 User-Agent
    user_agent = headers.get("user-agent", "unknown")
    
    return client_ip, user_agent


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 主要連接端點
    
    提供即時監控數據推送服務
    支援：
    - 即時監控數據接收
    - 伺服器狀態變化通知
    - 選擇性訂閱功能
    - 心跳檢測機制
    """
    client_ip, user_agent = get_client_info(websocket)
    connection_id = None
    
    try:
        # 建立 WebSocket 連接
        connection_id = await websocket_manager.connect(websocket, client_ip, user_agent)
        logger.info(f"WebSocket 連接建立: {connection_id} from {client_ip}")
        
        # 主要訊息處理循環
        while True:
            try:
                # 接收客戶端訊息
                message = await websocket.receive_text()
                
                # 處理訊息
                await websocket_manager.handle_message(connection_id, message)
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket 客戶端主動斷開: {connection_id}")
                break
                
            except Exception as e:
                logger.error(f"WebSocket 訊息處理錯誤: {e}")
                # 可以選擇是否繼續處理或斷開連接
                break
    
    except Exception as e:
        logger.error(f"WebSocket 連接錯誤: {e}")
        
    finally:
        # 清理連接
        if connection_id:
            await websocket_manager.disconnect(connection_id, "connection_closed")


@router.websocket("/ws/monitoring/{server_id}")
async def websocket_server_monitoring(websocket: WebSocket, server_id: int):
    """
    特定伺服器監控 WebSocket 端點
    
    直接訂閱指定伺服器的監控數據
    自動設定訂閱過濾器只接收該伺服器的數據
    """
    client_ip, user_agent = get_client_info(websocket)
    connection_id = None
    
    try:
        # 建立 WebSocket 連接
        connection_id = await websocket_manager.connect(websocket, client_ip, user_agent)
        logger.info(f"伺服器 {server_id} 監控連接建立: {connection_id}")
        
        # 自動訂閱指定伺服器
        subscribe_data = {
            "server_ids": [server_id],
            "metric_types": ["cpu", "memory", "disk", "network"],
            "alert_levels": ["ok", "warning", "critical"],
            "update_interval": 30
        }
        
        await websocket_manager._handle_subscribe(connection_id, subscribe_data)
        
        # 主要訊息處理循環
        while True:
            try:
                message = await websocket.receive_text()
                await websocket_manager.handle_message(connection_id, message)
                
            except WebSocketDisconnect:
                logger.info(f"伺服器 {server_id} 監控連接斷開: {connection_id}")
                break
                
            except Exception as e:
                logger.error(f"伺服器 {server_id} 監控訊息處理錯誤: {e}")
                break
    
    except Exception as e:
        logger.error(f"伺服器 {server_id} WebSocket 連接錯誤: {e}")
        
    finally:
        if connection_id:
            await websocket_manager.disconnect(connection_id, "server_monitoring_closed")


@router.get("/connections/stats")
async def get_websocket_stats():
    """
    取得 WebSocket 連接統計
    
    回傳：
    - 總連接數
    - 活躍連接數
    - 訊息傳輸統計
    - 伺服器訂閱統計
    """
    try:
        stats = websocket_manager.get_connection_stats()
        return JSONResponse(content={
            "success": True,
            "data": stats
        })
        
    except Exception as e:
        logger.error(f"取得 WebSocket 統計失敗: {e}")
        raise HTTPException(status_code=500, detail=f"取得統計失敗: {str(e)}")


@router.get("/connections")
async def get_websocket_connections(
    connection_id: Optional[str] = Query(None, description="特定連接ID")
):
    """
    取得 WebSocket 連接資訊
    
    如果提供 connection_id，回傳特定連接的詳細資訊
    否則回傳所有連接的列表
    """
    try:
        if connection_id:
            # 取得特定連接資訊
            connection_info = websocket_manager.get_connection_info(connection_id)
            if not connection_info:
                raise HTTPException(status_code=404, detail="連接不存在")
            
            return JSONResponse(content={
                "success": True,
                "data": connection_info
            })
        else:
            # 取得所有連接資訊
            connections = websocket_manager.get_connection_info()
            return JSONResponse(content={
                "success": True,
                "data": {
                    "total_connections": len(connections),
                    "connections": connections
                }
            })
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得 WebSocket 連接資訊失敗: {e}")
        raise HTTPException(status_code=500, detail=f"取得連接資訊失敗: {str(e)}")


@router.post("/broadcast")
async def broadcast_message(
    message_data: Dict[str, Any]
):
    """
    廣播訊息到所有連接
    
    用於系統管理員發送系統通知或緊急訊息
    """
    try:
        from app.services.websocket_manager import WebSocketMessage, MessageType
        
        # 驗證訊息格式
        if "type" not in message_data or "data" not in message_data:
            raise HTTPException(status_code=400, detail="訊息格式錯誤，需要 type 和 data 欄位")
        
        # 建立訊息
        try:
            message_type = MessageType(message_data["type"])
        except ValueError:
            raise HTTPException(status_code=400, detail=f"不支援的訊息類型: {message_data['type']}")
        
        message = WebSocketMessage(
            message_type=message_type,
            data=message_data["data"]
        )
        
        # 廣播訊息
        sent_count = await websocket_manager.broadcast_to_all(message)
        
        return JSONResponse(content={
            "success": True,
            "data": {
                "message_sent": True,
                "recipients": sent_count,
                "message_id": message.message_id
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"廣播訊息失敗: {e}")
        raise HTTPException(status_code=500, detail=f"廣播失敗: {str(e)}")


@router.post("/servers/{server_id}/broadcast")
async def broadcast_to_server_subscribers(
    server_id: int,
    message_data: Dict[str, Any]
):
    """
    廣播訊息到特定伺服器的訂閱者
    
    用於向特定伺服器的監控客戶端發送訊息
    """
    try:
        from app.services.websocket_manager import WebSocketMessage, MessageType
        
        # 驗證訊息格式
        if "type" not in message_data or "data" not in message_data:
            raise HTTPException(status_code=400, detail="訊息格式錯誤，需要 type 和 data 欄位")
        
        # 建立訊息
        try:
            message_type = MessageType(message_data["type"])
        except ValueError:
            raise HTTPException(status_code=400, detail=f"不支援的訊息類型: {message_data['type']}")
        
        message = WebSocketMessage(
            message_type=message_type,
            data=message_data["data"]
        )
        
        # 廣播到伺服器訂閱者
        metric_type = message_data.get("metric_type")
        alert_level = message_data.get("alert_level")
        
        sent_count = await websocket_manager.broadcast_to_subscribers(
            server_id, message, metric_type, alert_level
        )
        
        return JSONResponse(content={
            "success": True,
            "data": {
                "message_sent": True,
                "server_id": server_id,
                "recipients": sent_count,
                "message_id": message.message_id
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"廣播伺服器訊息失敗: {e}")
        raise HTTPException(status_code=500, detail=f"廣播失敗: {str(e)}")


@router.delete("/connections/{connection_id}")
async def disconnect_websocket(connection_id: str):
    """
    強制斷開特定 WebSocket 連接
    
    用於管理員強制斷開有問題的連接
    """
    try:
        # 檢查連接是否存在
        connection_info = websocket_manager.get_connection_info(connection_id)
        if not connection_info:
            raise HTTPException(status_code=404, detail="連接不存在")
        
        # 斷開連接
        await websocket_manager.disconnect(connection_id, "admin_disconnect")
        
        return JSONResponse(content={
            "success": True,
            "data": {
                "connection_id": connection_id,
                "disconnected": True,
                "reason": "admin_disconnect"
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"強制斷開連接失敗: {e}")
        raise HTTPException(status_code=500, detail=f"斷開連接失敗: {str(e)}")


@router.get("/health")
async def websocket_health_check():
    """
    WebSocket 服務健康檢查
    
    檢查 WebSocket 管理器狀態和背景任務運行情況
    """
    try:
        stats = websocket_manager.get_connection_stats()
        
        # 檢查背景任務狀態
        background_tasks = {
            "heartbeat_task": websocket_manager.heartbeat_task is not None and not websocket_manager.heartbeat_task.done(),
            "cleanup_task": websocket_manager.cleanup_task is not None and not websocket_manager.cleanup_task.done(),
            "broadcast_task": websocket_manager.broadcast_task is not None and not websocket_manager.broadcast_task.done()
        }
        
        # 計算健康狀態
        all_tasks_running = all(background_tasks.values())
        health_status = "healthy" if all_tasks_running else "degraded"
        
        return JSONResponse(content={
            "success": True,
            "data": {
                "status": health_status,
                "active_connections": stats["active_connections"],
                "uptime_seconds": stats["uptime_seconds"],
                "background_tasks": background_tasks,
                "queue_size": websocket_manager.broadcast_queue.qsize()
            }
        })
        
    except Exception as e:
        logger.error(f"WebSocket 健康檢查失敗: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "data": {
                    "status": "unhealthy",
                    "error": str(e)
                }
            }
        )


# 添加到主應用程式的生命週期事件中
async def setup_websocket_manager():
    """初始化 WebSocket 管理器"""
    # WebSocket 管理器會在導入時自動初始化
    logger.info("WebSocket 管理器已準備就緒")


async def shutdown_websocket_manager():
    """關閉 WebSocket 管理器"""
    await websocket_manager.shutdown()
    logger.info("WebSocket 管理器已關閉")


# 導出清理函數供主應用程式使用
__all__ = ["router", "setup_websocket_manager", "shutdown_websocket_manager"]