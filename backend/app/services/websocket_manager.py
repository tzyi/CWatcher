"""
CWatcher WebSocket 即時推送管理服務

提供 WebSocket 連接管理、訂閱系統、即時數據推送功能
支援多客戶端連接、選擇性訂閱、心跳檢測和自動重連機制
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, List, Optional, Set, Any, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from fastapi import WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager

from app.core.config import settings

# 設定日誌
logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """WebSocket 連接狀態"""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class MessageType(Enum):
    """WebSocket 訊息類型"""
    # 基礎控制訊息
    PING = "ping"
    PONG = "pong"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    ERROR = "error"
    
    # 監控數據訊息
    MONITORING_UPDATE = "monitoring_update"
    STATUS_CHANGE = "status_change"
    SERVER_ONLINE = "server_online"
    SERVER_OFFLINE = "server_offline"
    
    # 系統訊息
    CONNECTION_INFO = "connection_info"
    SUBSCRIPTION_ACK = "subscription_ack"
    HEARTBEAT = "heartbeat"


@dataclass
class SubscriptionFilter:
    """訂閱過濾器"""
    server_ids: Optional[Set[int]] = None  # 訂閱的伺服器ID
    metric_types: Optional[Set[str]] = None  # 訂閱的指標類型 (cpu, memory, disk, network)
    alert_levels: Optional[Set[str]] = None  # 訂閱的警告等級 (ok, warning, critical)
    update_interval: int = 30  # 更新間隔 (秒)
    
    def matches(self, server_id: int, metric_type: str = None, alert_level: str = None) -> bool:
        """檢查是否符合訂閱條件"""
        if self.server_ids and server_id not in self.server_ids:
            return False
        
        if metric_type and self.metric_types and metric_type not in self.metric_types:
            return False
            
        if alert_level and self.alert_levels and alert_level not in self.alert_levels:
            return False
            
        return True


@dataclass
class WebSocketConnection:
    """WebSocket 連接信息"""
    connection_id: str
    websocket: WebSocket
    client_ip: str
    user_agent: str
    connected_at: datetime = field(default_factory=datetime.now)
    last_ping: datetime = field(default_factory=datetime.now)
    last_pong: datetime = field(default_factory=datetime.now)
    state: ConnectionState = ConnectionState.CONNECTING
    subscription_filter: Optional[SubscriptionFilter] = None
    message_count_sent: int = 0
    message_count_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    
    def is_alive(self) -> bool:
        """檢查連接是否存活"""
        return (self.state == ConnectionState.CONNECTED and 
                datetime.now() - self.last_pong < timedelta(seconds=60))
    
    def get_connection_info(self) -> Dict[str, Any]:
        """取得連接資訊"""
        return {
            "connection_id": self.connection_id,
            "client_ip": self.client_ip,
            "user_agent": self.user_agent,
            "connected_at": self.connected_at.isoformat(),
            "state": self.state.value,
            "uptime_seconds": int((datetime.now() - self.connected_at).total_seconds()),
            "messages_sent": self.message_count_sent,
            "messages_received": self.message_count_received,
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "subscription": {
                "server_ids": list(self.subscription_filter.server_ids) if self.subscription_filter and self.subscription_filter.server_ids else [],
                "metric_types": list(self.subscription_filter.metric_types) if self.subscription_filter and self.subscription_filter.metric_types else [],
                "update_interval": self.subscription_filter.update_interval if self.subscription_filter else 30
            }
        }


class WebSocketMessage:
    """WebSocket 訊息封裝"""
    
    def __init__(self, message_type: MessageType, data: Dict[str, Any] = None, 
                 message_id: str = None, timestamp: datetime = None):
        self.message_type = message_type
        self.data = data or {}
        self.message_id = message_id or str(uuid.uuid4())
        self.timestamp = timestamp or datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            "type": self.message_type.value,
            "data": self.data,
            "message_id": self.message_id,
            "timestamp": self.timestamp.isoformat()
        }
    
    def to_json(self) -> str:
        """轉換為JSON字串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'WebSocketMessage':
        """從JSON字串建立訊息"""
        try:
            data = json.loads(json_str)
            message_type = MessageType(data.get("type", "error"))
            return cls(
                message_type=message_type,
                data=data.get("data", {}),
                message_id=data.get("message_id"),
                timestamp=datetime.fromisoformat(data.get("timestamp")) if data.get("timestamp") else None
            )
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning(f"解析 WebSocket 訊息失敗: {e}")
            return cls(
                message_type=MessageType.ERROR,
                data={"error": "訊息格式錯誤", "original_error": str(e)}
            )


