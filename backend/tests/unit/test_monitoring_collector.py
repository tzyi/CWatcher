"""
CWatcher 監控數據收集器單元測試

測試監控數據收集器的各個組件功能
包括 CPU、記憶體、磁碟、網路監控器的單元測試
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from services.monitoring_collector import (
    CPUMonitor,
    MemoryMonitor,
    DiskMonitor,
    NetworkMonitor,
    MonitoringCollectorService,
    MonitoringThresholds,
    MetricType,
    AlertLevel,
    MonitoringData
)
from services.command_executor import CommandResult, ExecutionStatus
from services.ssh_manager import SSHConnectionConfig


@pytest.fixture
def mock_executor():
    """Mock 指令執行器"""
    executor = Mock()
    executor.execute_command = AsyncMock()
    executor.execute_predefined_command = AsyncMock()
    return executor


@pytest.fixture
def test_config():
    """測試用 SSH 配置"""
    return SSHConnectionConfig(
        host="test-host",
        port=22,
        username="test-user",
        password="test-pass"
    )


@pytest.fixture
def test_thresholds():
    """測試用監控閾值"""
    return MonitoringThresholds(
        cpu_warning=80.0,
        cpu_critical=90.0,
        memory_warning=85.0,
        memory_critical=95.0,
        disk_warning=85.0,
        disk_critical=95.0,
        load_warning=5.0,
        load_critical=10.0
    )


class TestCPUMonitor:
    """CPU 監控器測試"""
    
    @pytest.fixture
    def cpu_monitor(self, mock_executor, test_thresholds):
        return CPUMonitor(mock_executor, test_thresholds)
    
    @pytest.mark.asyncio
    async def test_collect_cpu_metrics_success(self, cpu_monitor, mock_executor, test_config):
        """測試成功收集 CPU 監控數據"""
        # 模擬指令執行結果
        mock_executor.execute_command.side_effect = [
            # cat /proc/stat
            CommandResult(
                command="cat /proc/stat",
                stdout="cpu  123456 0 234567 7890123 12345 0 6789 0 0 0\n",
                stderr="",
                exit_code=0,
                status=ExecutionStatus.SUCCESS
            ),
            # lscpu
            CommandResult(
                command="lscpu",
                stdout="Architecture: x86_64\nCPU(s): 4\nModel name: Intel Core i5\nCPU max MHz: 2400.0000\n",
                stderr="",
                exit_code=0,
                status=ExecutionStatus.SUCCESS
            ),
            # cat /proc/loadavg
            CommandResult(
                command="cat /proc/loadavg",
                stdout="0.15 0.10 0.05 1/123 456\n",
                stderr="",
                exit_code=0,
                status=ExecutionStatus.SUCCESS
            ),
            # uptime
            CommandResult(
                command="uptime",
                stdout=" 10:30:00 up 1 day,  2:15,  1 user,  load average: 0.15, 0.10, 0.05\n",
                stderr="",
                exit_code=0,
                status=ExecutionStatus.SUCCESS
            )
        ]
        
        # 執行監控數據收集
        result = await cpu_monitor.collect_cpu_metrics(test_config, server_id=1)
        
        # 驗證結果
        assert isinstance(result, MonitoringData)
        assert result.metric_type == MetricType.CPU
        assert result.server_id == 1
        assert result.alert_level == AlertLevel.OK
        assert "usage_percent" in result.data
        assert "core_count" in result.data
        assert "load_average" in result.data
        
        # 驗證指令執行次數
        assert mock_executor.execute_command.call_count == 4
    
    @pytest.mark.asyncio
    async def test_cpu_usage_calculation(self, cpu_monitor, mock_executor, test_config):
        """測試 CPU 使用率計算"""
        # 第一次收集（基準數據）
        mock_executor.execute_command.side_effect = [
            CommandResult(
                command="cat /proc/stat",
                stdout="cpu  100000 0 20000 800000 10000 0 5000 0 0 0\n",
                stderr="",
                exit_code=0,
                status=ExecutionStatus.SUCCESS
            ),
            CommandResult(command="lscpu", stdout="CPU(s): 4\n", stderr="", exit_code=0, status=ExecutionStatus.SUCCESS),
            CommandResult(command="cat /proc/loadavg", stdout="0.15 0.10 0.05 1/123 456\n", stderr="", exit_code=0, status=ExecutionStatus.SUCCESS),
            CommandResult(command="uptime", stdout="uptime info\n", stderr="", exit_code=0, status=ExecutionStatus.SUCCESS),
        ]
        
        result1 = await cpu_monitor.collect_cpu_metrics(test_config)
        assert result1.data.get("usage_percent", 0) == 0.0  # 第一次沒有歷史數據
        
        # 第二次收集（計算使用率）
        mock_executor.execute_command.side_effect = [
            CommandResult(
                command="cat /proc/stat",
                stdout="cpu  102000 0 22000 810000 10000 0 5000 0 0 0\n",  # CPU活動增加
                stderr="",
                exit_code=0,
                status=ExecutionStatus.SUCCESS
            ),
            CommandResult(command="lscpu", stdout="CPU(s): 4\n", stderr="", exit_code=0, status=ExecutionStatus.SUCCESS),
            CommandResult(command="cat /proc/loadavg", stdout="0.15 0.10 0.05 1/123 456\n", stderr="", exit_code=0, status=ExecutionStatus.SUCCESS),
            CommandResult(command="uptime", stdout="uptime info\n", stderr="", exit_code=0, status=ExecutionStatus.SUCCESS),
        ]
        
        result2 = await cpu_monitor.collect_cpu_metrics(test_config)
        usage = result2.data.get("usage_percent", 0)
        assert usage > 0  # 應該有計算出使用率
        assert usage <= 100  # 使用率應該在合理範圍內
    
    @pytest.mark.asyncio
    async def test_cpu_alert_detection(self, cpu_monitor, mock_executor, test_config):
        """測試 CPU 警告檢測"""
        # 模擬高 CPU 使用率
        with patch.object(cpu_monitor, '_calculate_cpu_usage', return_value=95.0):
            mock_executor.execute_command.side_effect = [
                CommandResult(command="cat /proc/stat", stdout="cpu  123456 0 234567 7890123 12345 0 6789 0 0 0\n", stderr="", exit_code=0, status=ExecutionStatus.SUCCESS),
                CommandResult(command="lscpu", stdout="CPU(s): 4\n", stderr="", exit_code=0, status=ExecutionStatus.SUCCESS),
                CommandResult(command="cat /proc/loadavg", stdout="0.15 0.10 0.05 1/123 456\n", stderr="", exit_code=0, status=ExecutionStatus.SUCCESS),
                CommandResult(command="uptime", stdout="uptime info\n", stderr="", exit_code=0, status=ExecutionStatus.SUCCESS),
            ]
            
            result = await cpu_monitor.collect_cpu_metrics(test_config)
            assert result.alert_level == AlertLevel.CRITICAL
            assert "CPU使用率過高" in result.alert_message
    
    @pytest.mark.asyncio
    async def test_cpu_parsing_methods(self, cpu_monitor):
        """測試 CPU 數據解析方法"""
        # 測試 /proc/stat 解析
        cpu_stat_output = "cpu  123456 0 234567 7890123 12345 0 6789 0 0 0"
        stats = cpu_monitor._parse_cpu_stat(cpu_stat_output)
        
        assert stats["user"] == 123456
        assert stats["system"] == 234567
        assert stats["idle"] == 7890123
        assert "total" in stats
        
        # 測試 lscpu 解析
        lscpu_output = """Architecture: x86_64
