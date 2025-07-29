#!/usr/bin/env python3
"""
簡單的 WebSocket 測試執行器
在沒有 pytest 的環境中測試 WebSocket 管理器功能
"""

import asyncio
import json
import sys
import traceback
from datetime import datetime
from unittest.mock import Mock, AsyncMock

# 添加 app 目錄到 Python 路徑
sys.path.insert(0, '/home/cabie/cabie/01_project/CWatcher/backend')

try:
    from app.services.websocket_manager import (
        WebSocketManager, WebSocketConnection, WebSocketMessage, MessageType,
        ConnectionState, SubscriptionFilter
    )
except ImportError as e:
    print(f"❌ 無法導入 WebSocket 管理器: {e}")
    sys.exit(1)


class WebSocketTester:
    """WebSocket 測試器"""
    
    def __init__(self):
        self.test_count = 0
        self.passed_count = 0
        self.failed_count = 0
        self.results = []
    
    def assert_equal(self, actual, expected, message=""):
        """簡單的斷言函數"""
        if actual == expected:
            return True
        else:
            raise AssertionError(f"Expected {expected}, got {actual}. {message}")
    
    def assert_true(self, condition, message=""):
        """斷言條件為真"""
        if condition:
            return True
        else:
            raise AssertionError(f"Expected True, got {condition}. {message}")
    
    def assert_not_none(self, value, message=""):
        """斷言值不為 None"""
        if value is not None:
            return True
        else:
            raise AssertionError(f"Expected not None, got None. {message}")
    
    def assert_in(self, item, container, message=""):
        """斷言項目在容器中"""
        if item in container:
            return True
        else:
            raise AssertionError(f"Expected {item} in {container}. {message}")
    
    async def run_test(self, test_name, test_func):
        """執行單個測試"""
        self.test_count += 1
        print(f"🧪 執行測試: {test_name}")
        
        try:
            await test_func()
            self.passed_count += 1
            print(f"✅ 測試通過: {test_name}")
            self.results.append({"name": test_name, "status": "PASSED"})
        except Exception as e:
            self.failed_count += 1
            print(f"❌ 測試失敗: {test_name}")
            print(f"   錯誤: {str(e)}")
            print(f"   堆疊: {traceback.format_exc()}")
            self.results.append({"name": test_name, "status": "FAILED", "error": str(e)})
    
    def print_summary(self):
        """印出測試總結"""
        print("\n" + "="*60)
        print("🧪 測試總結")
        print("="*60)
        print(f"總測試數: {self.test_count}")
        print(f"通過數: {self.passed_count}")
        print(f"失敗數: {self.failed_count}")
        print(f"成功率: {(self.passed_count/self.test_count*100):.1f}%" if self.test_count > 0 else "0%")
        
        if self.failed_count > 0:
            print(f"\n❌ 失敗的測試:")
            for result in self.results:
                if result["status"] == "FAILED":
                    print(f"  - {result['name']}: {result.get('error', '未知錯誤')}")
        
        print("="*60)


async def test_websocket_manager_initialization():
    """測試 WebSocket 管理器初始化"""
    tester = WebSocketTester()
    
    async def test():
        manager = WebSocketManager()
        tester.assert_equal(manager.connections, {})
        tester.assert_equal(manager.server_subscribers, {})
        tester.assert_not_none(manager.broadcast_queue)
        tester.assert_not_none(manager.heartbeat_task)
        tester.assert_not_none(manager.cleanup_task)
        tester.assert_not_none(manager.broadcast_task)
    
    await tester.run_test("WebSocket 管理器初始化", test)
    return tester


