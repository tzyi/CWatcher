"""
測試指令執行 API 端點

測試所有指令執行相關的 API 端點功能
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from models.server import Server
from schemas.command import (
    CommandExecuteRequest, PredefinedCommandRequest, SystemInfoRequest,
    CommandResult, ExecutionStatus, CommandType
)
from services.command_executor import command_executor
from services.system_collector import system_collector
from core.deps import get_db, get_current_server


# 建立測試客戶端
client = TestClient(app)


class TestCommandExecutionAPI:
    """測試指令執行 API"""
    
    def setup_method(self):
        """設置測試環境"""
        self.test_server = Server(
            id=1,
            name="Test Server",
            ip_address="192.168.1.100",
            ssh_port=22,
            username="testuser",
            is_active=True,
            password_encrypted="encrypted_password",
            connection_timeout=30
        )
    
    @patch('app.api.v1.endpoints.command.get_current_server')
    @patch('app.api.v1.endpoints.command.execute_custom_command')
    @patch('app.api.v1.endpoints.command.get_db')
    async def test_execute_custom_command_success(self, mock_get_db, mock_execute_command, mock_get_server):
        """測試成功執行自訂指令"""
        # 設置模擬
        mock_get_server.return_value = self.test_server
        mock_get_db.return_value = Mock(spec=Session)
        
        mock_result = CommandResult(
            command="uptime",
            command_type=CommandType.CUSTOM,
            status=ExecutionStatus.SUCCESS,
            stdout=" 16:30:01 up 10 days,  1:23,  2 users,  load average: 0.15, 0.10, 0.05",
            stderr="",
            exit_code=0,
            execution_time=0.25,
            timestamp=datetime.now()
        )
        mock_execute_command.return_value = mock_result
        
        # 準備請求數據
        request_data = {
            "command": "uptime",
            "command_type": "custom",
            "timeout": 30,
            "use_cache": True
        }
        
        # 發送請求
        response = client.post(
            "/api/v1/command/servers/1/execute",
            json=request_data
        )
        
        # 驗證回應
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "指令執行完成" in data["message"]
        assert data["result"]["command"] == "uptime"
        assert data["result"]["status"] == "success"
    
    @patch('app.api.v1.endpoints.command.get_current_server')
    @patch('app.api.v1.endpoints.command.get_db')
    def test_execute_custom_command_server_not_found(self, mock_get_db, mock_get_server):
        """測試伺服器不存在的情況"""
        mock_get_server.return_value = None
        mock_get_db.return_value = Mock(spec=Session)
        
        request_data = {
            "command": "uptime",
            "command_type": "custom"
        }
        
        response = client.post(
            "/api/v1/command/servers/999/execute",
            json=request_data
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "伺服器不存在" in data["detail"]
    
    @patch('app.api.v1.endpoints.command.get_current_server')
    @patch('app.api.v1.endpoints.command.get_db')
    def test_execute_custom_command_inactive_server(self, mock_get_db, mock_get_server):
        """測試未啟用的伺服器"""
        inactive_server = Server(
            id=1,
            name="Inactive Server",
            ip_address="192.168.1.100",
            ssh_port=22,
            username="testuser",
            is_active=False  # 未啟用
        )
        mock_get_server.return_value = inactive_server
        mock_get_db.return_value = Mock(spec=Session)
        
        request_data = {
            "command": "uptime",
            "command_type": "custom"
        }
        
        response = client.post(
            "/api/v1/command/servers/1/execute",
            json=request_data
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "伺服器未啟用" in data["detail"]
    
    def test_execute_custom_command_invalid_parameters(self):
        """測試無效的請求參數"""
        # 空指令
        response = client.post(
            "/api/v1/command/servers/1/execute",
            json={"command": "", "command_type": "custom"}
        )
        assert response.status_code == 422
        
        # 包含危險字符的指令
        response = client.post(
            "/api/v1/command/servers/1/execute",
            json={"command": "ls | rm -rf", "command_type": "custom"}
        )
        assert response.status_code == 422
        
        # 無效的超時時間
        response = client.post(
            "/api/v1/command/servers/1/execute",
            json={"command": "uptime", "timeout": 500}  # 超過最大值 300
        )
        assert response.status_code == 422
    
    @patch('app.api.v1.endpoints.command.get_current_server')
    @patch('app.api.v1.endpoints.command.execute_system_command')
    @patch('app.api.v1.endpoints.command.command_executor')
    @patch('app.api.v1.endpoints.command.get_db')
    async def test_execute_predefined_command_success(self, mock_get_db, mock_executor, mock_execute_command, mock_get_server):
        """測試成功執行預定義指令"""
        # 設置模擬
        mock_get_server.return_value = self.test_server
        mock_get_db.return_value = Mock(spec=Session)
        
        # 模擬預定義指令存在
        mock_executor.get_predefined_commands.return_value = {
            "uptime": {
                "name": "uptime",
                "command": "uptime",
                "description": "獲取系統運行時間"
            }
        }
        
        mock_result = CommandResult(
            command="uptime",
            command_type=CommandType.SYSTEM_INFO,
            status=ExecutionStatus.SUCCESS,
            stdout=" 16:30:01 up 10 days,  1:23,  2 users,  load average: 0.15, 0.10, 0.05",
            timestamp=datetime.now(),
            parsed_data={"uptime_string": "10 days,  1:23", "load_average": {"1min": 0.15}}
        )
        mock_execute_command.return_value = mock_result
        
        request_data = {
            "command_name": "uptime",
            "use_cache": True
        }
        
        response = client.post(
            "/api/v1/command/servers/1/execute/predefined",
            json=request_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "預定義指令執行完成" in data["message"]
        assert data["result"]["parsed_data"] is not None
    
    @patch('app.api.v1.endpoints.command.get_current_server')
    @patch('app.api.v1.endpoints.command.command_executor')
    @patch('app.api.v1.endpoints.command.get_db')
    def test_execute_predefined_command_not_found(self, mock_get_db, mock_executor, mock_get_server):
        """測試執行不存在的預定義指令"""
        mock_get_server.return_value = self.test_server
        mock_get_db.return_value = Mock(spec=Session)
        
        # 模擬預定義指令不存在
        mock_executor.get_predefined_commands.return_value = {}
        
        request_data = {
            "command_name": "nonexistent_command",
            "use_cache": True
        }
        
        response = client.post(
            "/api/v1/command/servers/1/execute/predefined",
            json=request_data
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "預定義指令不存在" in data["detail"]
    
    def test_execute_predefined_command_invalid_name(self):
        """測試無效的預定義指令名稱"""
        # 包含特殊字符的指令名稱
        response = client.post(
            "/api/v1/command/servers/1/execute/predefined",
            json={"command_name": "invalid-command-name!", "use_cache": True}
        )
        assert response.status_code == 422
        
        # 空指令名稱
        response = client.post(
            "/api/v1/command/servers/1/execute/predefined",
            json={"command_name": "", "use_cache": True}
        )
        assert response.status_code == 422


class TestPredefinedCommandsAPI:
    """測試預定義指令 API"""
    
    @patch('app.api.v1.endpoints.command.command_executor')
    def test_get_predefined_commands_success(self, mock_executor):
        """測試成功獲取預定義指令列表"""
        mock_commands = {
            "uptime": {
                "name": "uptime",
                "command": "uptime",
                "command_type": "system_info",
                "description": "獲取系統運行時間和負載",
                "timeout": 10,
                "cache_ttl": 60,
                "security_level": "safe"
            },
            "hostname": {
                "name": "hostname",
                "command": "hostname",
                "command_type": "system_info",
                "description": "獲取主機名",
                "timeout": 5,
                "cache_ttl": 3600,
                "security_level": "safe"
            }
        }
        mock_executor.get_predefined_commands.return_value = mock_commands
        
        response = client.get("/api/v1/command/commands/predefined")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_count"] == 2
        assert "uptime" in data["commands"]
        assert "hostname" in data["commands"]
        assert data["commands"]["uptime"]["description"] == "獲取系統運行時間和負載"


class TestSystemInfoAPI:
    """測試系統資訊收集 API"""
    
    def setup_method(self):
        """設置測試環境"""
        self.test_server = Server(
            id=1,
            name="Test Server",
            ip_address="192.168.1.100",
            ssh_port=22,
            username="testuser",
            is_active=True,
            password_encrypted="encrypted_password",
            connection_timeout=30
        )
    
    @patch('app.api.v1.endpoints.command.get_current_server')
    @patch('app.api.v1.endpoints.command.collect_server_system_info')
    @patch('app.api.v1.endpoints.command.get_db')
    async def test_collect_system_info_success(self, mock_get_db, mock_collect_info, mock_get_server):
        """測試成功收集系統資訊"""
        from services.system_collector import SystemInfo, SystemInfoType
        
        mock_get_server.return_value = self.test_server
        mock_get_db.return_value = Mock(spec=Session)
        
        # 模擬系統資訊收集結果
        mock_system_info = {
            SystemInfoType.HARDWARE: SystemInfo(
                info_type=SystemInfoType.HARDWARE,
                data={
                    "collection_status": "success",
                    "cpu": {"core_count": 4, "cpu_model": "Intel Core i5"},
                    "memory": {"total": 8192, "unit": "MB"}
                },
                collection_time=1.5,
                timestamp=datetime.now()
            ),
            SystemInfoType.OPERATING_SYSTEM: SystemInfo(
                info_type=SystemInfoType.OPERATING_SYSTEM,
                data={
                    "collection_status": "success",
                    "hostname": "test-server",
                    "os_release": {"name": "Ubuntu", "version": "20.04"}
                },
                collection_time=0.8,
                timestamp=datetime.now()
            )
        }
        mock_collect_info.return_value = mock_system_info
        
        request_data = {
            "include_details": True,
            "use_cache": True
        }
        
        response = client.post(
            "/api/v1/command/servers/1/system-info",
            json=request_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "系統資訊收集完成" in data["message"]
        assert data["data"] is not None
        assert data["collection_time"] is not None
    
    @patch('app.api.v1.endpoints.command.get_current_server')
    @patch('app.api.v1.endpoints.command.collect_server_basic_info')
    @patch('app.api.v1.endpoints.command.get_db')
    async def test_get_basic_system_info_success(self, mock_get_db, mock_collect_basic, mock_get_server):
        """測試成功獲取基本系統資訊"""
        mock_get_server.return_value = self.test_server
        mock_get_db.return_value = Mock(spec=Session)
        
        # 模擬基本資訊收集結果
        mock_basic_info = {
            "hostname": {"status": "success", "data": "test-server"},
            "uptime": {"status": "success", "data": {"uptime_string": "1 day"}},
            "os_info": {"status": "success", "data": "Ubuntu 20.04"},
            "memory": {"status": "success", "data": {"total": 8192, "unit": "MB"}},
            "disk": {"status": "success", "data": {"filesystems": []}}
        }
        mock_collect_basic.return_value = mock_basic_info
        
        response = client.get("/api/v1/command/servers/1/system-info/basic?use_cache=true")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "基本系統資訊收集完成" in data["message"]
        assert data["data"]["hostname"]["data"] == "test-server"
    
    def test_collect_system_info_invalid_server_id(self):
        """測試無效的伺服器 ID"""
        request_data = {
            "include_details": True,
            "use_cache": True
        }
        
        # 負數 ID
        response = client.post(
            "/api/v1/command/servers/-1/system-info",
            json=request_data
        )
        assert response.status_code == 422
        
        # 零 ID
        response = client.post(
            "/api/v1/command/servers/0/system-info",
            json=request_data
        )
        assert response.status_code == 422


class TestStatisticsAPI:
    """測試統計資訊 API"""
    
    @patch('app.api.v1.endpoints.command.command_executor')
    def test_get_command_statistics_success(self, mock_executor):
        """測試成功獲取指令執行統計"""
        mock_stats = {
            "total_executions": 150,
            "success_rate": 95.5,
            "cache_hit_rate": 65.2,
            "statistics": {
                "success": 143,
                "failed": 5,
                "timeout": 2,
                "cache_hit": 98
            },
            "cache_size": 25,
            "predefined_commands": 12
        }
        mock_executor.get_statistics.return_value = mock_stats
        
        response = client.get("/api/v1/command/statistics")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["statistics"]["total_executions"] == 150
        assert data["statistics"]["success_rate"] == 95.5
        assert data["statistics"]["cache_hit_rate"] == 65.2
    
    @patch('app.api.v1.endpoints.command.command_executor')
    def test_clear_command_cache_success(self, mock_executor):
        """測試成功清理指令快取"""
        mock_executor.clear_cache.return_value = None
        
        response = client.delete("/api/v1/command/cache")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "指令快取已清理" in data["message"]


class TestConnectionTestAPI:
    """測試連接測試 API"""
    
    def setup_method(self):
        """設置測試環境"""
        self.test_server = Server(
            id=1,
            name="Test Server",
            ip_address="192.168.1.100",
            ssh_port=22,
            username="testuser",
            is_active=True,
            password_encrypted="encrypted_password",
            connection_timeout=30
        )
    
    @patch('app.api.v1.endpoints.command.get_current_server')
    @patch('app.api.v1.endpoints.command.ssh_manager')
    @patch('app.api.v1.endpoints.command.get_db')
    def test_test_server_connection_success(self, mock_get_db, mock_ssh_manager, mock_get_server):
        """測試成功的伺服器連接測試"""
        mock_get_server.return_value = self.test_server
        mock_get_db.return_value = Mock(spec=Session)
        
        # 模擬連接測試結果
        mock_test_result = {
            "success": True,
            "message": "連接成功，認證方式: password",
            "host": "192.168.1.100",
            "port": 22,
            "username": "testuser",
            "duration": 0.25
        }
        mock_ssh_manager.decrypt_server_credentials.return_value = Mock()
        mock_ssh_manager.test_connection.return_value = mock_test_result
        
        response = client.get("/api/v1/command/servers/1/connection/test")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "連接成功，認證方式: password"
        assert data["connection_info"]["host"] == "192.168.1.100"
        assert data["connection_info"]["duration"] == 0.25
    
    @patch('app.api.v1.endpoints.command.get_current_server')
    @patch('app.api.v1.endpoints.command.ssh_manager')
    @patch('app.api.v1.endpoints.command.get_db')
    def test_test_server_connection_failure(self, mock_get_db, mock_ssh_manager, mock_get_server):
        """測試失敗的伺服器連接測試"""
        mock_get_server.return_value = self.test_server
        mock_get_db.return_value = Mock(spec=Session)
        
        # 模擬連接測試失敗
        mock_test_result = {
            "success": False,
            "message": "連接失敗: Authentication failed",
            "host": "192.168.1.100",
            "port": 22,
            "username": "testuser",
            "duration": 5.0
        }
        mock_ssh_manager.decrypt_server_credentials.return_value = Mock()
        mock_ssh_manager.test_connection.return_value = mock_test_result
        
        response = client.get("/api/v1/command/servers/1/connection/test")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Authentication failed" in data["message"]


class TestErrorHandling:
    """測試錯誤處理"""
    
    @patch('app.api.v1.endpoints.command.get_current_server')
    @patch('app.api.v1.endpoints.command.execute_custom_command')
    @patch('app.api.v1.endpoints.command.get_db')
    def test_security_error_handling(self, mock_get_db, mock_execute_command, mock_get_server):
        """測試安全錯誤處理"""
        from utils.exceptions import SecurityError
        
        mock_get_server.return_value = Server(id=1, is_active=True)
        mock_get_db.return_value = Mock(spec=Session)
        
        # 模擬安全錯誤
        mock_execute_command.side_effect = SecurityError("危險指令被阻止")
        
        request_data = {
            "command": "rm -rf /",
            "command_type": "custom"
        }
        
        response = client.post(
            "/api/v1/command/servers/1/execute",
            json=request_data
        )
        
        assert response.status_code == 403
        data = response.json()
        assert "安全檢查失敗" in data["detail"]
    
    @patch('app.api.v1.endpoints.command.get_current_server')
    @patch('app.api.v1.endpoints.command.execute_custom_command')
    @patch('app.api.v1.endpoints.command.get_db')
    def test_ssh_connection_error_handling(self, mock_get_db, mock_execute_command, mock_get_server):
        """測試 SSH 連接錯誤處理"""
        from utils.exceptions import SSHConnectionError
        
        mock_get_server.return_value = Server(id=1, is_active=True)
        mock_get_db.return_value = Mock(spec=Session)
        
        # 模擬 SSH 連接錯誤
        mock_execute_command.side_effect = SSHConnectionError("連接超時")
        
        request_data = {
            "command": "uptime",
            "command_type": "custom"
        }
        
        response = client.post(
            "/api/v1/command/servers/1/execute",
            json=request_data
        )
        
        assert response.status_code == 500
        data = response.json()
        assert "SSH 連接失敗" in data["detail"]
    
    def test_validation_error_handling(self):
        """測試輸入驗證錯誤處理"""
        # 測試缺少必需欄位
        response = client.post(
            "/api/v1/command/servers/1/execute",
            json={}  # 缺少 command 欄位
        )
        assert response.status_code == 422
        
        # 測試無效的 JSON
        response = client.post(
            "/api/v1/command/servers/1/execute",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422


# 整合測試
class TestCommandAPIIntegration:
    """指令 API 整合測試"""
    
    @pytest.mark.asyncio
    async def test_full_command_execution_workflow(self):
        """測試完整的指令執行工作流程"""
        # 這個測試需要完整的應用程式設置，通常在整合測試中運行
        pass
    
    @pytest.mark.asyncio
    async def test_concurrent_api_requests(self):
        """測試並發 API 請求"""
        # 測試多個同時的 API 請求
        pass
    
    @pytest.mark.asyncio
    async def test_api_performance(self):
        """測試 API 性能"""
        # 測試 API 回應時間和資源使用
        pass


if __name__ == "__main__":
    # 執行測試
    pytest.main([__file__, "-v"])