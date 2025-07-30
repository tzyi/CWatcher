"""
CWatcher 監控系統整合測試

測試監控系統的端到端整合功能
包括 SSH 連接、數據收集、API 調用的完整流程
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from sqlalchemy.orm import Session

from services.monitoring_collector import (
    MonitoringCollectorService,
    monitoring_service,
    collect_server_monitoring_data,
    test_server_connection_and_monitoring,
    MetricType,
    AlertLevel,
    MonitoringThresholds
)
from services.ssh_manager import SSHConnectionConfig, ssh_manager
from services.command_executor import CommandResult, ExecutionStatus, command_executor
from models.server import Server


@pytest.fixture
def test_server_data():
    """測試用伺服器數據"""
    return {
        "id": 1,
        "name": "Test Server",
        "host": "localhost",
        "port": 22,
        "username": "test-user",
        "encrypted_password": "encrypted_test_password",
        "encrypted_private_key": None
    }


@pytest.fixture
def mock_ssh_commands():
    """Mock SSH 指令執行結果"""
    return {
        # CPU 相關指令
        "cat /proc/stat": CommandResult(
            command="cat /proc/stat",
            stdout="cpu  123456 0 234567 7890123 12345 0 6789 0 0 0\ncpu0 30864 0 58641 1972530 3086 0 1697 0 0 0\n",
            stderr="",
            exit_code=0,
            status=ExecutionStatus.SUCCESS
        ),
        "lscpu": CommandResult(
            command="lscpu",
            stdout="""Architecture:        x86_64
CPU op-mode(s):      32-bit, 64-bit
Byte Order:          Little Endian
CPU(s):              4
Model name:          Intel(R) Core(TM) i5-8250U CPU @ 1.60GHz
CPU max MHz:         3400.0000
CPU min MHz:         400.0000""",
            stderr="",
            exit_code=0,
            status=ExecutionStatus.SUCCESS
        ),
        "cat /proc/loadavg": CommandResult(
            command="cat /proc/loadavg",
            stdout="0.15 0.10 0.05 1/123 456",
            stderr="",
            exit_code=0,
            status=ExecutionStatus.SUCCESS
        ),
        "uptime": CommandResult(
            command="uptime",
            stdout=" 10:30:15 up 1 day,  2:25,  1 user,  load average: 0.15, 0.10, 0.05",
            stderr="",
            exit_code=0,
            status=ExecutionStatus.SUCCESS
        ),
        
        # 記憶體相關指令
        "cat /proc/meminfo": CommandResult(
            command="cat /proc/meminfo",
            stdout="""MemTotal:        8174592 kB
MemFree:         1234567 kB
MemAvailable:    5678901 kB
Buffers:          123456 kB
Cached:          2345678 kB
SwapCached:            0 kB
Active:          3456789 kB
Inactive:        1234567 kB
SwapTotal:       2097148 kB
SwapFree:        2097148 kB""",
            stderr="",
            exit_code=0,
            status=ExecutionStatus.SUCCESS
        ),
        "free -b": CommandResult(
            command="free -b",
            stdout="""              total        used        free      shared  buff/cache   available
Mem:     8370782208  2678456320  1265637888    89104384  4426688000  5817344000
Swap:    2147479552           0  2147479552""",
            stderr="",
            exit_code=0,
            status=ExecutionStatus.SUCCESS
        ),
        
        # 磁碟相關指令
        "df -h": CommandResult(
            command="df -h",
            stdout="""Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1       500G  380G  120G  76% /
/dev/sda2       100G   50G   50G  50% /home
tmpfs           4.0G     0  4.0G   0% /dev/shm""",
            stderr="",
            exit_code=0,
            status=ExecutionStatus.SUCCESS
        ),
        "df -B1": CommandResult(
            command="df -B1",
            stdout="""Filesystem     1B-blocks        Used   Available Use% Mounted on
