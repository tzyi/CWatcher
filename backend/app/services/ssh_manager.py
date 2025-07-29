"""
CWatcher SSH 連接管理器

提供穩定、安全的 SSH 連接管理功能
支援連接池、重試機制、超時處理和多種認證方式
"""

import asyncio
import io
import logging
import time
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import paramiko
from paramiko import SSHClient, SSHException, AuthenticationException
import socket
import threading
from enum import Enum
from collections import defaultdict

from core.config import settings
from utils.encryption import AESGCMEncryption, EncryptionError


# 設定日誌
logger = logging.getLogger(__name__)


class ConnectionStatus(Enum):
    """連接狀態枚舉"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    TIMEOUT = "timeout"


class AuthType(Enum):
    """認證類型枚舉"""
    PASSWORD = "password"
    KEY = "key"
    KEY_WITH_PASSPHRASE = "key_with_passphrase"


@dataclass
class SSHConnectionConfig:
    """SSH 連接配置"""
    host: str
    port: int = 22
    username: str = ""
    password: Optional[str] = None
    private_key: Optional[str] = None
    key_passphrase: Optional[str] = None
    timeout: int = 10
    max_connections: int = 3
    auto_add_policy: bool = True


@dataclass
class ConnectionInfo:
    """連接資訊"""
    config: SSHConnectionConfig
    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    client: Optional[SSHClient] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None
    retry_count: int = 0


class SSHConnectionPool:
    """SSH 連接池管理器"""
    
    def __init__(self, max_connections: int = 3):
        self.max_connections = max_connections
        self.connections: List[ConnectionInfo] = []
        self.lock = threading.Lock()
    
    def get_available_connection(self) -> Optional[ConnectionInfo]:
        """獲取可用連接"""
        with self.lock:
            for conn in self.connections:
                if conn.status == ConnectionStatus.CONNECTED and conn.client:
                    # 檢查連接是否仍然有效
                    try:
                        conn.client.exec_command("echo test", timeout=5)
                        conn.last_used = datetime.now()
                        return conn
                    except Exception:
                        conn.status = ConnectionStatus.ERROR
                        self._close_connection(conn)
            return None
    
    def add_connection(self, conn_info: ConnectionInfo) -> bool:
        """添加連接到池中"""
        with self.lock:
            if len(self.connections) >= self.max_connections:
                # 移除最舊的連接
                oldest = min(self.connections, key=lambda x: x.last_used)
                self._close_connection(oldest)
                self.connections.remove(oldest)
            
            self.connections.append(conn_info)
            return True
    
    def remove_connection(self, conn_info: ConnectionInfo):
        """從池中移除連接"""
        with self.lock:
            if conn_info in self.connections:
                self._close_connection(conn_info)
                self.connections.remove(conn_info)
    
    def _close_connection(self, conn_info: ConnectionInfo):
        """關閉連接"""
        if conn_info.client:
            try:
                conn_info.client.close()
            except Exception as e:
                logger.warning(f"關閉連接時出錯: {e}")
            conn_info.client = None
        conn_info.status = ConnectionStatus.DISCONNECTED
    
    def close_all(self):
        """關閉所有連接"""
        with self.lock:
            for conn in self.connections:
                self._close_connection(conn)
            self.connections.clear()
    
    def get_status(self) -> Dict[str, Any]:
        """獲取連接池狀態"""
        with self.lock:
            total = len(self.connections)
            connected = sum(1 for c in self.connections if c.status == ConnectionStatus.CONNECTED)
            return {
                "total_connections": total,
                "connected": connected,
                "max_connections": self.max_connections,
                "connections": [
                    {
                        "host": c.config.host,
                        "status": c.status.value,
                        "created_at": c.created_at.isoformat(),
                        "last_used": c.last_used.isoformat(),
                        "error": c.error_message
                    } for c in self.connections
                ]
            }


class SSHManager:
    """
    SSH 連接管理器
    
    提供統一的 SSH 連接管理接口，支援：
    - 連接池管理
    - 自動重試機制
    - 多種認證方式
    - 安全的憑證處理
    """
    
    def __init__(self, encryption: Optional[AESGCMEncryption] = None):
        self.encryption = encryption or AESGCMEncryption()
        self.connection_pools: Dict[str, SSHConnectionPool] = {}
        self.lock = threading.Lock()
        
        # 統計資訊
        self.connection_stats = defaultdict(int)
        self.command_stats = defaultdict(int)
    
    def _get_server_key(self, host: str, port: int, username: str) -> str:
        """生成伺服器唯一標識"""
        return f"{username}@{host}:{port}"
    
    def _get_connection_pool(self, config: SSHConnectionConfig) -> SSHConnectionPool:
        """獲取或建立連接池"""
        server_key = self._get_server_key(config.host, config.port, config.username)
        
        with self.lock:
            if server_key not in self.connection_pools:
                self.connection_pools[server_key] = SSHConnectionPool(config.max_connections)
            return self.connection_pools[server_key]
    
    def _create_ssh_client(self, config: SSHConnectionConfig) -> SSHClient:
        """建立 SSH 客戶端"""
        client = SSHClient()
        
        if config.auto_add_policy:
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        return client
    
    def _authenticate(self, client: SSHClient, config: SSHConnectionConfig) -> AuthType:
        """執行 SSH 認證"""
        auth_type = None
        
        try:
            # 嘗試金鑰認證
            if config.private_key:
                try:
                    if config.key_passphrase:
                        # 帶密碼的金鑰
                        pkey = paramiko.RSAKey.from_private_key(
                            io.StringIO(config.private_key),
                            password=config.key_passphrase
                        )
                        auth_type = AuthType.KEY_WITH_PASSPHRASE
                    else:
                        # 無密碼金鑰
                        pkey = paramiko.RSAKey.from_private_key(
                            io.StringIO(config.private_key)
                        )
                        auth_type = AuthType.KEY
                    
                    client.connect(
                        hostname=config.host,
                        port=config.port,
                        username=config.username,
                        pkey=pkey,
                        timeout=config.timeout
                    )
                    return auth_type
                    
                except (paramiko.AuthenticationException, paramiko.SSHException) as e:
                    logger.warning(f"金鑰認證失敗: {e}")
            
            # 嘗試密碼認證
            if config.password:
                client.connect(
                    hostname=config.host,
                    port=config.port,
                    username=config.username,
                    password=config.password,
                    timeout=config.timeout
                )
                auth_type = AuthType.PASSWORD
                return auth_type
            
            raise AuthenticationException("無可用的認證方式")
            
        except AuthenticationException as e:
            raise AuthenticationException(f"認證失敗: {str(e)}")
        except socket.timeout:
            raise socket.timeout("連接超時")
        except Exception as e:
            raise SSHException(f"連接失敗: {str(e)}")
    
    async def connect(self, config: SSHConnectionConfig, retry_count: int = 3) -> ConnectionInfo:
        """
        建立 SSH 連接
        
        Args:
            config: SSH 連接配置
            retry_count: 重試次數
            
        Returns:
            ConnectionInfo: 連接資訊
            
        Raises:
            SSHException: 連接失敗
        """
        pool = self._get_connection_pool(config)
        server_key = self._get_server_key(config.host, config.port, config.username)
        
        # 嘗試從連接池獲取可用連接
        existing_conn = pool.get_available_connection()
        if existing_conn:
            logger.debug(f"重用現有連接: {server_key}")
            self.connection_stats["reused"] += 1
            return existing_conn
        
        # 建立新連接
        conn_info = ConnectionInfo(config=config)
        conn_info.status = ConnectionStatus.CONNECTING
        
        for attempt in range(retry_count + 1):
            try:
                logger.info(f"嘗試連接 {server_key} (第 {attempt + 1} 次)")
                
                # 建立 SSH 客戶端
                client = self._create_ssh_client(config)
                
                # 執行認證
                auth_type = self._authenticate(client, config)
                
                # 測試連接
                stdin, stdout, stderr = client.exec_command("echo 'connection_test'", timeout=5)
                result = stdout.read().decode().strip()
                
                if result == "connection_test":
                    conn_info.client = client
                    conn_info.status = ConnectionStatus.CONNECTED
                    conn_info.error_message = None
                    conn_info.retry_count = attempt
                    
                    # 添加到連接池
                    pool.add_connection(conn_info)
                    
                    self.connection_stats["successful"] += 1
                    logger.info(f"成功連接 {server_key}，認證方式: {auth_type.value}")
                    
                    return conn_info
                else:
                    raise SSHException("連接測試失敗")
                    
            except (AuthenticationException, socket.timeout, SSHException) as e:
                conn_info.error_message = str(e)
                conn_info.retry_count = attempt
                logger.warning(f"連接 {server_key} 失敗 (第 {attempt + 1} 次): {e}")
                
                if attempt < retry_count:
                    # 指數退避重試
                    wait_time = min(2 ** attempt, 30)
                    logger.info(f"等待 {wait_time} 秒後重試...")
                    await asyncio.sleep(wait_time)
                else:
                    conn_info.status = ConnectionStatus.ERROR
                    self.connection_stats["failed"] += 1
                    raise SSHException(f"連接失敗，已重試 {retry_count} 次: {e}")
            
            except Exception as e:
                conn_info.error_message = str(e)
                conn_info.status = ConnectionStatus.ERROR
                self.connection_stats["failed"] += 1
                logger.error(f"連接 {server_key} 時發生未預期錯誤: {e}")
                raise SSHException(f"連接失敗: {e}")
        
        # 不應該到達這裡
        raise SSHException("連接失敗：未知錯誤")
    
    async def execute_command(
        self, 
        config: SSHConnectionConfig, 
        command: str, 
        timeout: Optional[int] = None
    ) -> Tuple[str, str, int]:
        """
        執行 SSH 指令
        
        Args:
            config: SSH 連接配置
            command: 要執行的指令
            timeout: 指令超時時間
            
        Returns:
            (stdout, stderr, exit_code)
            
        Raises:
            SSHException: 指令執行失敗
        """
        timeout = timeout or settings.SSH_COMMAND_TIMEOUT
        
        # 獲取連接
        conn_info = await self.connect(config)
        
        if not conn_info.client:
            raise SSHException("無可用的 SSH 連接")
        
        try:
            logger.debug(f"執行指令: {command}")
            start_time = time.time()
            
            stdin, stdout, stderr = conn_info.client.exec_command(command, timeout=timeout)
            
            # 讀取輸出
            stdout_data = stdout.read().decode('utf-8', errors='ignore')
            stderr_data = stderr.read().decode('utf-8', errors='ignore')
            exit_code = stdout.channel.recv_exit_status()
            
            execution_time = time.time() - start_time
            
            # 更新統計
            self.command_stats["executed"] += 1
            self.command_stats["total_time"] += execution_time
            
            logger.debug(
                f"指令執行完成，耗時: {execution_time:.2f}s, "
                f"退出碼: {exit_code}"
            )
            
            return stdout_data, stderr_data, exit_code
            
        except socket.timeout:
            self.command_stats["timeout"] += 1
            raise SSHException(f"指令執行超時 ({timeout}s): {command}")
        except Exception as e:
            self.command_stats["failed"] += 1
            raise SSHException(f"指令執行失敗: {e}")
    
    @asynccontextmanager
    async def ssh_connection(self, config: SSHConnectionConfig):
        """
        SSH 連接上下文管理器
        
        Args:
            config: SSH 連接配置
            
        Yields:
            ConnectionInfo: 連接資訊
        """
        conn_info = None
        try:
            conn_info = await self.connect(config)
            yield conn_info
        finally:
            # 連接會保留在池中，不需要手動關閉
            pass
    
    def test_connection(self, config: SSHConnectionConfig) -> Dict[str, Any]:
        """
        測試 SSH 連接
        
        Args:
            config: SSH 連接配置
            
        Returns:
            測試結果字典
        """
        start_time = time.time()
        result = {
            "success": False,
            "message": "",
            "duration": 0.0,
            "host": config.host,
            "port": config.port,
            "username": config.username
        }
        
        try:
            # 同步測試連接
            client = self._create_ssh_client(config) 
            auth_type = self._authenticate(client, config)
            
            # 執行測試指令
            stdin, stdout, stderr = client.exec_command("echo 'test'", timeout=5)
            output = stdout.read().decode().strip()
            
            if output == "test":
                result["success"] = True
                result["message"] = f"連接成功，認證方式: {auth_type.value}"
            else:
                result["message"] = "連接測試失敗"
            
            client.close()
            
        except Exception as e:
            result["message"] = f"連接失敗: {str(e)}"
        
        result["duration"] = time.time() - start_time
        return result
    
    def get_server_status(self, host: str, port: int, username: str) -> Dict[str, Any]:
        """獲取伺服器連接狀態"""
        server_key = self._get_server_key(host, port, username)
        
        if server_key in self.connection_pools:
            pool = self.connection_pools[server_key]
            return pool.get_status()
        
        return {
            "total_connections": 0,
            "connected": 0,
            "max_connections": 0,
            "connections": []
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """獲取管理器統計資訊"""
        total_pools = len(self.connection_pools)
        total_connections = sum(len(pool.connections) for pool in self.connection_pools.values())
        active_connections = sum(
            sum(1 for c in pool.connections if c.status == ConnectionStatus.CONNECTED)
            for pool in self.connection_pools.values()
        )
        
        avg_command_time = 0
        if self.command_stats["executed"] > 0:
            avg_command_time = self.command_stats["total_time"] / self.command_stats["executed"]
        
        return {
            "connection_pools": total_pools,
            "total_connections": total_connections,
            "active_connections": active_connections,
            "connection_stats": dict(self.connection_stats),
            "command_stats": dict(self.command_stats),
            "avg_command_time": round(avg_command_time, 3)
        }
    
    def close_all_connections(self):
        """關閉所有連接"""
        with self.lock:
            for pool in self.connection_pools.values():
                pool.close_all()
            self.connection_pools.clear()
        
        logger.info("已關閉所有 SSH 連接")
    
    def decrypt_server_credentials(self, server_data: Dict[str, Any]) -> SSHConnectionConfig:
        """
        從資料庫資料解密並建立 SSH 配置
        
        Args:
            server_data: 包含加密憑證的伺服器資料
            
        Returns:
            SSHConnectionConfig: 解密後的連接配置
        """
        try:
            config = SSHConnectionConfig(
                host=server_data["ip_address"],
                port=server_data.get("ssh_port", 22),
                username=server_data["username"],
                timeout=server_data.get("connection_timeout", settings.SSH_CONNECT_TIMEOUT),
                max_connections=server_data.get("max_connections", settings.SSH_MAX_CONNECTIONS),
            )
            
            # 解密密碼
            if server_data.get("password_encrypted"):
                config.password = self.encryption.decrypt(server_data["password_encrypted"])
            
            # 解密私鑰
            if server_data.get("private_key_encrypted"):
                config.private_key = self.encryption.decrypt(server_data["private_key_encrypted"])
                
                # 如果有金鑰密碼
                if server_data.get("key_passphrase_encrypted"):
                    config.key_passphrase = self.encryption.decrypt(server_data["key_passphrase_encrypted"])
            
            return config
            
        except EncryptionError as e:
            raise SSHException(f"憑證解密失敗: {e}")
        except Exception as e:
            raise SSHException(f"配置建立失敗: {e}")


# 全域 SSH 管理器實例
ssh_manager = SSHManager()


# 便利函數
async def test_ssh_connection(server_data: Dict[str, Any]) -> Dict[str, Any]:
    """測試 SSH 連接的便利函數"""
    config = ssh_manager.decrypt_server_credentials(server_data)
    return ssh_manager.test_connection(config)


async def execute_ssh_command(
    server_data: Dict[str, Any], 
    command: str, 
    timeout: Optional[int] = None
) -> Tuple[str, str, int]:
    """執行 SSH 指令的便利函數"""
    config = ssh_manager.decrypt_server_credentials(server_data)
    return await ssh_manager.execute_command(config, command, timeout)


if __name__ == "__main__":
    # 測試 SSH 管理器
    import io
    import asyncio
    
    async def test_ssh_manager():
        print("🔗 測試 SSH 管理器...")
        
        # 測試配置（請根據實際環境修改）
        test_config = SSHConnectionConfig(
            host="localhost",
            port=22,
            username="test",
            password="test123"
        )
        
        try:
            # 測試連接
            result = ssh_manager.test_connection(test_config)
            print(f"連接測試結果: {result}")
            
            if result["success"]:
                # 測試指令執行
                stdout, stderr, code = await ssh_manager.execute_command(
                    test_config, "echo 'Hello from SSH'"
                )
                print(f"指令輸出: {stdout.strip()}")
                print(f"退出碼: {code}")
            
            # 顯示統計
            stats = ssh_manager.get_statistics()
            print(f"統計資訊: {stats}")
            
        except Exception as e:
            print(f"測試失敗: {e}")
        finally:
            ssh_manager.close_all_connections()
    
    # 執行測試
    asyncio.run(test_ssh_manager())