CPU(s): 4
Model name: Intel(R) Core(TM) i5-8250U CPU @ 1.60GHz
CPU max MHz: 3400.0000"""
        
        info = cpu_monitor._parse_lscpu(lscpu_output)
        assert info["cpu_cores"] == 4
        assert info["model_name"] == "Intel(R) Core(TM) i5-8250U CPU @ 1.60GHz"
        assert info["cpu_max_mhz"] == 3400.0
        
        # 測試負載平均值解析
        load_output = "0.15 0.10 0.05 1/123 456"
        load_data = cpu_monitor._parse_load_average(load_output)
        
        assert load_data["1min"] == 0.15
        assert load_data["5min"] == 0.10
        assert load_data["15min"] == 0.05


class TestMemoryMonitor:
    """記憶體監控器測試"""
    
    @pytest.fixture
    def memory_monitor(self, mock_executor, test_thresholds):
        return MemoryMonitor(mock_executor, test_thresholds)
    
    @pytest.mark.asyncio
    async def test_collect_memory_metrics_success(self, memory_monitor, mock_executor, test_config):
        """測試成功收集記憶體監控數據"""
        # 模擬指令執行結果
        mock_executor.execute_command.side_effect = [
            # cat /proc/meminfo
            CommandResult(
                command="cat /proc/meminfo",
                stdout="""MemTotal:        8174592 kB