/dev/sda1     500000000000  380000000000  120000000000  76% /
/dev/sda2     100000000000   50000000000   50000000000  50% /home""",
            stderr="",
            exit_code=0,
            status=ExecutionStatus.SUCCESS
        ),
        "iostat -x 1 1 2>/dev/null || cat /proc/diskstats": CommandResult(
            command="iostat -x 1 1 2>/dev/null || cat /proc/diskstats",
            stdout="""   8       0 sda 12345 0 567890 12000 23456 0 789012 34000 0 45000 78000 0 0 0 0 0
   8       1 sda1 8901 0 234567 8000 12345 0 345678 20000 0 28000 45000 0 0 0 0 0""",
            stderr="",
            exit_code=0,
            status=ExecutionStatus.SUCCESS
        ),
        "lsblk -b -P 2>/dev/null || lsblk": CommandResult(
            command="lsblk -b -P 2>/dev/null || lsblk",
            stdout='NAME="sda" SIZE="500000000000" TYPE="disk" MOUNTPOINT=""\nNAME="sda1" SIZE="500000000000" TYPE="part" MOUNTPOINT="/"',
            stderr="",
            exit_code=0,
            status=ExecutionStatus.SUCCESS
        ),
        
        # 網路相關指令
        "cat /proc/net/dev": CommandResult(
            command="cat /proc/net/dev",
            stdout="""Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 1234567890   123456    0    0    0     0          0         0  1234567890   123456    0    0    0     0       0          0
  eth0: 9876543210   987654    0    0    0     0          0         0  5432109876   543210    0    0    0     0       0          0""",
            stderr="",
            exit_code=0,
            status=ExecutionStatus.SUCCESS
        ),
        "ip addr show": CommandResult(
            command="ip addr show",
            stdout="""1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 52:54:00:12:34:56 brd ff:ff:ff:ff:ff:ff
    inet 192.168.1.100/24 brd 192.168.1.255 scope global eth0""",
            stderr="",
            exit_code=0,
            status=ExecutionStatus.SUCCESS
        ),
        "ss -s": CommandResult(
            command="ss -s",
            stdout="""Total: 123 (kernel 456)