class WebSocketManager:
    """WebSocket 連接管理器"""
    
    def __init__(self):
        self.connections: Dict[str, WebSocketConnection] = {}
        self.server_subscribers: Dict[int, Set[str]] = {}  # server_id -> connection_ids
        self.connection_lock = asyncio.Lock()
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        self.broadcast_queue: asyncio.Queue = asyncio.Queue()
        self.broadcast_task: Optional[asyncio.Task] = None
        self._stats = {
            "total_connections": 0,
            "active_connections": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "bytes_sent": 0,
            "bytes_received": 0,
            "start_time": datetime.now()
        }
        
        # 啟動背景任務
        self._start_background_tasks()
    
    def _start_background_tasks(self):
        """啟動背景任務"""
        if not self.heartbeat_task or self.heartbeat_task.done():
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        if not self.cleanup_task or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            
        if not self.broadcast_task or self.broadcast_task.done():
            self.broadcast_task = asyncio.create_task(self._broadcast_loop())
    
    async def connect(self, websocket: WebSocket, client_ip: str = "unknown", 
                     user_agent: str = "unknown") -> str:
        """建立 WebSocket 連接"""
        connection_id = str(uuid.uuid4())
        
        try:
            await websocket.accept()
            
            async with self.connection_lock:
                connection = WebSocketConnection(
                    connection_id=connection_id,
                    websocket=websocket,
                    client_ip=client_ip,
                    user_agent=user_agent,
                    state=ConnectionState.CONNECTED
                )
                
                self.connections[connection_id] = connection
                self._stats["total_connections"] += 1
                self._stats["active_connections"] = len(self.connections)
            
            # 發送連接確認訊息
            welcome_message = WebSocketMessage(
                message_type=MessageType.CONNECTION_INFO,
                data={
                    "connection_id": connection_id,
                    "server_time": datetime.now().isoformat(),
                    "supported_message_types": [t.value for t in MessageType],
                    "heartbeat_interval": 30,
                    "max_idle_time": 300
                }
            )
            
            await self._send_message_to_connection(connection_id, welcome_message)
            
            logger.info(f"WebSocket 連接建立: {connection_id} from {client_ip}")
            return connection_id
            
        except Exception as e:
            logger.error(f"建立 WebSocket 連接失敗: {e}")
            raise
    
    async def disconnect(self, connection_id: str, reason: str = "client_disconnect"):
        """斷開 WebSocket 連接"""
        async with self.connection_lock:
            if connection_id not in self.connections:
                return
            
            connection = self.connections[connection_id]
            connection.state = ConnectionState.DISCONNECTING
            
            try:
                # 從訂閱列表中移除
                self._remove_from_subscriptions(connection_id)
                
                # 關閉 WebSocket 連接
                if connection.websocket:
                    try:
                        await connection.websocket.close()
                    except:
                        pass
                
                # 移除連接記錄
                del self.connections[connection_id]
                self._stats["active_connections"] = len(self.connections)
                
                logger.info(f"WebSocket 連接斷開: {connection_id}, 原因: {reason}")
                
            except Exception as e:
                logger.error(f"斷開 WebSocket 連接失敗: {e}")
    
    def _remove_from_subscriptions(self, connection_id: str):
        """從所有訂閱中移除連接"""
        for server_id, subscribers in self.server_subscribers.items():
            subscribers.discard(connection_id)
        
        # 清理空的訂閱
        empty_servers = [server_id for server_id, subscribers in self.server_subscribers.items() 
                        if not subscribers]
        for server_id in empty_servers:
            del self.server_subscribers[server_id]
    
    async def handle_message(self, connection_id: str, message_data: str):
        """處理接收到的 WebSocket 訊息"""
        if connection_id not in self.connections:
            return
        
        connection = self.connections[connection_id]
        connection.message_count_received += 1
        connection.bytes_received += len(message_data.encode('utf-8'))
        self._stats["messages_received"] += 1
        self._stats["bytes_received"] += len(message_data.encode('utf-8'))
        
        try:
            message = WebSocketMessage.from_json(message_data)
            
            # 處理不同類型的訊息
            if message.message_type == MessageType.PING:
                await self._handle_ping(connection_id)
            
            elif message.message_type == MessageType.PONG:
                await self._handle_pong(connection_id)
            
            elif message.message_type == MessageType.SUBSCRIBE:
                await self._handle_subscribe(connection_id, message.data)
            
            elif message.message_type == MessageType.UNSUBSCRIBE:
                await self._handle_unsubscribe(connection_id, message.data)
            
            else:
                logger.warning(f"未知的訊息類型: {message.message_type} from {connection_id}")
                
        except Exception as e:
            logger.error(f"處理 WebSocket 訊息失敗: {e}")
            await self._send_error_message(connection_id, f"訊息處理失敗: {e}")
    
    async def _handle_ping(self, connection_id: str):
        """處理 Ping 訊息"""
        connection = self.connections.get(connection_id)
        if connection:
            connection.last_ping = datetime.now()
            pong_message = WebSocketMessage(MessageType.PONG)
            await self._send_message_to_connection(connection_id, pong_message)
    
    async def _handle_pong(self, connection_id: str):
        """處理 Pong 訊息"""
        connection = self.connections.get(connection_id)
        if connection:
            connection.last_pong = datetime.now()
    
    async def _handle_subscribe(self, connection_id: str, subscribe_data: Dict[str, Any]):
        """處理訂閱請求"""
        try:
            # 解析訂閱參數
            server_ids = set(subscribe_data.get("server_ids", []))
            metric_types = set(subscribe_data.get("metric_types", ["cpu", "memory", "disk", "network"]))
            alert_levels = set(subscribe_data.get("alert_levels", ["ok", "warning", "critical"]))
            update_interval = subscribe_data.get("update_interval", 30)
            
            # 驗證參數
            if update_interval < 10 or update_interval > 300:
                update_interval = 30
            
            # 建立訂閱過濾器
            subscription_filter = SubscriptionFilter(
                server_ids=server_ids if server_ids else None,
                metric_types=metric_types,
                alert_levels=alert_levels,
                update_interval=update_interval
            )
            
            # 更新連接的訂閱設定
            connection = self.connections.get(connection_id)
            if connection:
                connection.subscription_filter = subscription_filter
                
                # 更新伺服器訂閱者列表
                async with self.connection_lock:
                    # 清除舊的訂閱
                    self._remove_from_subscriptions(connection_id)
                    
                    # 添加新的訂閱
                    if server_ids:
                        for server_id in server_ids:
                            if server_id not in self.server_subscribers:
                                self.server_subscribers[server_id] = set()
                            self.server_subscribers[server_id].add(connection_id)
                    else:
                        # 訂閱所有伺服器 (如果有的話)
                        pass
                
                # 發送訂閱確認
                ack_message = WebSocketMessage(
                    message_type=MessageType.SUBSCRIPTION_ACK,
                    data={
                        "success": True,
                        "subscription": {
                            "server_ids": list(server_ids) if server_ids else "all",
                            "metric_types": list(metric_types),
                            "alert_levels": list(alert_levels),
                            "update_interval": update_interval
                        }
                    }
                )
                
                await self._send_message_to_connection(connection_id, ack_message)
                
                logger.info(f"訂閱設定完成: {connection_id}, 伺服器: {server_ids or 'all'}")
            
        except Exception as e:
            logger.error(f"處理訂閱請求失敗: {e}")
            await self._send_error_message(connection_id, f"訂閱失敗: {e}")
    
    async def _handle_unsubscribe(self, connection_id: str, unsubscribe_data: Dict[str, Any]):
        """處理取消訂閱請求"""
        try:
            connection = self.connections.get(connection_id)
            if connection:
                # 從訂閱列表中移除
                self._remove_from_subscriptions(connection_id)
                connection.subscription_filter = None
                
                # 發送取消訂閱確認
                ack_message = WebSocketMessage(
                    message_type=MessageType.SUBSCRIPTION_ACK,
                    data={"success": True, "subscription": None}
                )
                
                await self._send_message_to_connection(connection_id, ack_message)
                logger.info(f"取消訂閱完成: {connection_id}")
            
        except Exception as e:
            logger.error(f"處理取消訂閱請求失敗: {e}")
            await self._send_error_message(connection_id, f"取消訂閱失敗: {e}")
    
    async def _send_error_message(self, connection_id: str, error_message: str):
        """發送錯誤訊息"""
        error_msg = WebSocketMessage(
            message_type=MessageType.ERROR,
            data={"error": error_message, "timestamp": datetime.now().isoformat()}
        )
        await self._send_message_to_connection(connection_id, error_msg)
    
    async def _send_message_to_connection(self, connection_id: str, message: WebSocketMessage):
        """發送訊息到指定連接"""
        connection = self.connections.get(connection_id)
        if not connection or connection.state != ConnectionState.CONNECTED:
            return False
        
        try:
            message_json = message.to_json()
            await connection.websocket.send_text(message_json)
            
            # 更新統計
            connection.message_count_sent += 1
            connection.bytes_sent += len(message_json.encode('utf-8'))
            self._stats["messages_sent"] += 1
            self._stats["bytes_sent"] += len(message_json.encode('utf-8'))
            
            return True
            
        except WebSocketDisconnect:
            logger.info(f"WebSocket 連接已斷開: {connection_id}")
            await self.disconnect(connection_id, "websocket_disconnect")
            return False
        except Exception as e:
            logger.error(f"發送 WebSocket 訊息失敗: {e}")
            connection.state = ConnectionState.ERROR
            return False
    
    async def broadcast_to_subscribers(self, server_id: int, message: WebSocketMessage, 
                                     metric_type: str = None, alert_level: str = None):
        """廣播訊息給訂閱者"""
        if server_id not in self.server_subscribers:
            return 0
        
        sent_count = 0
        subscribers = self.server_subscribers[server_id].copy()  # 複製以避免並發修改
        
        for connection_id in subscribers:
            connection = self.connections.get(connection_id)
            if not connection or not connection.subscription_filter:
                continue
            
            # 檢查是否符合訂閱條件
            if connection.subscription_filter.matches(server_id, metric_type, alert_level):
                success = await self._send_message_to_connection(connection_id, message)
                if success:
                    sent_count += 1
        
        return sent_count
    
    async def broadcast_to_all(self, message: WebSocketMessage):
        """廣播訊息給所有連接"""
        sent_count = 0
        
        for connection_id in list(self.connections.keys()):  # 複製鍵以避免並發修改
            success = await self._send_message_to_connection(connection_id, message)
            if success:
                sent_count += 1
        
        return sent_count
    
    async def _heartbeat_loop(self):
        """心跳檢測循環"""
        while True:
            try:
                await asyncio.sleep(30)  # 每30秒檢查一次
                
                current_time = datetime.now()
                disconnected_connections = []
                
                for connection_id, connection in self.connections.items():
                    # 檢查連接是否超時
                    if not connection.is_alive():
                        disconnected_connections.append(connection_id)
                        continue
                    
                    # 發送心跳
                    if current_time - connection.last_ping > timedelta(seconds=30):
                        heartbeat_message = WebSocketMessage(MessageType.HEARTBEAT)
                        await self._send_message_to_connection(connection_id, heartbeat_message)
                
                # 清理斷開的連接
                for connection_id in disconnected_connections:
                    await self.disconnect(connection_id, "heartbeat_timeout")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳檢測循環錯誤: {e}")
                await asyncio.sleep(5)
    
    async def _cleanup_loop(self):
        """清理循環"""
        while True:
            try:
                await asyncio.sleep(300)  # 每5分鐘執行一次
                
                # 清理統計數據
                if len(self.connections) == 0:
                    self._stats["messages_sent"] = 0
                    self._stats["messages_received"] = 0
                    self._stats["bytes_sent"] = 0
                    self._stats["bytes_received"] = 0
                
                logger.debug(f"WebSocket 清理完成，當前連接數: {len(self.connections)}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"WebSocket 清理循環錯誤: {e}")
                await asyncio.sleep(30)
    
    async def _broadcast_loop(self):
        """廣播循環處理"""
        while True:
            try:
                # 從廣播隊列中取得訊息
                broadcast_item = await self.broadcast_queue.get()
                
                if broadcast_item is None:  # 終止信號
                    break
                
                # 解析廣播項目
                message = broadcast_item.get("message")
                server_id = broadcast_item.get("server_id")
                metric_type = broadcast_item.get("metric_type")
                alert_level = broadcast_item.get("alert_level")
                broadcast_all = broadcast_item.get("broadcast_all", False)
                
                if broadcast_all:
                    await self.broadcast_to_all(message)
                elif server_id is not None:
                    await self.broadcast_to_subscribers(server_id, message, metric_type, alert_level)
                
                self.broadcast_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"廣播循環錯誤: {e}")
                await asyncio.sleep(1)
    
    async def queue_broadcast(self, message: WebSocketMessage, server_id: int = None, 
                            metric_type: str = None, alert_level: str = None, 
                            broadcast_all: bool = False):
        """將廣播訊息加入隊列"""
        try:
            broadcast_item = {
                "message": message,
                "server_id": server_id,
                "metric_type": metric_type,
                "alert_level": alert_level,
                "broadcast_all": broadcast_all
            }
            
            await self.broadcast_queue.put(broadcast_item)
            
        except Exception as e:
            logger.error(f"加入廣播隊列失敗: {e}")
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """取得連接統計"""
        current_time = datetime.now()
        uptime_seconds = int((current_time - self._stats["start_time"]).total_seconds())
        
        return {
            "total_connections": self._stats["total_connections"],
            "active_connections": len(self.connections),
            "messages_sent": self._stats["messages_sent"],
            "messages_received": self._stats["messages_received"],
            "bytes_sent": self._stats["bytes_sent"],
            "bytes_received": self._stats["bytes_received"],
            "uptime_seconds": uptime_seconds,
            "server_subscribers": {
                server_id: len(subscribers) 
                for server_id, subscribers in self.server_subscribers.items()
            }
        }
    
    def get_connection_info(self, connection_id: str = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """取得連接資訊"""
        if connection_id:
            connection = self.connections.get(connection_id)
            return connection.get_connection_info() if connection else None
        else:
            return [conn.get_connection_info() for conn in self.connections.values()]
    
    async def shutdown(self):
        """關閉 WebSocket 管理器"""
        logger.info("正在關閉 WebSocket 管理器...")
        
        # 停止背景任務
        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
            
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            
        if self.broadcast_task and not self.broadcast_task.done():
            # 發送終止信號
            await self.broadcast_queue.put(None)
            self.broadcast_task.cancel()
        
        # 斷開所有連接
        connection_ids = list(self.connections.keys())
        for connection_id in connection_ids:
            await self.disconnect(connection_id, "server_shutdown")
        
        logger.info("WebSocket 管理器已關閉")


# 全域 WebSocket 管理器實例
websocket_manager = WebSocketManager()


# 便利函數
async def get_websocket_manager() -> WebSocketManager:
    """取得 WebSocket 管理器實例"""
    return websocket_manager


async def broadcast_monitoring_update(server_id: int, monitoring_data: Dict[str, Any]):
    """廣播監控數據更新"""
    message = WebSocketMessage(
        message_type=MessageType.MONITORING_UPDATE,
        data={
            "server_id": server_id,
            "timestamp": datetime.now().isoformat(),
            "data": monitoring_data
        }
    )
    
    await websocket_manager.queue_broadcast(
        message=message,
        server_id=server_id,
        metric_type="all"
    )


async def broadcast_status_change(server_id: int, old_status: str, new_status: str, reason: str = None):
    """廣播伺服器狀態變化"""
    message = WebSocketMessage(
        message_type=MessageType.STATUS_CHANGE,
        data={
            "server_id": server_id,
            "old_status": old_status,
            "new_status": new_status,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }
    )
    
    await websocket_manager.queue_broadcast(
        message=message,
        server_id=server_id,
        alert_level="warning" if new_status in ["warning", "offline"] else "ok"
    )


if __name__ == "__main__":
    # 測試 WebSocket 管理器
    
    async def test_websocket_manager():
        """測試 WebSocket 管理器"""
        print("🧪 測試 WebSocket 管理器")
        
        manager = WebSocketManager()
        
        # 測試訊息建立
        test_message = WebSocketMessage(
            message_type=MessageType.MONITORING_UPDATE,
            data={"server_id": 1, "cpu_usage": 45.2}
        )
        
        print(f"✅ 測試訊息: {test_message.to_json()}")
        
        # 測試訊息解析
        parsed_message = WebSocketMessage.from_json(test_message.to_json())
        print(f"✅ 解析訊息: {parsed_message.message_type.value}")
        
        # 測試統計
        stats = manager.get_connection_stats()
        print(f"✅ 連接統計: {stats}")
        
        await manager.shutdown()
        print("✅ WebSocket 管理器測試完成")
    
    # 執行測試
    import asyncio
    asyncio.run(test_websocket_manager())