async def test_websocket_connection():
    """測試 WebSocket 連接建立"""
    tester = WebSocketTester()
    
    async def test():
        manager = WebSocketManager()
        
        # 建立模擬 WebSocket
        mock_websocket = Mock()
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        mock_websocket.close = AsyncMock()
        
        client_ip = "127.0.0.1"
        user_agent = "test-agent"
        
        # 測試連接建立
        connection_id = await manager.connect(mock_websocket, client_ip, user_agent)
        
        # 驗證連接建立
        tester.assert_in(connection_id, manager.connections)
        connection = manager.connections[connection_id]
        tester.assert_equal(connection.websocket, mock_websocket)
        tester.assert_equal(connection.client_ip, client_ip)
        tester.assert_equal(connection.user_agent, user_agent)
        tester.assert_equal(connection.state, ConnectionState.CONNECTED)
        
        # 驗證統計更新
        tester.assert_equal(manager._stats["total_connections"], 1)
        tester.assert_equal(manager._stats["active_connections"], 1)
    
    await tester.run_test("WebSocket 連接建立", test)
    return tester


async def test_websocket_message_handling():
    """測試 WebSocket 訊息處理"""
    tester = WebSocketTester()
    
    async def test():
        manager = WebSocketManager()
        
        # 建立模擬連接
        mock_websocket = Mock()
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        mock_websocket.close = AsyncMock()
        
        connection_id = await manager.connect(mock_websocket, "127.0.0.1", "test")
        mock_websocket.send_text.reset_mock()
        
        # 測試 Ping 訊息
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
        tester.assert_equal(sent_message["type"], "pong")
    
    await tester.run_test("WebSocket 訊息處理", test)
    return tester


async def test_subscription_system():
    """測試訂閱系統"""
    tester = WebSocketTester()
    
    async def test():
        manager = WebSocketManager()
        
        # 建立模擬連接
        mock_websocket = Mock()
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        mock_websocket.close = AsyncMock()
        
        connection_id = await manager.connect(mock_websocket, "127.0.0.1", "test")
        mock_websocket.send_text.reset_mock()
        
        # 測試訂閱
        subscribe_data = {
            "server_ids": [1, 2],
            "metric_types": ["cpu", "memory"],
            "alert_levels": ["warning", "critical"],
            "update_interval": 30
        }
        
        await manager._handle_subscribe(connection_id, subscribe_data)
        
        # 驗證訂閱設定
        connection = manager.connections[connection_id]
        tester.assert_not_none(connection.subscription_filter)
        tester.assert_equal(connection.subscription_filter.server_ids, {1, 2})
        tester.assert_equal(connection.subscription_filter.metric_types, {"cpu", "memory"})
        tester.assert_equal(connection.subscription_filter.update_interval, 30)
        
        # 驗證伺服器訂閱者列表
        tester.assert_in(1, manager.server_subscribers)
        tester.assert_in(2, manager.server_subscribers)
        tester.assert_in(connection_id, manager.server_subscribers[1])
        tester.assert_in(connection_id, manager.server_subscribers[2])
    
    await tester.run_test("訂閱系統", test)
    return tester


async def test_broadcast_system():
    """測試廣播系統"""
    tester = WebSocketTester()
    
    async def test():
        manager = WebSocketManager()
        
        # 建立模擬連接
        mock_websocket = Mock()
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        mock_websocket.close = AsyncMock()
        
        connection_id = await manager.connect(mock_websocket, "127.0.0.1", "test")
        
        # 設定訂閱
        subscribe_data = {
            "server_ids": [1],
            "metric_types": ["cpu"],
            "alert_levels": ["ok", "warning"],
            "update_interval": 30
        }
        await manager._handle_subscribe(connection_id, subscribe_data)
        
        mock_websocket.send_text.reset_mock()
        
        # 測試廣播
        test_message = WebSocketMessage(
            message_type=MessageType.MONITORING_UPDATE,
            data={"server_id": 1, "cpu_usage": 45.2}
        )
        
        sent_count = await manager.broadcast_to_subscribers(1, test_message, "cpu", "ok")
        
        # 驗證廣播結果
        tester.assert_equal(sent_count, 1)
        mock_websocket.send_text.assert_called_once()
        
        sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
        tester.assert_equal(sent_message["type"], "monitoring_update")
        tester.assert_equal(sent_message["data"]["server_id"], 1)
    
    await tester.run_test("廣播系統", test)
    return tester