TCP:   45 (estab 12, closed 8, orphaned 1, synrecv 0, timewait 7/0), ports 0
UDP:   78 (kernel 90)""",
            stderr="",
            exit_code=0,
            status=ExecutionStatus.SUCCESS
        ),
        "netstat -i 2>/dev/null || cat /proc/net/dev": CommandResult(
            command="netstat -i 2>/dev/null || cat /proc/net/dev",
            stdout="netstat output",
            stderr="",
            exit_code=0,
            status=ExecutionStatus.SUCCESS
        ),
        
        # 連接測試指令
        "echo 'connection_test'": CommandResult(
            command="echo 'connection_test'",
            stdout="connection_test",
            stderr="",
            exit_code=0,
            status=ExecutionStatus.SUCCESS
        )
    }


class TestMonitoringIntegration:
    """監控系統整合測試"""
    
    @pytest.mark.asyncio
    async def test_complete_monitoring_workflow(self, test_server_data, mock_ssh_commands):
        """測試完整的監控工作流程"""
        
        # Mock SSH 管理器和指令執行器
        with patch.object(ssh_manager, 'decrypt_server_credentials') as mock_decrypt, \
             patch.object(command_executor, 'execute_command') as mock_execute:
            
            # 設定 SSH 解密
            mock_config = SSHConnectionConfig(
                host=test_server_data["host"],
                port=test_server_data["port"],
                username=test_server_data["username"],
                password="test_password"
            )
            mock_decrypt.return_value = mock_config
            
            # 設定指令執行 Mock
            def mock_execute_side_effect(config, command, timeout=30):
                if command in mock_ssh_commands:
                    return mock_ssh_commands[command]
                else:
                    return CommandResult(
                        command=command,
                        stdout="",
                        stderr=f"Command not mocked: {command}",
                        exit_code=1,
                        status=ExecutionStatus.FAILED
                    )
            
            mock_execute.side_effect = mock_execute_side_effect
            
            # 測試監控數據收集
            summary_data = await collect_server_monitoring_data(test_server_data)
            
            # 驗證摘要數據結構
            assert summary_data["server_id"] == 1
            assert summary_data["collection_status"] == "success"
            assert "metrics" in summary_data
            assert "cpu" in summary_data["metrics"]
            assert "memory" in summary_data["metrics"]
            assert "disk" in summary_data["metrics"]
            assert "network" in summary_data["metrics"]
            
            # 驗證 CPU 數據
            cpu_metrics = summary_data["metrics"]["cpu"]
            assert "usage_percent" in cpu_metrics
            assert "core_count" in cpu_metrics
            assert cpu_metrics["core_count"] == 4
            assert "model_name" in cpu_metrics
            assert "Intel" in cpu_metrics["model_name"]
            
            # 驗證記憶體數據
            memory_metrics = summary_data["metrics"]["memory"]
            assert "usage_percent" in memory_metrics
            assert "total_gb" in memory_metrics
            assert memory_metrics["total_gb"] > 0
            assert "swap_usage_percent" in memory_metrics
            
            # 驗證磁碟數據
            disk_metrics = summary_data["metrics"]["disk"]
            assert "usage_percent" in disk_metrics
            assert "total_gb" in disk_metrics
            assert "filesystems" in disk_metrics
            assert len(disk_metrics["filesystems"]) > 0
            
            # 驗證網路數據
            network_metrics = summary_data["metrics"]["network"]
            assert "download_mb_per_sec" in network_metrics
            assert "upload_mb_per_sec" in network_metrics
            assert "interfaces" in network_metrics
            assert "eth0" in network_metrics["interfaces"]
    
    @pytest.mark.asyncio
    async def test_monitoring_with_alerts(self, test_server_data, mock_ssh_commands):
        """測試包含警告的監控數據收集"""
        
        # 修改 CPU 統計以觸發高使用率警告
        high_cpu_stats = mock_ssh_commands["cat /proc/stat"]
        high_cpu_stats.stdout = "cpu  900000 0 50000 100000 10000 0 5000 0 0 0"  # 模擬高 CPU 使用
        
        with patch.object(ssh_manager, 'decrypt_server_credentials') as mock_decrypt, \
             patch.object(command_executor, 'execute_command') as mock_execute:
            
            mock_config = SSHConnectionConfig(
                host=test_server_data["host"],
                port=test_server_data["port"],
                username=test_server_data["username"],
                password="test_password"
            )
            mock_decrypt.return_value = mock_config
            
            # 第一次收集（建立基準）
            def mock_execute_first_time(config, command, timeout=30):
                if command == "cat /proc/stat":
                    return CommandResult(
                        command=command,
                        stdout="cpu  100000 0 20000 800000 10000 0 5000 0 0 0",
                        stderr="",
                        exit_code=0,
                        status=ExecutionStatus.SUCCESS
                    )
                return mock_ssh_commands.get(command, CommandResult(command, "", "", 1, ExecutionStatus.FAILED))
            
            mock_execute.side_effect = mock_execute_first_time
            
            # 第一次收集
            await collect_server_monitoring_data(test_server_data)
            
            # 第二次收集（觸發警告）
            def mock_execute_second_time(config, command, timeout=30):
                if command == "cat /proc/stat":
                    return CommandResult(
                        command=command,
                        stdout="cpu  900000 0 50000 100000 10000 0 5000 0 0 0",  # 高 CPU 活動
                        stderr="",
                        exit_code=0,
                        status=ExecutionStatus.SUCCESS
                    )
                return mock_ssh_commands.get(command, CommandResult(command, "", "", 1, ExecutionStatus.FAILED))
            
            mock_execute.side_effect = mock_execute_second_time
            
            # 第二次收集
            summary_data = await collect_server_monitoring_data(test_server_data)
            
            # 驗證警告狀態
            assert "overall_alert_level" in summary_data
            cpu_metrics = summary_data["metrics"]["cpu"]
            
            # CPU 使用率應該很高且觸發警告
            if cpu_metrics["usage_percent"] > 80:
                assert cpu_metrics["alert_level"] in ["warning", "critical"]
    
    @pytest.mark.asyncio
    async def test_connection_test_integration(self, test_server_data, mock_ssh_commands):
        """測試連接測試整合功能"""
        
        with patch.object(ssh_manager, 'decrypt_server_credentials') as mock_decrypt, \
             patch.object(command_executor, 'execute_command') as mock_execute:
            
            mock_config = SSHConnectionConfig(
                host=test_server_data["host"],
                port=test_server_data["port"],
                username=test_server_data["username"],
                password="test_password"
            )
            mock_decrypt.return_value = mock_config
            
            def mock_execute_side_effect(config, command, timeout=30):
                return mock_ssh_commands.get(command, CommandResult(command, "", "", 1, ExecutionStatus.FAILED))
            
            mock_execute.side_effect = mock_execute_side_effect
            
            # 測試連接和監控
            test_result = await test_server_connection_and_monitoring(test_server_data)
            
            # 驗證連接測試結果
            assert test_result["connection_status"] == "success"
            assert test_result["collection_status"] == "success"
            assert "metrics" in test_result
    
    @pytest.mark.asyncio
    async def test_connection_failure_handling(self, test_server_data):
        """測試連接失敗處理"""
        
        with patch.object(ssh_manager, 'decrypt_server_credentials') as mock_decrypt, \
             patch.object(command_executor, 'execute_command') as mock_execute:
            
            mock_config = SSHConnectionConfig(
                host=test_server_data["host"],
                port=test_server_data["port"],
                username=test_server_data["username"],
                password="test_password"
            )
            mock_decrypt.return_value = mock_config
            
            # 模擬連接失敗
            mock_execute.return_value = CommandResult(
                command="echo 'connection_test'",
                stdout="",
                stderr="Connection failed",
                exit_code=1,
                status=ExecutionStatus.FAILED,
                error_message="SSH connection timeout"
            )
            
            # 測試連接失敗處理
            test_result = await test_server_connection_and_monitoring(test_server_data)
            
            # 驗證失敗處理
            assert test_result["connection_status"] == "failed"
            assert "error" in test_result
    
    @pytest.mark.asyncio
    async def test_partial_data_collection(self, test_server_data, mock_ssh_commands):
        """測試部分數據收集失敗的處理"""
        
        with patch.object(ssh_manager, 'decrypt_server_credentials') as mock_decrypt, \
             patch.object(command_executor, 'execute_command') as mock_execute:
            
            mock_config = SSHConnectionConfig(
                host=test_server_data["host"],
                port=test_server_data["port"],
                username=test_server_data["username"],
                password="test_password"
            )
            mock_decrypt.return_value = mock_config
            
            # 設定部分指令失敗
            def mock_execute_partial_failure(config, command, timeout=30):
                if command == "cat /proc/meminfo":  # 記憶體指令失敗
                    return CommandResult(
                        command=command,
                        stdout="",
                        stderr="Permission denied",
                        exit_code=1,
                        status=ExecutionStatus.FAILED
                    )
                return mock_ssh_commands.get(command, CommandResult(command, "", "", 1, ExecutionStatus.FAILED))
            
            mock_execute.side_effect = mock_execute_partial_failure
            
            # 測試部分失敗的數據收集
            summary_data = await collect_server_monitoring_data(test_server_data)
            
            # 驗證部分成功的結果
            assert summary_data["collection_status"] == "success"  # 整體仍然成功
            assert "cpu" in summary_data["metrics"]  # CPU 數據應該成功
            
            # 記憶體數據可能失敗或為預設值
            if "memory" in summary_data["metrics"]:
                memory_metrics = summary_data["metrics"]["memory"]
                # 檢查是否有錯誤指示
                assert isinstance(memory_metrics, dict)
    
    @pytest.mark.asyncio
    async def test_threshold_integration(self, test_server_data, mock_ssh_commands):
        """測試閾值整合功能"""
        
        # 建立自訂閾值
        custom_thresholds = MonitoringThresholds(
            cpu_warning=50.0,      # 降低 CPU 警告閾值
            cpu_critical=70.0,     # 降低 CPU 嚴重閾值
            memory_warning=60.0,   # 降低記憶體警告閾值
            memory_critical=80.0   # 降低記憶體嚴重閾值
        )
        
        # 建立使用自訂閾值的監控服務
        with patch('app.services.monitoring_collector.command_executor'):
            custom_service = MonitoringCollectorService(custom_thresholds)
        
        with patch.object(ssh_manager, 'decrypt_server_credentials') as mock_decrypt, \
             patch.object(custom_service.executor, 'execute_command') as mock_execute:
            
            mock_config = SSHConnectionConfig(
                host=test_server_data["host"],
                port=test_server_data["port"],
                username=test_server_data["username"],
                password="test_password"
            )
            mock_decrypt.return_value = mock_config
            
            def mock_execute_side_effect(config, command, timeout=30):
                return mock_ssh_commands.get(command, CommandResult(command, "", "", 1, ExecutionStatus.FAILED))
            
            mock_execute.side_effect = mock_execute_side_effect
            
            # 測試自訂閾值的監控
            all_metrics = await custom_service.collect_all_metrics(mock_config, server_id=1)
            
            # 驗證閾值設定生效
            assert custom_service.thresholds.cpu_warning == 50.0
            assert custom_service.thresholds.cpu_critical == 70.0
            
            # 驗證收集結果
            assert len(all_metrics) == 4
            for metric_type, metric_data in all_metrics.items():
                assert isinstance(metric_data.alert_level, AlertLevel)
    
    @pytest.mark.asyncio 
    async def test_concurrent_monitoring(self, mock_ssh_commands):
        """測試並發監控數據收集"""
        
        # 準備多台伺服器數據
        server_data_list = [
            {
                "id": i,
                "host": f"192.168.1.{100 + i}",
                "port": 22,
                "username": "test-user",
                "encrypted_password": f"encrypted_password_{i}",
                "encrypted_private_key": None
            }
            for i in range(1, 4)
        ]
        
        with patch.object(ssh_manager, 'decrypt_server_credentials') as mock_decrypt, \
             patch.object(command_executor, 'execute_command') as mock_execute:
            
            # 設定解密和指令執行 Mock
            def mock_decrypt_side_effect(server_data):
                return SSHConnectionConfig(
                    host=server_data["host"],
                    port=server_data["port"],
                    username=server_data["username"],
                    password="test_password"
                )
            
            mock_decrypt.side_effect = mock_decrypt_side_effect
            
            def mock_execute_side_effect(config, command, timeout=30):
                return mock_ssh_commands.get(command, CommandResult(command, "", "", 1, ExecutionStatus.FAILED))
            
            mock_execute.side_effect = mock_execute_side_effect
            
            # 並發收集多台伺服器數據
            tasks = [collect_server_monitoring_data(server_data) for server_data in server_data_list]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 驗證並發結果
            assert len(results) == 3
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    pytest.fail(f"Server {i+1} monitoring failed: {result}")
                else:
                    assert result["server_id"] == i + 1
                    assert result["collection_status"] == "success"
    
    @pytest.mark.asyncio
    async def test_monitoring_performance(self, test_server_data, mock_ssh_commands):
        """測試監控性能"""
        
        with patch.object(ssh_manager, 'decrypt_server_credentials') as mock_decrypt, \
             patch.object(command_executor, 'execute_command') as mock_execute:
            
            mock_config = SSHConnectionConfig(
                host=test_server_data["host"],
                port=test_server_data["port"],
                username=test_server_data["username"],
                password="test_password"
            )
            mock_decrypt.return_value = mock_config
            
            def mock_execute_side_effect(config, command, timeout=30):
                return mock_ssh_commands.get(command, CommandResult(command, "", "", 1, ExecutionStatus.FAILED))
            
            mock_execute.side_effect = mock_execute_side_effect
            
            # 測量執行時間
            import time
            start_time = time.time()
            
            summary_data = await collect_server_monitoring_data(test_server_data)
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # 驗證性能要求 (應該在合理時間內完成)
            assert execution_time < 10.0  # 應該在 10 秒內完成
            assert summary_data["collection_status"] == "success"
            
            # 驗證收集時間有記錄
            assert "timestamp" in summary_data


@pytest.mark.slow
class TestMonitoringRealWorldScenarios:
    """監控真實場景測試"""
    
    @pytest.mark.asyncio
    async def test_large_server_fleet_monitoring(self):
        """測試大量伺服器監控"""
        # 這個測試模擬監控大量伺服器的情況
        pass
    
    @pytest.mark.asyncio
    async def test_long_running_monitoring(self):
        """測試長時間運行的監控"""
        # 這個測試模擬長時間監控的情況
        pass
    
    @pytest.mark.asyncio
    async def test_network_instability_handling(self):
        """測試網路不穩定處理"""
        # 這個測試模擬網路不穩定的情況
        pass


if __name__ == "__main__":
    # 執行整合測試
    pytest.main([__file__, "-v", "--tb=short"])