MemFree:         1234567 kB
MemAvailable:    5678901 kB
Buffers:          123456 kB
Cached:          2345678 kB
SwapTotal:       2097148 kB
SwapFree:        2097148 kB""",
                stderr="",
                exit_code=0,
                status=ExecutionStatus.SUCCESS
            ),
            # free -b
            CommandResult(
                command="free -b",
                stdout="""              total        used        free      shared  buff/cache   available
Mem:     8370782208  2678456320  1265637888    89104384  4426688000  5817344000
Swap:    2147479552           0  2147479552""",
                stderr="",
                exit_code=0,
                status=ExecutionStatus.SUCCESS
            )
        ]
        
        # 執行監控數據收集
        result = await memory_monitor.collect_memory_metrics(test_config, server_id=1)
        
        # 驗證結果
        assert isinstance(result, MonitoringData)
        assert result.metric_type == MetricType.MEMORY
        assert result.server_id == 1
        assert "usage_percent" in result.data
        assert "total_bytes" in result.data
        assert "used_bytes" in result.data
        assert "swap_usage_percent" in result.data
        
        # 驗證數據計算
        assert result.data["total_bytes"] > 0
        assert result.data["usage_percent"] >= 0
        assert result.data["usage_percent"] <= 100
    
    @pytest.mark.asyncio
    async def test_memory_alert_detection(self, memory_monitor, mock_executor, test_config):
        """測試記憶體警告檢測"""
        # 模擬高記憶體使用率
        mock_executor.execute_command.side_effect = [
            CommandResult(
                command="cat /proc/meminfo",
                stdout="""MemTotal:        8174592 kB
MemFree:          100000 kB
MemAvailable:     400000 kB""",  # 低可用記憶體
                stderr="",
                exit_code=0,
                status=ExecutionStatus.SUCCESS
            ),
            CommandResult(command="free -b", stdout="free output", stderr="", exit_code=0, status=ExecutionStatus.SUCCESS)
        ]
        
        result = await memory_monitor.collect_memory_metrics(test_config)
        # 應該觸發警告（使用率 > 85%）
        assert result.alert_level in [AlertLevel.WARNING, AlertLevel.CRITICAL]
    
    def test_meminfo_parsing(self, memory_monitor):
        """測試 /proc/meminfo 解析"""
        meminfo_output = """MemTotal:        8174592 kB
MemFree:         1234567 kB
MemAvailable:    5678901 kB
Buffers:          123456 kB
Cached:          2345678 kB
SwapTotal:       2097148 kB
SwapFree:        2097148 kB"""
        
        meminfo = memory_monitor._parse_meminfo(meminfo_output)
        
        assert meminfo["MemTotal"] == 8174592
        assert meminfo["MemFree"] == 1234567
        assert meminfo["MemAvailable"] == 5678901
        assert meminfo["SwapTotal"] == 2097148


class TestDiskMonitor:
    """磁碟監控器測試"""
    
    @pytest.fixture
    def disk_monitor(self, mock_executor, test_thresholds):
        return DiskMonitor(mock_executor, test_thresholds)
    
    @pytest.mark.asyncio
    async def test_collect_disk_metrics_success(self, disk_monitor, mock_executor, test_config):
        """測試成功收集磁碟監控數據"""
        # 模擬指令執行結果
        mock_executor.execute_command.side_effect = [
            # df -h
            CommandResult(command="df -h", stdout="df -h output", stderr="", exit_code=0, status=ExecutionStatus.SUCCESS),
            # df -B1
            CommandResult(
                command="df -B1",
                stdout="""Filesystem     1B-blocks      Used Available Use% Mounted on
