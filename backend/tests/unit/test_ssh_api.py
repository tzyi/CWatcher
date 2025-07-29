"""
SSH API 端點單元測試

測試 SSH 管理相關的 API 端點功能
使用 FastAPI TestClient 進行 API 測試
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
import json

# 我們需要導入主應用程式來建立測試客戶端
from app.main import app
from app.services.ssh_manager import SSHConnectionConfig
from app.services.security_service import SecurityLevel


# 建立測試客戶端
client = TestClient(app)


class TestSSHConnectionTestAPI:
    """測試 SSH 連接測試 API"""
    
    @patch('app.api.v1.endpoints.ssh.ssh_manager.test_connection')
    @patch('app.api.v1.endpoints.ssh.check_connection_security')
    def test_test_connection_success(self, mock_security_check, mock_test_connection):
        """測試連接測試 API 成功"""
        # 設置模擬回應
        mock_security_check.return_value = (True, "")
        mock_test_connection.return_value = {
            "success": True,
            "message": "連接成功，認證方式: password",
            "duration": 1.23,
            "host": "192.168.1.100",
            "port": 22,
            "username": "admin"
        }
        
        # 準備請求資料
        request_data = {
            "host": "192.168.1.100",
            "port": 22,
            "username": "admin",
            "password": "secure-password",
            "timeout": 10
        }
        
        # 發送請求
        response = client.post("/api/v1/ssh/test-connection", json=request_data)
        
        # 驗證回應
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "連接成功" in data["message"]
        assert data["duration"] == 1.23
        assert data["host"] == "192.168.1.100"
        assert data["port"] == 22
        assert data["username"] == "admin"
        assert data["details"] is not None
    
    @patch('app.api.v1.endpoints.ssh.check_connection_security')
    def test_test_connection_security_denied(self, mock_security_check):
        """測試連接被安全策略拒絕"""
        mock_security_check.return_value = (False, "IP 不在白名單中")
        
        request_data = {
            "host": "192.168.1.100",
            "port": 22,
            "username": "admin",
            "password": "secure-password"
        }
        
        response = client.post("/api/v1/ssh/test-connection", json=request_data)
        
        assert response.status_code == 403
        data = response.json()
        assert "安全策略拒絕" in data["detail"]
        assert "IP 不在白名單中" in data["detail"]
    
    @patch('app.api.v1.endpoints.ssh.ssh_manager.test_connection')
    @patch('app.api.v1.endpoints.ssh.check_connection_security')
    def test_test_connection_failure(self, mock_security_check, mock_test_connection):
        """測試連接失敗"""
        mock_security_check.return_value = (True, "")
        mock_test_connection.return_value = {
            "success": False,
            "message": "連接失敗: Authentication failed",
            "duration": 2.5,
            "host": "192.168.1.100",
            "port": 22,
            "username": "admin"
        }
        
        request_data = {
            "host": "192.168.1.100",
            "port": 22,
            "username": "admin",
            "password": "wrong-password"
        }
        
        response = client.post("/api/v1/ssh/test-connection", json=request_data)
        
        assert response.status_code == 200  # API 正常，但連接失敗
        data = response.json()
        
        assert data["success"] is False
        assert "連接失敗" in data["message"]
        assert data["details"] is None
    
    def test_test_connection_invalid_request(self):
        """測試無效請求"""
        # 缺少必要欄位
        request_data = {
            "host": "192.168.1.100",
            # 缺少 username
            "password": "password"
        }
        
        response = client.post("/api/v1/ssh/test-connection", json=request_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_test_connection_invalid_port(self):
        """測試無效端口"""
        request_data = {
            "host": "192.168.1.100",
            "port": 99999,  # 超出範圍
            "username": "admin",
            "password": "password"
        }
        
        response = client.post("/api/v1/ssh/test-connection", json=request_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_test_connection_invalid_username(self):
        """測試無效使用者名稱"""
        request_data = {
            "host": "192.168.1.100",
            "port": 22,
            "username": "123invalid",  # 不能以數字開頭
            "password": "password"
        }
        
        response = client.post("/api/v1/ssh/test-connection", json=request_data)
        
        assert response.status_code == 422  # Validation error


class TestSSHCommandExecutionAPI:
    """測試 SSH 指令執行 API"""
    
    @patch('app.api.v1.endpoints.ssh.get_db')
    @patch('app.api.v1.endpoints.ssh.ssh_manager.execute_command')
    @patch('app.api.v1.endpoints.ssh.ssh_manager.decrypt_server_credentials')
    @patch('app.api.v1.endpoints.ssh.security_service.validate_command')
    async def test_execute_command_success(
        self, 
        mock_validate_command,
        mock_decrypt_credentials,
        mock_execute_command,
        mock_get_db
    ):
        """測試指令執行成功"""
        # 設置資料庫模擬
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db
        
        # 模擬伺服器查詢結果
        mock_server = Mock()
        mock_server.id = 1
        mock_server.name = "test-server"
        mock_server.ip_address = "192.168.1.100"
        mock_server.ssh_port = 22
        mock_server.username = "admin"
        mock_server.monitoring_enabled = True
        mock_server.password_encrypted = "encrypted-password"
        mock_server.private_key_encrypted = None
        mock_server.connection_timeout = 10
        mock_server.max_connections = 3
        
        # 設置資料庫查詢模擬
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_server
        mock_db.execute.return_value = mock_result
        
        # 設置服務模擬
        mock_validate_command.return_value = (True, "")
        mock_config = Mock(spec=SSHConnectionConfig)
        mock_decrypt_credentials.return_value = mock_config
        mock_execute_command.return_value = ("Hello World", "", 0)
        
        request_data = {
            "server_id": 1,
            "command": "echo 'Hello World'",
            "timeout": 30
        }
        
        response = client.post("/api/v1/ssh/servers/1/execute", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["stdout"] == "Hello World"
        assert data["stderr"] == ""
        assert data["exit_code"] == 0
        assert data["command"] == "echo 'Hello World'"
    
    @patch('app.api.v1.endpoints.ssh.get_db')
    async def test_execute_command_server_not_found(self, mock_get_db):
        """測試伺服器不存在"""
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db
        
        # 模擬伺服器不存在
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        request_data = {
            "server_id": 999,
            "command": "ls -la"
        }
        
        response = client.post("/api/v1/ssh/servers/999/execute", json=request_data)
        
        assert response.status_code == 404
        data = response.json()
        assert "伺服器不存在" in data["detail"]
    
    @patch('app.api.v1.endpoints.ssh.get_db')
    async def test_execute_command_monitoring_disabled(self, mock_get_db):
        """測試監控已停用的伺服器"""
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db
        
        # 模擬監控已停用的伺服器
        mock_server = Mock()
        mock_server.monitoring_enabled = False
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_server
        mock_db.execute.return_value = mock_result
        
        request_data = {
            "server_id": 1,
            "command": "ls -la"
        }
        
        response = client.post("/api/v1/ssh/servers/1/execute", json=request_data)
        
        assert response.status_code == 403
        data = response.json()
        assert "監控已停用" in data["detail"]
    
    @patch('app.api.v1.endpoints.ssh.get_db')
    @patch('app.api.v1.endpoints.ssh.security_service.validate_command')
    async def test_execute_command_security_blocked(self, mock_validate_command, mock_get_db):
        """測試指令被安全策略阻擋"""
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db
        
        # 模擬有效伺服器
        mock_server = Mock()
        mock_server.monitoring_enabled = True
        mock_server.username = "admin"
        mock_server.ip_address = "192.168.1.100"
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_server
        mock_db.execute.return_value = mock_result
        
        # 模擬危險指令
        mock_validate_command.return_value = (False, "指令包含危險模式: rm -rf /")
        
        request_data = {
            "server_id": 1,
            "command": "rm -rf /"
        }
        
        response = client.post("/api/v1/ssh/servers/1/execute", json=request_data)
        
        assert response.status_code == 403
        data = response.json()
        assert "安全策略拒絕" in data["detail"]
        assert "危險模式" in data["detail"]


class TestSSHConnectionStatusAPI:
    """測試 SSH 連接狀態 API"""
    
    @patch('app.api.v1.endpoints.ssh.get_db')
    @patch('app.api.v1.endpoints.ssh.ssh_manager.get_server_status')
    async def test_get_server_status_success(self, mock_get_server_status, mock_get_db):
        """測試獲取伺服器狀態成功"""
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db
        
        # 模擬伺服器資料
        mock_server = Mock()
        mock_server.id = 1
        mock_server.status = "online"
        mock_server.last_connected_at = None
        mock_server.ip_address = "192.168.1.100"
        mock_server.ssh_port = 22
        mock_server.username = "admin"
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_server
        mock_db.execute.return_value = mock_result
        
        # 模擬連接池狀態
        mock_get_server_status.return_value = {
            "total_connections": 1,
            "connected": 1,
            "max_connections": 3,
            "connections": []
        }
        
        response = client.get("/api/v1/ssh/servers/1/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["server_id"] == 1
        assert data["status"] == "online"
        assert data["last_connected"] is None
        assert "connection_pool" in data
    
    @patch('app.api.v1.endpoints.ssh.get_db')
    async def test_get_server_status_not_found(self, mock_get_db):
        """測試伺服器不存在"""
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        response = client.get("/api/v1/ssh/servers/999/status")
        
        assert response.status_code == 404
        data = response.json()
        assert "伺服器不存在" in data["detail"]


class TestSSHManagerStatisticsAPI:
    """測試 SSH 管理器統計 API"""
    
    @patch('app.api.v1.endpoints.ssh.ssh_manager.get_statistics')
    def test_get_ssh_manager_statistics(self, mock_get_statistics):
        """測試獲取 SSH 管理器統計"""
        mock_get_statistics.return_value = {
            "connection_pools": 2,
            "total_connections": 5,
            "active_connections": 3,
            "connection_stats": {
                "successful": 10,
                "failed": 2
            },
            "command_stats": {
                "executed": 50,
                "failed": 3
            },
            "avg_command_time": 0.85
        }
        
        response = client.get("/api/v1/ssh/manager/statistics")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["connection_pools"] == 2
        assert data["data"]["active_connections"] == 3
    
    @patch('app.api.v1.endpoints.ssh.ssh_manager.close_all_connections')
    def test_cleanup_ssh_connections(self, mock_close_all):
        """測試清理 SSH 連接"""
        response = client.post("/api/v1/ssh/manager/cleanup")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "清理" in data["message"]
        mock_close_all.assert_called_once()


class TestSecurityAPI:
    """測試安全相關 API"""
    
    @patch('app.api.v1.endpoints.ssh.security_service.get_security_summary')
    def test_get_security_summary(self, mock_get_summary):
        """測試獲取安全摘要"""
        mock_get_summary.return_value = {
            "total_events_24h": 15,
            "event_types": {
                "connection_success": 10,
                "connection_failure": 3,
                "suspicious_activity": 2
            },
            "severity_distribution": {
                "low": 10,
                "medium": 3,
                "high": 2
            },
            "blocked_ips": 1,
            "whitelist_size": {
                "ip": 5,
                "host": 2,
                "user": 3
            }
        }
        
        response = client.get("/api/v1/ssh/security/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["total_events_24h"] == 15
        assert data["data"]["blocked_ips"] == 1
    
    @patch('app.api.v1.endpoints.ssh.security_service.get_recent_events')
    def test_get_security_events(self, mock_get_events):
        """測試獲取安全事件"""
        mock_events = [
            {
                "event_type": "connection_success",
                "timestamp": "2024-01-01T10:00:00",
                "source_ip": "192.168.1.100",
                "target_host": "test-server",
                "username": "admin",
                "severity": "low",
                "details": {},
                "resolved": False
            }
        ]
        mock_get_events.return_value = mock_events
        
        response = client.get("/api/v1/ssh/security/events?limit=10&severity=low")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["count"] == 1
        assert len(data["data"]) == 1
        assert data["data"][0]["event_type"] == "connection_success"
    
    def test_get_security_events_invalid_severity(self):
        """測試無效嚴重程度"""
        response = client.get("/api/v1/ssh/security/events?severity=invalid")
        
        assert response.status_code == 400
        data = response.json()
        assert "無效的嚴重程度" in data["detail"]
    
    @patch('app.api.v1.endpoints.ssh.security_service.add_to_whitelist')
    def test_add_to_whitelist_success(self, mock_add_whitelist):
        """測試添加白名單成功"""
        mock_add_whitelist.return_value = True
        
        response = client.post(
            "/api/v1/ssh/security/whitelist?item_type=ip&item=192.168.1.100"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "成功添加到白名單" in data["message"]
        mock_add_whitelist.assert_called_once_with("ip", "192.168.1.100")
    
    def test_add_to_whitelist_invalid_type(self):
        """測試添加無效類型到白名單"""
        response = client.post(
            "/api/v1/ssh/security/whitelist?item_type=invalid&item=test"
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "無效的項目類型" in data["detail"]
    
    @patch('app.api.v1.endpoints.ssh.security_service.add_to_whitelist')
    def test_add_to_whitelist_failure(self, mock_add_whitelist):
        """測試添加白名單失敗"""
        mock_add_whitelist.return_value = False
        
        response = client.post(
            "/api/v1/ssh/security/whitelist?item_type=ip&item=invalid-ip"
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "添加白名單項目失敗" in data["detail"]
    
    @patch('app.api.v1.endpoints.ssh.security_service.remove_from_whitelist')
    def test_remove_from_whitelist_success(self, mock_remove_whitelist):
        """測試從白名單移除成功"""
        mock_remove_whitelist.return_value = True
        
        response = client.delete(
            "/api/v1/ssh/security/whitelist?item_type=ip&item=192.168.1.100"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "成功從白名單移除" in data["message"]
        mock_remove_whitelist.assert_called_once_with("ip", "192.168.1.100")


class TestAPIValidation:
    """測試 API 驗證"""
    
    def test_connection_test_request_validation(self):
        """測試連接測試請求驗證"""
        # 測試各種驗證情況
        invalid_requests = [
            # 缺少主機
            {"port": 22, "username": "admin", "password": "pass"},
            # 空主機
            {"host": "", "port": 22, "username": "admin", "password": "pass"},
            # 無效端口
            {"host": "test", "port": 0, "username": "admin", "password": "pass"},
            {"host": "test", "port": 99999, "username": "admin", "password": "pass"},
            # 缺少使用者名稱
            {"host": "test", "port": 22, "password": "pass"},
            # 空使用者名稱
            {"host": "test", "port": 22, "username": "", "password": "pass"},
            # 超時時間超出範圍
            {"host": "test", "port": 22, "username": "admin", "password": "pass", "timeout": 1},
            {"host": "test", "port": 22, "username": "admin", "password": "pass", "timeout": 999},
        ]
        
        for req in invalid_requests:
            response = client.post("/api/v1/ssh/test-connection", json=req)
            assert response.status_code == 422, f"Request should be invalid: {req}"
    
    def test_command_execution_request_validation(self):
        """測試指令執行請求驗證"""
        invalid_requests = [
            # 缺少指令
            {"server_id": 1},
            # 空指令
            {"server_id": 1, "command": ""},
            # 指令太長
            {"server_id": 1, "command": "x" * 1001},
            # 超時時間超出範圍
            {"server_id": 1, "command": "ls", "timeout": 1},
            {"server_id": 1, "command": "ls", "timeout": 999},
        ]
        
        for req in invalid_requests:
            response = client.post("/api/v1/ssh/servers/1/execute", json=req)
            assert response.status_code == 422, f"Request should be invalid: {req}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])