async def test_websocket_message_creation():
    """測試 WebSocket 訊息建立"""
    tester = WebSocketTester()
    
    async def test():
        # 測試訊息建立
        message = WebSocketMessage(
            message_type=MessageType.MONITORING_UPDATE,
            data={"server_id": 1, "cpu": 45.2}
        )
        
        tester.assert_equal(message.message_type, MessageType.MONITORING_UPDATE)
        tester.assert_equal(message.data["server_id"], 1)
        tester.assert_not_none(message.message_id)
        tester.assert_not_none(message.timestamp)
        
        # 測試轉換為字典
        message_dict = message.to_dict()
        tester.assert_equal(message_dict["type"], "monitoring_update")
        tester.assert_equal(message_dict["data"]["server_id"], 1)
        tester.assert_in("message_id", message_dict)
        tester.assert_in("timestamp", message_dict)
        
        # 測試轉換為 JSON
        json_str = message.to_json()
        parsed = json.loads(json_str)
        tester.assert_equal(parsed["type"], "monitoring_update")
        tester.assert_in("message_id", parsed)
        tester.assert_in("timestamp", parsed)
    
    await tester.run_test("WebSocket 訊息建立", test)
    return tester


async def test_subscription_filter():
    """測試訂閱過濾器"""
    tester = WebSocketTester()
    
    async def test():
        # 測試有限制的過濾器
        filter1 = SubscriptionFilter(
            server_ids={1, 2},
            metric_types={"cpu", "memory"},
            alert_levels={"warning", "critical"}
        )
        
        tester.assert_true(filter1.matches(1, "cpu", "warning"))
        tester.assert_true(filter1.matches(2, "memory", "critical"))
        tester.assert_true(filter1.matches(1, "cpu", "ok") is False)
        tester.assert_true(filter1.matches(3, "cpu", "warning") is False)
        tester.assert_true(filter1.matches(1, "disk", "warning") is False)
        
        # 測試無限制的過濾器
        filter2 = SubscriptionFilter()
        tester.assert_true(filter2.matches(1, "cpu", "ok"))
        tester.assert_true(filter2.matches(999, "network", "critical"))
    
    await tester.run_test("訂閱過濾器", test)
    return tester


async def main():
    """主測試函數"""
    print("🚀 開始 WebSocket 管理器測試")
    print("="*60)
    
    all_results = []
    
    # 執行所有測試
    tests = [
        test_websocket_manager_initialization,
        test_websocket_connection,
        test_websocket_message_handling,
        test_subscription_system,
        test_broadcast_system,
        test_websocket_message_creation,
        test_subscription_filter
    ]
    
    for test_func in tests:
        try:
            result = await test_func()
            all_results.append(result)
        except Exception as e:
            print(f"❌ 測試執行錯誤: {e}")
            print(f"   堆疊: {traceback.format_exc()}")
    
    # 統計總結果
    total_tests = sum(r.test_count for r in all_results)
    total_passed = sum(r.passed_count for r in all_results)
    total_failed = sum(r.failed_count for r in all_results)
    
    print("\n" + "="*60)
    print("🎯 整體測試總結")
    print("="*60)
    print(f"總測試數: {total_tests}")
    print(f"通過數: {total_passed}")
    print(f"失敗數: {total_failed}")
    print(f"成功率: {(total_passed/total_tests*100):.1f}%" if total_tests > 0 else "0%")
    
    if total_failed == 0:
        print("🎉 所有測試都通過了！")
    else:
        print(f"⚠️  有 {total_failed} 個測試失敗")
    
    print("="*60)
    
    return total_failed == 0


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  測試被用戶中斷")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 測試執行失敗: {e}")
        print(f"   堆疊: {traceback.format_exc()}")
        sys.exit(1)