/dev/sda1     500000000000 380000000000 120000000000  76% /
/dev/sda2     100000000000  50000000000  50000000000  50% /home""",
                stderr="",
                exit_code=0,
                status=ExecutionStatus.SUCCESS
            ),
            # iostat or /proc/diskstats
            CommandResult(
                command="iostat -x 1 1 2>/dev/null || cat /proc/diskstats",
                stdout="""   8       0 sda 12345 0 567890 12000 23456 0 789012 34000 0 45000 78000
   8       1 sda1 8901 0 234567 8000 12345 0 345678 20000 0 28000 45000""",
                stderr="",
                exit_code=0,
                status=ExecutionStatus.SUCCESS
            ),
            # lsblk
            CommandResult(
                command="lsblk -b -P 2>/dev/null || lsblk",
                stdout='NAME="sda" SIZE="500000000000" TYPE="disk" MOUNTPOINT=""\nNAME="sda1" SIZE="500000000000" TYPE="part" MOUNTPOINT="/"',
                stderr="",
                exit_code=0,
                status=ExecutionStatus.SUCCESS
            )
        ]
        
        # 執行監控數據收集
        result = await disk_monitor.collect_disk_metrics(test_config, server_id=1)
        
        # 驗證結果
        assert isinstance(result, MonitoringData)
        assert result.metric_type == MetricType.DISK
        assert result.server_id == 1
        assert "filesystems" in result.data
        assert "overall_usage_percent" in result.data
        assert "io_stats" in result.data
    
    def test_df_parsing(self, disk_monitor):
        """測試 df 輸出解析"""
        df_output = """Filesystem     1B-blocks      Used Available Use% Mounted on
/dev/sda1     500000000000 380000000000 120000000000  76% /
/dev/sda2     100000000000  50000000000  50000000000  50% /home
tmpfs          1000000000           0   1000000000   0% /tmp"""
        
        filesystems = disk_monitor._parse_df_bytes(df_output)
        
        # 應該過濾掉 tmpfs，只保留真實磁碟
        assert len(filesystems) == 2
        
        fs1 = next(fs for fs in filesystems if fs["mountpoint"] == "/")
        assert fs1["total_bytes"] == 500000000000
        assert fs1["used_bytes"] == 380000000000
        assert fs1["usage_percent"] == 76.0


class TestNetworkMonitor:
    """網路監控器測試"""
    
    @pytest.fixture
    def network_monitor(self, mock_executor, test_thresholds):
        return NetworkMonitor(mock_executor, test_thresholds)
    
    @pytest.mark.asyncio
    async def test_collect_network_metrics_success(self, network_monitor, mock_executor, test_config):
        """測試成功收集網路監控數據"""
        # 模擬指令執行結果
        mock_executor.execute_command.side_effect = [
            # cat /proc/net/dev
            CommandResult(
                command="cat /proc/net/dev",
                stdout="""Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 1234567890   123456    0    0    0     0          0         0  1234567890   123456    0    0    0     0       0          0
  eth0: 9876543210   987654    0    0    0     0          0         0  5432109876   543210    0    0    0     0       0          0""",
                stderr="",
                exit_code=0,
                status=ExecutionStatus.SUCCESS
            ),
            # ip addr show
            CommandResult(
                command="ip addr show",
                stdout="""1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    inet 127.0.0.1/8 scope host lo
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    inet 192.168.1.100/24 brd 192.168.1.255 scope global eth0""",
                stderr="",
                exit_code=0,
                status=ExecutionStatus.SUCCESS
            ),
            # ss -s
            CommandResult(
                command="ss -s",
                stdout="""Total: 123 (kernel 456)
