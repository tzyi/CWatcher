"""
SSH 管理器單元測試

測試 SSH 連接管理、連接池、認證和安全功能
使用 Mock 避免實際 SSH 連接
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import paramiko

from services.ssh_manager import (
    SSHManager, SSHConnectionConfig, ConnectionInfo, ConnectionStatus,
    SSHConnectionPool, AuthType
)
from services.auth_service import AuthService
from utils.encryption import AESGCMEncryption


class TestSSHConnectionConfig:
    """測試 SSH 連接配置"""
    
    def test_basic_config_creation(self):
        """測試基本配置建立"""
        config = SSHConnectionConfig(
            host="192.168.1.100",
            port=22,
            username="admin"
        )
        
        assert config.host == "192.168.1.100"
        assert config.port == 22
        assert config.username == "admin"
        assert config.timeout == 10
        assert config.max_connections == 3
    
    def test_config_with_password(self):
        """測試密碼認證配置"""
        config = SSHConnectionConfig(
            host="test-server",
            username="user",
            password="secure-password"
        )
        
        assert config.password == "secure-password"
        assert config.private_key is None
    
    def test_config_with_key(self):
        """測試金鑰認證配置"""
        private_key = "-----BEGIN RSA PRIVATE KEY-----\ntest-key\n-----END RSA PRIVATE KEY-----"
        
        config = SSHConnectionConfig(
            host="test-server",
            username="user",
            private_key=private_key,
            key_passphrase="passphrase"
        )
        
        assert config.private_key == private_key
        assert config.key_passphrase == "passphrase"
        assert config.password is None


class TestSSHConnectionPool:
    """測試 SSH 連接池"""
    
    def setup_method(self):
        """測試前設置"""
        self.pool = SSHConnectionPool(max_connections=3)
    
    def test_pool_initialization(self):
        """測試連接池初始化"""
        assert self.pool.max_connections == 3
        assert len(self.pool.connections) == 0
    
    def test_add_connection(self):
        """測試添加連接"""
        config = SSHConnectionConfig(host="test", username="user")
        conn_info = ConnectionInfo(config=config)
        conn_info.status = ConnectionStatus.CONNECTED
        conn_info.client = Mock()
        
        result = self.pool.add_connection(conn_info)
        
        assert result is True
        assert len(self.pool.connections) == 1
        assert self.pool.connections[0] == conn_info
    
    def test_max_connections_limit(self):
        """測試最大連接限制"""
        config = SSHConnectionConfig(host="test", username="user")
        
        # 添加達到最大數量的連接
        for i in range(4):  # 超過最大限制
            conn_info = ConnectionInfo(config=config)
            conn_info.status = ConnectionStatus.CONNECTED
            conn_info.client = Mock()
            # 設定不同的時間戳以測試最舊連接移除
            conn_info.last_used = datetime.now() - timedelta(seconds=i)
            self.pool.add_connection(conn_info)
        
        # 應該只保留最大數量的連接
        assert len(self.pool.connections) == 3
    
    def test_get_available_connection(self):
        """測試獲取可用連接"""
        config = SSHConnectionConfig(host="test", username="user")
        conn_info = ConnectionInfo(config=config)
        conn_info.status = ConnectionStatus.CONNECTED
        
        # 模擬有效的 SSH 客戶端
        mock_client = Mock()
        mock_client.exec_command.return_value = (Mock(), Mock(), Mock())
        conn_info.client = mock_client
        
        self.pool.add_connection(conn_info)
        
        available = self.pool.get_available_connection()
        assert available == conn_info
    
    def test_get_status(self):
        """測試獲取連接池狀態"""
        config = SSHConnectionConfig(host="test", username="user")
        
        # 添加一個連接
        conn_info = ConnectionInfo(config=config)
        conn_info.status = ConnectionStatus.CONNECTED
        self.pool.add_connection(conn_info)
        
        status = self.pool.get_status()
        
        assert status["total_connections"] == 1
        assert status["connected"] == 1
        assert status["max_connections"] == 3
        assert len(status["connections"]) == 1


class TestSSHManager:
    """測試 SSH 管理器"""
    
    def setup_method(self):
        """測試前設置"""
        self.encryption = AESGCMEncryption()
        self.manager = SSHManager(encryption=self.encryption)
    
    def test_manager_initialization(self):
        """測試管理器初始化"""
        assert self.manager.encryption is not None
        assert len(self.manager.connection_pools) == 0
        assert len(self.manager.connection_stats) == 0
    
    def test_get_server_key(self):
        """測試伺服器唯一標識生成"""
        key = self.manager._get_server_key("192.168.1.100", 22, "admin")
        assert key == "admin@192.168.1.100:22"
    
    def test_get_connection_pool(self):
        """測試獲取連接池"""
        config = SSHConnectionConfig(
            host="test-server",
            port=22,
            username="admin",
            max_connections=5
        )
        
        pool = self.manager._get_connection_pool(config)
        
        assert pool is not None
        assert pool.max_connections == 5
        assert "admin@test-server:22" in self.manager.connection_pools
    
    @patch('paramiko.SSHClient')
    def test_create_ssh_client(self, mock_ssh_client_class):
        """測試 SSH 客戶端建立"""
        mock_client = Mock()
        mock_ssh_client_class.return_value = mock_client
        
        config = SSHConnectionConfig(
            host="test-server",
            username="admin",
            auto_add_policy=True
        )
        
        client = self.manager._create_ssh_client(config)
        
        assert client == mock_client
        mock_client.set_missing_host_key_policy.assert_called_once()
    
    @patch('paramiko.SSHClient')
    def test_authenticate_with_password(self, mock_ssh_client_class):
        """測試密碼認證"""
        mock_client = Mock()
        mock_ssh_client_class.return_value = mock_client
        
        config = SSHConnectionConfig(
            host="test-server",
            username="admin",
            password="secure-password"
        )
        
        auth_type = self.manager._authenticate(mock_client, config)
        
        assert auth_type == AuthType.PASSWORD
        mock_client.connect.assert_called_once_with(
            hostname="test-server",
            port=22,
            username="admin",
            password="secure-password",
            timeout=10
        )
    
    @patch('paramiko.RSAKey.from_private_key')
    @patch('paramiko.SSHClient')
    def test_authenticate_with_key(self, mock_ssh_client_class, mock_rsa_key):
        """測試金鑰認證"""
        mock_client = Mock()
        mock_ssh_client_class.return_value = mock_client
        
        mock_key = Mock()
        mock_rsa_key.return_value = mock_key
        
        private_key = "-----BEGIN RSA PRIVATE KEY-----\ntest-key\n-----END RSA PRIVATE KEY-----"
        config = SSHConnectionConfig(
            host="test-server",
            username="admin",
            private_key=private_key
        )
        
        auth_type = self.manager._authenticate(mock_client, config)
        
        assert auth_type == AuthType.KEY
        mock_client.connect.assert_called_once_with(
            hostname="test-server",
            port=22,
            username="admin",
            pkey=mock_key,
            timeout=10
        )
    
    @pytest.mark.asyncio
    @patch('app.services.ssh_manager.SSHManager._authenticate')
    @patch('app.services.ssh_manager.SSHManager._create_ssh_client')
    async def test_connect_success(self, mock_create_client, mock_authenticate):
        """測試成功連接"""
        # 設置模擬
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        mock_authenticate.return_value = AuthType.PASSWORD
        
        # 模擬測試指令執行
        mock_stdin = Mock()
        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_stdout.read.return_value = b"connection_test"
        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        
        config = SSHConnectionConfig(
            host="test-server",
            username="admin",
            password="password"
        )
        
        conn_info = await self.manager.connect(config)
        
        assert conn_info.status == ConnectionStatus.CONNECTED
        assert conn_info.client == mock_client
        assert conn_info.retry_count == 0
        assert conn_info.error_message is None
    
    @pytest.mark.asyncio
    @patch('app.services.ssh_manager.SSHManager._authenticate')
    @patch('app.services.ssh_manager.SSHManager._create_ssh_client')
    async def test_connect_failure_with_retry(self, mock_create_client, mock_authenticate):
        """測試連接失敗重試"""
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        mock_authenticate.side_effect = paramiko.AuthenticationException("Auth failed")
        
        config = SSHConnectionConfig(
            host="test-server",
            username="admin",
            password="wrong-password"
        )
        
        with pytest.raises(paramiko.SSHException) as exc_info:
            await self.manager.connect(config, retry_count=2)
        
        assert "連接失敗，已重試 2 次" in str(exc_info.value)
        assert mock_authenticate.call_count == 3  # 原始嘗試 + 2 次重試
    
    @pytest.mark.asyncio
    @patch('app.services.ssh_manager.SSHManager.connect')
    async def test_execute_command_success(self, mock_connect):
        """測試指令執行成功"""
        # 設置模擬連接
        mock_client = Mock()
        mock_conn_info = Mock()
        mock_conn_info.client = mock_client
        mock_connect.return_value = mock_conn_info
        
        # 設置模擬指令執行
        mock_stdin = Mock()
        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        
        mock_stdout.read.return_value = b"Hello World"
        mock_stderr.read.return_value = b""
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 0
        
        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        
        config = SSHConnectionConfig(host="test", username="user")
        
        stdout, stderr, exit_code = await self.manager.execute_command(
            config, "echo 'Hello World'"
        )
        
        assert stdout == "Hello World"
        assert stderr == ""
        assert exit_code == 0
        mock_client.exec_command.assert_called_once_with("echo 'Hello World'", timeout=30)
    
    def test_test_connection_success(self):
        """測試連接測試成功"""
        with patch.object(self.manager, '_create_ssh_client') as mock_create_client, \
             patch.object(self.manager, '_authenticate') as mock_authenticate:
            
            mock_client = Mock()
            mock_create_client.return_value = mock_client
            mock_authenticate.return_value = AuthType.PASSWORD
            
            # 模擬測試指令
            mock_stdin = Mock()
            mock_stdout = Mock()
            mock_stderr = Mock()
            mock_stdout.read.return_value = b"test"
            mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
            
            config = SSHConnectionConfig(
                host="test-server",
                username="admin",
                password="password"
            )
            
            result = self.manager.test_connection(config)
            
            assert result["success"] is True
            assert "連接成功" in result["message"]
            assert result["host"] == "test-server"
            assert result["port"] == 22
            assert result["username"] == "admin"
            assert result["duration"] > 0
    
    def test_test_connection_failure(self):
        """測試連接測試失敗"""
        with patch.object(self.manager, '_create_ssh_client') as mock_create_client, \
             patch.object(self.manager, '_authenticate') as mock_authenticate:
            
            mock_create_client.side_effect = paramiko.SSHException("Connection failed")
            
            config = SSHConnectionConfig(
                host="invalid-server",
                username="admin",
                password="password"
            )
            
            result = self.manager.test_connection(config)
            
            assert result["success"] is False
            assert "連接失敗" in result["message"]
            assert result["duration"] > 0
    
    def test_decrypt_server_credentials(self):
        """測試解密伺服器憑證"""
        # 準備加密資料
        password = "secure-password"
        encrypted_password = self.encryption.encrypt(password)
        
        server_data = {
            "ip_address": "192.168.1.100",
            "ssh_port": 22,
            "username": "admin",
            "password_encrypted": encrypted_password,
            "connection_timeout": 15,
            "max_connections": 5
        }
        
        config = self.manager.decrypt_server_credentials(server_data)
        
        assert config.host == "192.168.1.100"
        assert config.port == 22
        assert config.username == "admin"
        assert config.password == password
        assert config.timeout == 15
        assert config.max_connections == 5
    
    def test_get_statistics(self):
        """測試獲取統計資訊"""
        # 添加一些統計數據
        self.manager.connection_stats["successful"] = 10
        self.manager.connection_stats["failed"] = 2
        self.manager.command_stats["executed"] = 50
        self.manager.command_stats["total_time"] = 25.5
        
        stats = self.manager.get_statistics()
        
        assert stats["connection_pools"] == 0
        assert stats["total_connections"] == 0
        assert stats["active_connections"] == 0
        assert stats["connection_stats"]["successful"] == 10
        assert stats["connection_stats"]["failed"] == 2
        assert stats["command_stats"]["executed"] == 50
        assert stats["avg_command_time"] == 0.51  # 25.5 / 50
    
    def test_close_all_connections(self):
        """測試關閉所有連接"""
        # 建立一些連接池
        config1 = SSHConnectionConfig(host="server1", username="user1")
        config2 = SSHConnectionConfig(host="server2", username="user2")
        
        pool1 = self.manager._get_connection_pool(config1)
        pool2 = self.manager._get_connection_pool(config2)
        
        assert len(self.manager.connection_pools) == 2
        
        with patch.object(pool1, 'close_all') as mock_close1, \
             patch.object(pool2, 'close_all') as mock_close2:
            
            self.manager.close_all_connections()
            
            mock_close1.assert_called_once()
            mock_close2.assert_called_once()
            assert len(self.manager.connection_pools) == 0


# 便利函數測試
class TestSSHManagerHelpers:
    """測試 SSH 管理器便利函數"""
    
    @pytest.mark.asyncio
    @patch('app.services.ssh_manager.ssh_manager.test_connection')
    async def test_test_ssh_connection(self, mock_test):
        """測試 SSH 連接測試便利函數"""
        from services.ssh_manager import test_ssh_connection
        
        mock_test.return_value = {
            "success": True,
            "message": "連接成功",
            "duration": 1.23
        }
        
        server_data = {
            "ip_address": "192.168.1.100",
            "ssh_port": 22,
            "username": "admin",
            "password_encrypted": "encrypted-password"
        }
        
        with patch('app.services.ssh_manager.ssh_manager.decrypt_server_credentials') as mock_decrypt:
            mock_config = Mock()
            mock_decrypt.return_value = mock_config
            
            result = await test_ssh_connection(server_data)
            
            assert result["success"] is True
            mock_test.assert_called_once_with(mock_config)
    
    @pytest.mark.asyncio
    @patch('app.services.ssh_manager.ssh_manager.execute_command')
    async def test_execute_ssh_command(self, mock_execute):
        """測試 SSH 指令執行便利函數"""
        from services.ssh_manager import execute_ssh_command
        
        mock_execute.return_value = ("output", "", 0)
        
        server_data = {
            "ip_address": "192.168.1.100",
            "ssh_port": 22,
            "username": "admin",
            "password_encrypted": "encrypted-password"
        }
        
        with patch('app.services.ssh_manager.ssh_manager.decrypt_server_credentials') as mock_decrypt:
            mock_config = Mock()
            mock_decrypt.return_value = mock_config
            
            stdout, stderr, exit_code = await execute_ssh_command(
                server_data, "ls -la"
            )
            
            assert stdout == "output"
            assert stderr == ""
            assert exit_code == 0
            mock_execute.assert_called_once_with(mock_config, "ls -la", None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])