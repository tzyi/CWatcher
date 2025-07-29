"""
CWatcher WebSocket 管理器單元測試

測試 WebSocket 連接管理、訊息處理、訂閱系統和廣播功能
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from app.services.websocket_manager import (
    WebSocketManager, WebSocketConnection, WebSocketMessage, MessageType,
    ConnectionState, SubscriptionFilter
)


class TestWebSocketManager:
    """WebSocket 管理器測試"""
    
    @pytest.fixture
    def manager(self):
        """建立測試用的 WebSocket 管理器"""
        return WebSocketManager()
    
    @pytest.fixture
    def mock_websocket(self):
        """建立模擬的 WebSocket 連接"""
        websocket = Mock()
        websocket.accept = AsyncMock()
        websocket.send_text = AsyncMock()
        websocket.close = AsyncMock()
        return websocket
    
    def test_websocket_manager_initialization(self, manager):
        """測試 WebSocket 管理器初始化"""
        assert manager.connections == {}
        assert manager.server_subscribers == {}
        assert manager.broadcast_queue is not None
        assert manager.heartbeat_task is not None
        assert manager.cleanup_task is not None
        assert manager.broadcast_task is not None
    
    @pytest.mark.asyncio
    async def test_connect_websocket(self, manager, mock_websocket):
        """測試 WebSocket 連接建立"""
        client_ip = "127.0.0.1"
        user_agent = "test-agent"
        
        connection_id = await manager.connect(mock_websocket, client_ip, user_agent)
        
        # 驗證連接建立
        assert connection_id in manager.connections
        connection = manager.connections[connection_id]
        assert connection.websocket == mock_websocket
        assert connection.client_ip == client_ip
        assert connection.user_agent == user_agent
        assert connection.state == ConnectionState.CONNECTED
        
        # 驗證 WebSocket 被接受
        mock_websocket.accept.assert_called_once()
        
        # 驗證歡迎訊息被發送
        mock_websocket.send_text.assert_called_once()
        
        # 驗證統計更新
        assert manager._stats["total_connections"] == 1
        assert manager._stats["active_connections"] == 1
    
    @pytest.mark.asyncio
    async def test_disconnect_websocket(self, manager, mock_websocket):
        """測試 WebSocket 連接斷開"""
        # 先建立連接
        connection_id = await manager.connect(mock_websocket, "127.0.0.1", "test")
        
        # 斷開連接
        await manager.disconnect(connection_id, "test_disconnect")
        
        # 驗證連接被移除
        assert connection_id not in manager.connections
        assert manager._stats["active_connections"] == 0
        
        # 驗證 WebSocket 被關閉
        mock_websocket.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_ping_message(self, manager, mock_websocket):
        """測試 Ping 訊息處理"""
        # 建立連接
        connection_id = await manager.connect(mock_websocket, "127.0.0.1", "test")
        
        # 重置 mock 以清除歡迎訊息的調用記錄
        mock_websocket.send_text.reset_mock()
        
        # 發送 Ping 訊息
        ping_message = json.dumps({
            "type": "ping",
            "data": {},
            "message_id": "test_ping",
            "timestamp": datetime.now().isoformat()
        })
        
        await manager.handle_message(connection_id, ping_message)
        
        # 驗證 Pong 回應
        mock_websocket.send_text.assert_called_once()
        sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_message["type"] == "pong"
    
    @pytest.mark.asyncio
    async def test_handle_subscribe_message(self, manager, mock_websocket):
        """測試訂閱訊息處理"""
        # 建立連接
        connection_id = await manager.connect(mock_websocket, "127.0.0.1", "test")
        mock_websocket.send_text.reset_mock()
        
        # 發送訂閱訊息
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
        
        # 驗證訂閱設定
        connection = manager.connections[connection_id]
        assert connection.subscription_filter is not None
        assert connection.subscription_filter.server_ids == {1, 2}
        assert connection.subscription_filter.metric_types == {"cpu", "memory"}
        assert connection.subscription_filter.update_interval == 30
        
        # 驗證伺服器訂閱者列表
        assert 1 in manager.server_subscribers
        assert 2 in manager.server_subscribers
        assert connection_id in manager.server_subscribers[1]
        assert connection_id in manager.server_subscribers[2]
        
        # 驗證訂閱確認訊息
        mock_websocket.send_text.assert_called_once()
        sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_message["type"] == "subscription_ack"
        assert sent_message["data"]["success"] is True
    
    @pytest.mark.asyncio
    async def test_handle_unsubscribe_message(self, manager, mock_websocket):
        """測試取消訂閱訊息處理"""
        # 建立連接並訂閱
        connection_id = await manager.connect(mock_websocket, "127.0.0.1", "test")
        
        # 先訂閱
        subscribe_data = {
            "server_ids": [1],
            "metric_types": ["cpu"],
            "alert_levels": ["ok"],
            "update_interval": 30
        }
        await manager._handle_subscribe(connection_id, subscribe_data)
        
        # 重置 mock
        mock_websocket.send_text.reset_mock()
        
        # 發送取消訂閱訊息
        unsubscribe_message = json.dumps({
            "type": "unsubscribe",
            "data": {},
            "message_id": "test_unsubscribe",
            "timestamp": datetime.now().isoformat()
        })
        
        await manager.handle_message(connection_id, unsubscribe_message)
        
        # 驗證訂閱被移除
        connection = manager.connections[connection_id]
        assert connection.subscription_filter is None
        assert 1 not in manager.server_subscribers or connection_id not in manager.server_subscribers[1]
        
        # 驗證取消訂閱確認訊息
        mock_websocket.send_text.assert_called_once()
        sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_message["type"] == "subscription_ack"
        assert sent_message["data"]["success"] is True
    
    @pytest.mark.asyncio
    async def test_broadcast_to_subscribers(self, manager, mock_websocket):
        """測試向訂閱者廣播"""
        # 建立連接並訂閱
        connection_id = await manager.connect(mock_websocket, "127.0.0.1", "test")
        
        subscribe_data = {
            "server_ids": [1],
            "metric_types": ["cpu"],
            "alert_levels": ["ok", "warning"],
            "update_interval": 30
        }
        await manager._handle_subscribe(connection_id, subscribe_data)
        
        # 重置 mock
        mock_websocket.send_text.reset_mock()
        
        # 建立測試訊息
        test_message = WebSocketMessage(
            message_type=MessageType.MONITORING_UPDATE,
            data={"server_id": 1, "cpu_usage": 45.2}
        )
        
        # 廣播訊息
        sent_count = await manager.broadcast_to_subscribers(1, test_message, "cpu", "ok")
        
        # 驗證廣播結果
        assert sent_count == 1
        mock_websocket.send_text.assert_called_once()
        
        sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_message["type"] == "monitoring_update"
        assert sent_message["data"]["server_id"] == 1
    
    @pytest.mark.asyncio
    async def test_broadcast_to_all(self, manager, mock_websocket):
        """測試向所有連接廣播"""
        # 建立多個連接
        connection_id1 = await manager.connect(mock_websocket, "127.0.0.1", "test1")
        
        mock_websocket2 = Mock()
        mock_websocket2.accept = AsyncMock()
        mock_websocket2.send_text = AsyncMock()
        connection_id2 = await manager.connect(mock_websocket2, "127.0.0.2", "test2")
        
        # 重置 mock
        mock_websocket.send_text.reset_mock()
        mock_websocket2.send_text.reset_mock()
        
        # 建立測試訊息
        test_message = WebSocketMessage(
            message_type=MessageType.HEARTBEAT,
            data={"timestamp": datetime.now().isoformat()}
        )
        
        # 廣播到所有連接
        sent_count = await manager.broadcast_to_all(test_message)
        
        # 驗證廣播結果
        assert sent_count == 2
        mock_websocket.send_text.assert_called_once()
        mock_websocket2.send_text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_queue_broadcast(self, manager):
        """測試廣播佇列"""
        test_message = WebSocketMessage(
            message_type=MessageType.STATUS_CHANGE,
            data={"server_id": 1, "status": "offline"}
        )
        
        # 測試佇列大小
        initial_queue_size = manager.broadcast_queue.qsize()
        
        # 加入廣播佇列
        await manager.queue_broadcast(test_message, server_id=1)
        
        # 驗證佇列大小增加
        assert manager.broadcast_queue.qsize() == initial_queue_size + 1
    
    def test_connection_stats(self, manager):
        """測試連接統計"""
        stats = manager.get_connection_stats()
        
        assert "total_connections" in stats
        assert "active_connections" in stats
        assert "messages_sent" in stats
        assert "messages_received" in stats
        assert "bytes_sent" in stats
        assert "bytes_received" in stats
        assert "uptime_seconds" in stats
        assert "server_subscribers" in stats
    
    def test_subscription_filter_matches(self):
        """測試訂閱過濾器匹配"""
        filter1 = SubscriptionFilter(
            server_ids={1, 2},
            metric_types={"cpu", "memory"},
            alert_levels={"warning", "critical"}
        )
        
        # 測試匹配情況
        assert filter1.matches(1, "cpu", "warning") is True
        assert filter1.matches(1, "cpu", "ok") is False
        assert filter1.matches(3, "cpu", "warning") is False
        assert filter1.matches(1, "disk", "warning") is False
        
        # 測試無限制的過濾器
        filter2 = SubscriptionFilter()
        assert filter2.matches(1, "cpu", "ok") is True
        assert filter2.matches(999, "network", "critical") is True


class TestWebSocketMessage:
    """WebSocket 訊息測試"""
    
    def test_message_creation(self):
        """測試訊息建立"""
        message = WebSocketMessage(
            message_type=MessageType.MONITORING_UPDATE,
            data={"server_id": 1, "cpu": 45.2}
        )
        
        assert message.message_type == MessageType.MONITORING_UPDATE
        assert message.data["server_id"] == 1
        assert message.message_id is not None
        assert message.timestamp is not None
    
    def test_message_to_dict(self):
        """測試訊息轉換為字典"""
        message = WebSocketMessage(
            message_type=MessageType.ERROR,
            data={"error": "test error"}
        )
        
        message_dict = message.to_dict()
        
        assert message_dict["type"] == "error"
        assert message_dict["data"]["error"] == "test error"
        assert "message_id" in message_dict
        assert "timestamp" in message_dict
    
    def test_message_to_json(self):
        """測試訊息轉換為 JSON"""
        message = WebSocketMessage(
            message_type=MessageType.PING,
            data={}
        )
        
        json_str = message.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["type"] == "ping"
        assert "message_id" in parsed
        assert "timestamp" in parsed
    
    def test_message_from_json_valid(self):
        """測試從有效 JSON 建立訊息"""
        json_data = {
            "type": "pong",
            "data": {"test": "value"},
            "message_id": "test_id",
            "timestamp": "2024-01-01T12:00:00"
        }
        
        message = WebSocketMessage.from_json(json.dumps(json_data))
        
        assert message.message_type == MessageType.PONG
        assert message.data["test"] == "value"
        assert message.message_id == "test_id"
    
    def test_message_from_json_invalid(self):
        """測試從無效 JSON 建立訊息"""
        invalid_json = "invalid json string"
        
        message = WebSocketMessage.from_json(invalid_json)
        
        assert message.message_type == MessageType.ERROR
        assert "error" in message.data
        assert "訊息格式錯誤" in message.data["error"]


class TestWebSocketConnection:
    """WebSocket 連接測試"""
    
    def test_connection_creation(self):
        """測試連接建立"""
        mock_websocket = Mock()
        
        connection = WebSocketConnection(
            connection_id="test_id",
            websocket=mock_websocket,
            client_ip="127.0.0.1",
            user_agent="test-agent"
        )
        
        assert connection.connection_id == "test_id"
        assert connection.websocket == mock_websocket
        assert connection.client_ip == "127.0.0.1"
        assert connection.user_agent == "test-agent"
        assert connection.state == ConnectionState.CONNECTING
        assert connection.message_count_sent == 0
        assert connection.message_count_received == 0
    
    def test_connection_is_alive(self):
        """測試連接存活檢查"""
        connection = WebSocketConnection(
            connection_id="test",
            websocket=Mock(),
            client_ip="127.0.0.1",
            user_agent="test"
        )
        
        # 新連接應該不算存活（因為沒有收到 pong）
        assert connection.is_alive() is False
        
        # 設定為已連接並更新 pong 時間
        connection.state = ConnectionState.CONNECTED
        connection.last_pong = datetime.now()
        assert connection.is_alive() is True
        
        # 超時的連接不算存活
        connection.last_pong = datetime.now() - timedelta(seconds=70)
        assert connection.is_alive() is False
    
    def test_connection_info(self):
        """測試連接資訊"""
        connection = WebSocketConnection(
            connection_id="test",
            websocket=Mock(),
            client_ip="127.0.0.1",
            user_agent="test-agent"
        )
        
        connection.state = ConnectionState.CONNECTED
        connection.message_count_sent = 10
        connection.message_count_received = 5
        
        info = connection.get_connection_info()
        
        assert info["connection_id"] == "test"
        assert info["client_ip"] == "127.0.0.1"
        assert info["user_agent"] == "test-agent"
        assert info["state"] == "connected"
        assert info["messages_sent"] == 10
        assert info["messages_received"] == 5
        assert "uptime_seconds" in info
        assert "subscription" in info


if __name__ == "__main__":
    # 執行測試
    pytest.main([__file__, "-v"])