TCP:   45 (estab 12, closed 8, orphaned 1, synrecv 0, timewait 7/0), ports 0
UDP:   78 (kernel 90)""",
                stderr="",
                exit_code=0,
                status=ExecutionStatus.SUCCESS
            ),
            # netstat -i
            CommandResult(
                command="netstat -i 2>/dev/null || cat /proc/net/dev",
                stdout="netstat output",
                stderr="",
                exit_code=0,
                status=ExecutionStatus.SUCCESS
            )
        ]
        
        # 執行監控數據收集
        result = await network_monitor.collect_network_metrics(test_config, server_id=1)
        
        # 驗證結果
        assert isinstance(result, MonitoringData)
        assert result.metric_type == MetricType.NETWORK
        assert result.server_id == 1
        assert "interfaces" in result.data
        assert "total_rx_bytes" in result.data
        assert "total_tx_bytes" in result.data
        assert "active_connections" in result.data
    
    def test_netdev_parsing(self, network_monitor):
        """測試 /proc/net/dev 解析"""
        netdev_output = """Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 1234567890   123456    0    0    0     0          0         0  1234567890   123456    0    0    0     0       0          0
  eth0: 9876543210   987654    1    2    0     0          0         0  5432109876   543210    3    4    0     0       0          0"""
        
        interfaces = network_monitor._parse_netdev(netdev_output, "test-host")
        
        assert "lo" in interfaces
        assert "eth0" in interfaces
        
        eth0 = interfaces["eth0"]
        assert eth0["rx_bytes"] == 9876543210
        assert eth0["tx_bytes"] == 5432109876
        assert eth0["rx_errors"] == 1
        assert eth0["tx_errors"] == 3


class TestMonitoringCollectorService:
    """監控收集服務測試"""
    
    @pytest.fixture
    def monitoring_service(self, test_thresholds):
        with patch('app.services.monitoring_collector.command_executor'):
            return MonitoringCollectorService(test_thresholds)
    
    @pytest.mark.asyncio
    async def test_collect_all_metrics(self, monitoring_service, test_config):
        """測試收集所有監控數據"""
        # Mock 各個監控器的方法
        with patch.object(monitoring_service.cpu_monitor, 'collect_cpu_metrics') as mock_cpu, \
             patch.object(monitoring_service.memory_monitor, 'collect_memory_metrics') as mock_memory, \
             patch.object(monitoring_service.disk_monitor, 'collect_disk_metrics') as mock_disk, \
             patch.object(monitoring_service.network_monitor, 'collect_network_metrics') as mock_network:
            
            # 設定 Mock 回傳值
            mock_cpu.return_value = MonitoringData(
                metric_type=MetricType.CPU,
                data={"usage_percent": 45.0, "core_count": 4},
                alert_level=AlertLevel.OK
            )
            mock_memory.return_value = MonitoringData(
                metric_type=MetricType.MEMORY,
                data={"usage_percent": 60.0, "total_bytes": 8589934592},
                alert_level=AlertLevel.OK
            )
            mock_disk.return_value = MonitoringData(
                metric_type=MetricType.DISK,
                data={"overall_usage_percent": 70.0},
                alert_level=AlertLevel.OK
            )
            mock_network.return_value = MonitoringData(
                metric_type=MetricType.NETWORK,
                data={"active_connections": 25},
                alert_level=AlertLevel.OK
            )
            
            # 執行收集
            results = await monitoring_service.collect_all_metrics(test_config, server_id=1)
            
            # 驗證結果
            assert len(results) == 4
            assert MetricType.CPU in results
            assert MetricType.MEMORY in results
            assert MetricType.DISK in results
            assert MetricType.NETWORK in results
            
            # 驗證每個監控器都被調用
            mock_cpu.assert_called_once()
            mock_memory.assert_called_once()
            mock_disk.assert_called_once()
            mock_network.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_collect_summary_metrics(self, monitoring_service, test_config):
        """測試收集監控摘要數據"""
        # Mock collect_all_metrics
        mock_results = {
            MetricType.CPU: MonitoringData(
                metric_type=MetricType.CPU,
                data={
                    "usage_percent": 42.0,
                    "core_count": 4,
                    "frequency_mhz": 2400.0,
                    "load_average": {"1min": 0.38, "5min": 0.45, "15min": 0.52},
                    "model_name": "Intel Core i5"
                },
                alert_level=AlertLevel.OK
            ),
            MetricType.MEMORY: MonitoringData(
                metric_type=MetricType.MEMORY,
                data={
                    "usage_percent": 68.0,
                    "total_bytes": 8589934592,  # 8GB
                    "used_bytes": 5838471782,
                    "cached_bytes": 1288490189
                },
                alert_level=AlertLevel.OK
            )
        }
        
        with patch.object(monitoring_service, 'collect_all_metrics', return_value=mock_results):
            summary = await monitoring_service.collect_summary_metrics(test_config, server_id=1)
            
            # 驗證摘要格式
            assert summary["server_id"] == 1
            assert summary["collection_status"] == "success"
            assert summary["overall_alert_level"] == AlertLevel.OK.value
            assert "metrics" in summary
            
            # 驗證 CPU 摘要
            cpu_summary = summary["metrics"]["cpu"]
            assert cpu_summary["usage_percent"] == 42.0
            assert cpu_summary["core_count"] == 4
            assert cpu_summary["model_name"] == "Intel Core i5"
            
            # 驗證記憶體摘要
            memory_summary = summary["metrics"]["memory"]
            assert memory_summary["usage_percent"] == 68.0
            assert memory_summary["total_gb"] == 8.0
    
    def test_update_thresholds(self, monitoring_service):
        """測試更新監控閾值"""
        new_thresholds = MonitoringThresholds(
            cpu_warning=75.0,
            cpu_critical=95.0,
            memory_warning=80.0,
            memory_critical=90.0
        )
        
        monitoring_service.update_thresholds(new_thresholds)
        
        # 驗證閾值已更新
        assert monitoring_service.thresholds.cpu_warning == 75.0
        assert monitoring_service.cpu_monitor.thresholds.cpu_warning == 75.0
        assert monitoring_service.memory_monitor.thresholds.memory_warning == 80.0
    
    @pytest.mark.asyncio
    async def test_test_connection_and_collect(self, monitoring_service, test_config):
        """測試連接測試和數據收集"""
        # Mock executor 的測試連接
        with patch.object(monitoring_service.executor, 'execute_command') as mock_execute, \
             patch.object(monitoring_service, 'collect_summary_metrics') as mock_summary:
            
            # 設定連接測試成功
            mock_execute.return_value = CommandResult(
                command="echo 'connection_test'",
                stdout="connection_test\n",
                stderr="",
                exit_code=0,
                status=ExecutionStatus.SUCCESS
            )
            
            # 設定摘要數據
            mock_summary.return_value = {
                "server_id": 1,
                "collection_status": "success",
                "metrics": {}
            }
            
            result = await monitoring_service.test_connection_and_collect(test_config, server_id=1)
            
            # 驗證結果
            assert result["connection_status"] == "success"
            assert result["collection_status"] == "success"
            
            # 驗證方法調用
            mock_execute.assert_called_once()
            mock_summary.assert_called_once()


class TestMonitoringThresholds:
    """監控閾值測試"""
    
    def test_default_thresholds(self):
        """測試預設閾值"""
        thresholds = MonitoringThresholds()
        
        assert thresholds.cpu_warning == 80.0
        assert thresholds.cpu_critical == 90.0
        assert thresholds.memory_warning == 85.0
        assert thresholds.memory_critical == 95.0
        assert thresholds.disk_warning == 85.0
        assert thresholds.disk_critical == 95.0
        assert thresholds.load_warning == 5.0
        assert thresholds.load_critical == 10.0
    
    def test_custom_thresholds(self):
        """測試自訂閾值"""
        thresholds = MonitoringThresholds(
            cpu_warning=70.0,
            cpu_critical=85.0,
            memory_warning=75.0,
            memory_critical=90.0
        )
        
        assert thresholds.cpu_warning == 70.0
        assert thresholds.cpu_critical == 85.0
        assert thresholds.memory_warning == 75.0
        assert thresholds.memory_critical == 90.0


@pytest.mark.asyncio
async def test_monitoring_data_serialization():
    """測試監控數據序列化"""
    data = MonitoringData(
        metric_type=MetricType.CPU,
        server_id=1,
        data={"usage_percent": 45.0, "core_count": 4},
        alert_level=AlertLevel.OK,
        alert_message=None,
        collection_time=1.23
    )
    
    # 測試轉換為字典
    dict_data = data.to_dict()
    
    assert dict_data["metric_type"] == "cpu"
    assert dict_data["server_id"] == 1
    assert dict_data["data"]["usage_percent"] == 45.0
    assert dict_data["alert_level"] == "ok"
    assert dict_data["collection_time"] == 1.23
    assert "timestamp" in dict_data