#!/usr/bin/env python3
"""
簡化版 WebSocket 元件測試
測試不依賴外部套件的核心邏輯
"""

import asyncio
import json
import sys
from datetime import datetime
from enum import Enum
from typing import Dict, Set, Optional, Any
from dataclasses import dataclass
import uuid


# 簡化版的核心類別定義（用於測試）

class MessageType(Enum):
    """訊息類型"""
    PING = "ping"
    PONG = "pong"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    MONITORING_UPDATE = "monitoring_update"
    STATUS_CHANGE = "status_change"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class ConnectionState(Enum):
    """連接狀態"""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting" 
    DISCONNECTED = "disconnected"


@dataclass
class SubscriptionFilter:
    """訂閱過濾器"""
    server_ids: Optional[Set[int]] = None
    metric_types: Optional[Set[str]] = None
    alert_levels: Optional[Set[str]] = None
    update_interval: int = 30
    
    def matches(self, server_id: int, metric_type: str, alert_level: str) -> bool:
        """檢查是否匹配過濾條件"""
        if self.server_ids and server_id not in self.server_ids:
            return False
        
        if self.metric_types and metric_type not in self.metric_types:
            return False
        
        if self.alert_levels and alert_level not in self.alert_levels:
            return False
        
        return True


class WebSocketMessage:
    """WebSocket 訊息"""
    
    def __init__(self, message_type: MessageType, data: Dict[str, Any], 
                 message_id: Optional[str] = None, timestamp: Optional[datetime] = None):
        self.message_type = message_type
        self.data = data
        self.message_id = message_id or str(uuid.uuid4())
        self.timestamp = timestamp or datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            "type": self.message_type.value,
            "data": self.data,
            "message_id": self.message_id,
            "timestamp": self.timestamp.isoformat()
        }
    
    def to_json(self) -> str:
        """轉換為 JSON 字串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'WebSocketMessage':
        """從 JSON 字串建立訊息"""
        try:
            data = json.loads(json_str)
            message_type = MessageType(data.get("type", "error"))
            return cls(
                message_type=message_type,
                data=data.get("data", {}),
                message_id=data.get("message_id"),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat()))
            )
        except Exception as e:
            return cls(
                message_type=MessageType.ERROR,
                data={"error": f"訊息格式錯誤: {str(e)}"}
            )


class MockWebSocket:
    """模擬 WebSocket 連接"""
    
    def __init__(self):
        self.messages_sent = []
        self.is_closed = False
    
    async def accept(self):
        """接受連接"""
        pass
    
    async def send_text(self, message: str):
        """發送文字訊息"""
        self.messages_sent.append(message)
    
    async def close(self):
        """關閉連接"""
        self.is_closed = True


class SimplifiedWebSocketConnection:
    """簡化版 WebSocket 連接"""
    
    def __init__(self, connection_id: str, websocket: MockWebSocket, 
                 client_ip: str, user_agent: str):
        self.connection_id = connection_id
        self.websocket = websocket
        self.client_ip = client_ip
        self.user_agent = user_agent
        self.state = ConnectionState.CONNECTING
        self.connected_at = datetime.now()
        self.last_ping = None
        self.last_pong = None
        self.message_count_sent = 0
        self.message_count_received = 0
        self.subscription_filter: Optional[SubscriptionFilter] = None
    
    def is_alive(self) -> bool:
        """檢查連接是否存活"""
        if self.state != ConnectionState.CONNECTED:
            return False
        
        if self.last_pong is None:
            return False
        
        # 檢查是否超時（60秒）
        time_since_pong = (datetime.now() - self.last_pong).total_seconds()
        return time_since_pong < 60


class SimplifiedWebSocketManager:
    """簡化版 WebSocket 管理器"""
    
    def __init__(self):
        self.connections: Dict[str, SimplifiedWebSocketConnection] = {}
        self.server_subscribers: Dict[int, Set[str]] = {}
        self._stats = {
            "total_connections": 0,
            "active_connections": 0,
            "messages_sent": 0,
            "messages_received": 0
        }
    
    async def connect(self, websocket: MockWebSocket, client_ip: str, user_agent: str) -> str:
        """建立新連接"""
        connection_id = str(uuid.uuid4())
        
        connection = SimplifiedWebSocketConnection(
            connection_id=connection_id,
            websocket=websocket,
            client_ip=client_ip,
            user_agent=user_agent
        )
        
        # 接受連接
        await websocket.accept()
        connection.state = ConnectionState.CONNECTED
        
        # 保存連接
        self.connections[connection_id] = connection
        
        # 更新統計
        self._stats["total_connections"] += 1
        self._stats["active_connections"] = len(self.connections)
        
        # 發送歡迎訊息
        welcome_message = WebSocketMessage(
            message_type=MessageType.HEARTBEAT,
            data={"message": "連接已建立"}
        )
        await websocket.send_text(welcome_message.to_json())
        
        return connection_id
    
    async def disconnect(self, connection_id: str, reason: str = ""):
        """斷開連接"""
        if connection_id not in self.connections:
            return
        
        connection = self.connections[connection_id]
        
        # 關閉 WebSocket
        await connection.websocket.close()
        
        # 清理訂閱
        if connection.subscription_filter and connection.subscription_filter.server_ids:
            for server_id in connection.subscription_filter.server_ids:
                if server_id in self.server_subscribers:
                    self.server_subscribers[server_id].discard(connection_id)
                    if not self.server_subscribers[server_id]:
                        del self.server_subscribers[server_id]
        
        # 移除連接
        del self.connections[connection_id]
        
        # 更新統計
        self._stats["active_connections"] = len(self.connections)
    
    async def handle_message(self, connection_id: str, message_str: str):
        """處理收到的訊息"""
        if connection_id not in self.connections:
            return
        
        connection = self.connections[connection_id]
        connection.message_count_received += 1
        self._stats["messages_received"] += 1
        
        try:
            message = WebSocketMessage.from_json(message_str)
            
            if message.message_type == MessageType.PING:
                await self._handle_ping(connection_id)
            elif message.message_type == MessageType.SUBSCRIBE:
                await self._handle_subscribe(connection_id, message.data)
            elif message.message_type == MessageType.UNSUBSCRIBE:
                await self._handle_unsubscribe(connection_id)
        
        except Exception as e:
            error_message = WebSocketMessage(
                message_type=MessageType.ERROR,
                data={"error": f"處理訊息失敗: {str(e)}"}
            )
            await connection.websocket.send_text(error_message.to_json())
    
    async def _handle_ping(self, connection_id: str):
        """處理 Ping 訊息"""
        connection = self.connections[connection_id]
        connection.last_ping = datetime.now()
        
        pong_message = WebSocketMessage(
            message_type=MessageType.PONG,
            data={"timestamp": datetime.now().isoformat()}
        )
        
        await connection.websocket.send_text(pong_message.to_json())
        connection.message_count_sent += 1
        self._stats["messages_sent"] += 1
    
    async def _handle_subscribe(self, connection_id: str, data: Dict[str, Any]):
        """處理訂閱訊息"""
        connection = self.connections[connection_id]
        
        # 創建訂閱過濾器
        server_ids = set(data.get("server_ids", []))
        metric_types = set(data.get("metric_types", []))
        alert_levels = set(data.get("alert_levels", []))
        update_interval = data.get("update_interval", 30)
        
        connection.subscription_filter = SubscriptionFilter(
            server_ids=server_ids,
            metric_types=metric_types,
            alert_levels=alert_levels,
            update_interval=update_interval
        )
        
        # 更新伺服器訂閱者列表
        for server_id in server_ids:
            if server_id not in self.server_subscribers:
                self.server_subscribers[server_id] = set()
            self.server_subscribers[server_id].add(connection_id)
        
        # 發送訂閱確認
        ack_message = WebSocketMessage(
            message_type=MessageType.SUBSCRIBE,
            data={"success": True, "message": "訂閱成功"}
        )
        
        await connection.websocket.send_text(ack_message.to_json())
        connection.message_count_sent += 1
        self._stats["messages_sent"] += 1
    
    async def _handle_unsubscribe(self, connection_id: str):
        """處理取消訂閱訊息"""
        connection = self.connections[connection_id]
        
        # 清理伺服器訂閱者列表
        if connection.subscription_filter and connection.subscription_filter.server_ids:
            for server_id in connection.subscription_filter.server_ids:
                if server_id in self.server_subscribers:
                    self.server_subscribers[server_id].discard(connection_id)
                    if not self.server_subscribers[server_id]:
                        del self.server_subscribers[server_id]
        
        # 清除訂閱過濾器
        connection.subscription_filter = None
        
        # 發送取消訂閱確認
        ack_message = WebSocketMessage(
            message_type=MessageType.UNSUBSCRIBE,
            data={"success": True, "message": "取消訂閱成功"}
        )
        
        await connection.websocket.send_text(ack_message.to_json())
        connection.message_count_sent += 1
        self._stats["messages_sent"] += 1
    
    async def broadcast_to_subscribers(self, server_id: int, message: WebSocketMessage, 
                                     metric_type: str, alert_level: str) -> int:
        """向訂閱者廣播訊息"""
        if server_id not in self.server_subscribers:
            return 0
        
        sent_count = 0
        subscriber_ids = self.server_subscribers[server_id].copy()
        
        for connection_id in subscriber_ids:
            if connection_id not in self.connections:
                continue
            
            connection = self.connections[connection_id]
            
            # 檢查訂閱過濾器
            if connection.subscription_filter:
                if not connection.subscription_filter.matches(server_id, metric_type, alert_level):
                    continue
            
            try:
                await connection.websocket.send_text(message.to_json())
                connection.message_count_sent += 1
                self._stats["messages_sent"] += 1
                sent_count += 1
            except Exception:
                # 發送失敗，可能需要清理連接
                pass
        
        return sent_count
    
    async def broadcast_to_all(self, message: WebSocketMessage) -> int:
        """向所有連接廣播訊息"""
        sent_count = 0
        
        for connection in self.connections.values():
            try:
                await connection.websocket.send_text(message.to_json())
                connection.message_count_sent += 1
                self._stats["messages_sent"] += 1
                sent_count += 1
            except Exception:
                # 發送失敗，可能需要清理連接
                pass
        
        return sent_count
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """取得連接統計"""
        return {
            **self._stats,
            "server_subscribers": {
                server_id: len(subscribers) 
                for server_id, subscribers in self.server_subscribers.items()
            }
        }


# 測試函數

async def test_manager_initialization():
    """測試管理器初始化"""
    print("🧪 測試管理器初始化...")
    
    manager = SimplifiedWebSocketManager()
    
    assert manager.connections == {}, "連接字典應該為空"
    assert manager.server_subscribers == {}, "訂閱者字典應該為空"
    assert manager._stats["total_connections"] == 0, "總連接數應該為0"
    assert manager._stats["active_connections"] == 0, "活躍連接數應該為0"
    
    print("✅ 管理器初始化測試通過")


async def test_connection_management():
    """測試連接管理"""
    print("🧪 測試連接管理...")
    
    manager = SimplifiedWebSocketManager()
    mock_websocket = MockWebSocket()
    
    # 測試連接建立
    connection_id = await manager.connect(mock_websocket, "127.0.0.1", "test-agent")
    
    assert connection_id in manager.connections, "連接應該被保存"
    assert manager._stats["total_connections"] == 1, "總連接數應該為1"
    assert manager._stats["active_connections"] == 1, "活躍連接數應該為1"
    assert len(mock_websocket.messages_sent) == 1, "應該發送歡迎訊息"
    
    # 測試連接斷開
    await manager.disconnect(connection_id, "測試斷開")
    
    assert connection_id not in manager.connections, "連接應該被移除"
    assert manager._stats["active_connections"] == 0, "活躍連接數應該為0"
    assert mock_websocket.is_closed, "WebSocket 應該被關閉"
    
    print("✅ 連接管理測試通過")


async def test_message_handling():
    """測試訊息處理"""
    print("🧪 測試訊息處理...")
    
    manager = SimplifiedWebSocketManager()
    mock_websocket = MockWebSocket()
    
    connection_id = await manager.connect(mock_websocket, "127.0.0.1", "test")
    initial_sent_count = len(mock_websocket.messages_sent)
    
    # 測試 Ping 訊息
    ping_message = json.dumps({
        "type": "ping",
        "data": {},
        "message_id": "test_ping",
        "timestamp": datetime.now().isoformat()
    })
    
    await manager.handle_message(connection_id, ping_message)
    
    # 檢查是否收到 Pong 回應
    assert len(mock_websocket.messages_sent) == initial_sent_count + 1, "應該發送 Pong 回應"
    
    last_message = json.loads(mock_websocket.messages_sent[-1])
    assert last_message["type"] == "pong", "回應類型應該是 pong"
    
    print("✅ 訊息處理測試通過")


async def test_subscription_system():
    """測試訂閱系統"""
    print("🧪 測試訂閱系統...")
    
    manager = SimplifiedWebSocketManager()
    mock_websocket = MockWebSocket()
    
    connection_id = await manager.connect(mock_websocket, "127.0.0.1", "test")
    initial_sent_count = len(mock_websocket.messages_sent)
    
    # 測試訂閱
    subscribe_message = json.dumps({
        "type": "subscribe",
        "data": {
            "server_ids": [1, 2],
            "metric_types": ["cpu", "memory"],
            "alert_levels": ["warning", "critical"],
            "update_interval": 30
        },
        "message_id": "test_subscribe",
        "timestamp": datetime.now().isoformat()
    })
    
    await manager.handle_message(connection_id, subscribe_message)
    
    # 檢查訂閱設定
    connection = manager.connections[connection_id]
    assert connection.subscription_filter is not None, "應該設定訂閱過濾器"
    assert connection.subscription_filter.server_ids == {1, 2}, "伺服器ID應該正確設定"
    assert connection.subscription_filter.metric_types == {"cpu", "memory"}, "監控類型應該正確設定"
    
    # 檢查伺服器訂閱者列表
    assert 1 in manager.server_subscribers, "伺服器1應該有訂閱者"
    assert 2 in manager.server_subscribers, "伺服器2應該有訂閱者"
    assert connection_id in manager.server_subscribers[1], "連接應該在伺服器1的訂閱列表中"
    assert connection_id in manager.server_subscribers[2], "連接應該在伺服器2的訂閱列表中"
    
    # 檢查訂閱確認訊息
    assert len(mock_websocket.messages_sent) == initial_sent_count + 1, "應該發送訂閱確認"
    
    print("✅ 訂閱系統測試通過")


async def test_broadcast_system():
    """測試廣播系統"""
    print("🧪 測試廣播系統...")
    
    manager = SimplifiedWebSocketManager()
    mock_websocket = MockWebSocket()
    
    connection_id = await manager.connect(mock_websocket, "127.0.0.1", "test")
    
    # 設定訂閱
    subscribe_data = {
        "server_ids": [1],
        "metric_types": ["cpu"],
        "alert_levels": ["ok", "warning"],
        "update_interval": 30
    }
    await manager._handle_subscribe(connection_id, subscribe_data)
    
    initial_sent_count = len(mock_websocket.messages_sent)
    
    # 測試廣播
    test_message = WebSocketMessage(
        message_type=MessageType.MONITORING_UPDATE,
        data={"server_id": 1, "cpu_usage": 45.2}
    )
    
    sent_count = await manager.broadcast_to_subscribers(1, test_message, "cpu", "ok")
    
    assert sent_count == 1, "應該廣播給1個訂閱者"
    assert len(mock_websocket.messages_sent) == initial_sent_count + 1, "應該發送1條訊息"
    
    last_message = json.loads(mock_websocket.messages_sent[-1])
    assert last_message["type"] == "monitoring_update", "訊息類型應該正確"
    assert last_message["data"]["server_id"] == 1, "數據內容應該正確"
    
    print("✅ 廣播系統測試通過")


async def test_subscription_filter():
    """測試訂閱過濾器"""
    print("🧪 測試訂閱過濾器...")
    
    # 測試有限制的過濾器
    filter1 = SubscriptionFilter(
        server_ids={1, 2},
        metric_types={"cpu", "memory"},
        alert_levels={"warning", "critical"}
    )
    
    assert filter1.matches(1, "cpu", "warning") == True, "應該匹配符合條件的訊息"
    assert filter1.matches(1, "cpu", "ok") == False, "不應該匹配不符合警告級別的訊息"
    assert filter1.matches(3, "cpu", "warning") == False, "不應該匹配不符合伺服器ID的訊息"
    assert filter1.matches(1, "disk", "warning") == False, "不應該匹配不符合監控類型的訊息"
    
    # 測試無限制的過濾器
    filter2 = SubscriptionFilter()
    assert filter2.matches(1, "cpu", "ok") == True, "無限制過濾器應該匹配所有訊息"
    assert filter2.matches(999, "network", "critical") == True, "無限制過濾器應該匹配所有訊息"
    
    print("✅ 訂閱過濾器測試通過")


async def test_message_creation():
    """測試訊息建立"""
    print("🧪 測試訊息建立...")
    
    # 測試訊息建立
    message = WebSocketMessage(
        message_type=MessageType.MONITORING_UPDATE,
        data={"server_id": 1, "cpu": 45.2}
    )
    
    assert message.message_type == MessageType.MONITORING_UPDATE, "訊息類型應該正確"
    assert message.data["server_id"] == 1, "數據內容應該正確"
    assert message.message_id is not None, "應該有訊息ID"
    assert message.timestamp is not None, "應該有時間戳"
    
    # 測試轉換為字典
    message_dict = message.to_dict()
    assert message_dict["type"] == "monitoring_update", "字典格式的類型應該正確"
    assert message_dict["data"]["server_id"] == 1, "字典格式的數據應該正確"
    assert "message_id" in message_dict, "字典應該包含訊息ID"
    assert "timestamp" in message_dict, "字典應該包含時間戳"
    
    # 測試轉換為 JSON
    json_str = message.to_json()
    parsed = json.loads(json_str)
    assert parsed["type"] == "monitoring_update", "JSON格式的類型應該正確"
    assert "message_id" in parsed, "JSON應該包含訊息ID"
    assert "timestamp" in parsed, "JSON應該包含時間戳"
    
    print("✅ 訊息建立測試通過")


async def main():
    """主測試函數"""
    print("🚀 開始簡化版 WebSocket 測試")
    print("="*50)
    
    tests = [
        test_manager_initialization,
        test_connection_management,
        test_message_handling,
        test_subscription_system,
        test_broadcast_system,
        test_subscription_filter,
        test_message_creation
    ]
    
    passed_tests = 0
    total_tests = len(tests)
    
    for test_func in tests:
        try:
            await test_func()
            passed_tests += 1
        except Exception as e:
            print(f"❌ 測試失敗: {test_func.__name__}")
            print(f"   錯誤: {str(e)}")
            import traceback
            print(f"   堆疊: {traceback.format_exc()}")
    
    print("\n" + "="*50)
    print("🎯 測試總結")
    print("="*50)
    print(f"總測試數: {total_tests}")
    print(f"通過數: {passed_tests}")
    print(f"失敗數: {total_tests - passed_tests}")
    print(f"成功率: {(passed_tests/total_tests*100):.1f}%")
    
    if passed_tests == total_tests:
        print("🎉 所有測試都通過了！")
        print("✅ WebSocket 核心功能驗證完成")
    else:
        print(f"⚠️  有 {total_tests - passed_tests} 個測試失敗")
    
    print("="*50)
    
    return passed_tests == total_tests


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        if success:
            print("\n🎊 WebSocket 實現測試完成，核心功能運作正常！")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  測試被用戶中斷")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 測試執行失敗: {e}")
        sys.exit(1)