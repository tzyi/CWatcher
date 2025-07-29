"""
測試系統資訊收集器模組

測試硬體資訊、作業系統資訊和運行狀態收集功能
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.services.system_collector import (
    SystemInfoCollector, HardwareInfoCollector, OperatingSystemCollector,
    RuntimeStatusCollector, NetworkInfoCollector,
    SystemInfoType, SystemInfo
)
from app.services.command_executor import CommandExecutor, CommandResult, ExecutionStatus, CommandType
from app.services.ssh_manager import SSHConnectionConfig


class TestHardwareInfoCollector:
    """測試硬體資訊收集器"""
    
    def setup_method(self):
        """設置測試環境"""
        self.mock_executor = Mock(spec=CommandExecutor)
        self.collector = HardwareInfoCollector(self.mock_executor)
    
    async def test_collect_cpu_info_success(self):
        """測試成功收集 CPU 資訊"""
        # 模擬指令執行結果
        mock_cpu_result = CommandResult(
            command="lscpu",
            command_type=CommandType.HARDWARE_INFO,
            status=ExecutionStatus.SUCCESS,
            stdout="Architecture: x86_64\nCPU(s): 4\nModel name: Intel Core i5",
            parsed_data={"architecture": "x86_64", "cpu(s)": "4", "model_name": "Intel Core i5"}
        )
        
        mock_cores_result = CommandResult(
            command="cat /proc/cpuinfo | grep processor | wc -l",
            command_type=CommandType.HARDWARE_INFO,
            status=ExecutionStatus.SUCCESS,
            stdout="4"
        )
        
        mock_cpuinfo_result = CommandResult(
            command="cat /proc/cpuinfo",
            command_type=CommandType.HARDWARE_INFO,
            status=ExecutionStatus.SUCCESS,
            stdout="""processor	: 0
vendor_id	: GenuineIntel
cpu family	: 6
model		: 142
model name	: Intel(R) Core(TM) i5-8250U CPU @ 1.60GHz
stepping	: 10
microcode	: 0xca
cpu MHz		: 1800.000
cache size	: 6144 KB
flags		: fpu vme de pse"""
        )
        
        # 設置 mock 方法
        self.mock_executor.execute_predefined_command = AsyncMock(
            side_effect=[mock_cpu_result, mock_cores_result]
        )
        self.mock_executor.execute_command = AsyncMock(return_value=mock_cpuinfo_result)
        
        config = SSHConnectionConfig(host="localhost", username="test")
        result = await self.collector.collect_cpu_info(config)
        
        assert result["collection_status"] == "success"
        assert result["core_count"] == 4
        assert "cpu_model" in result
        assert "cpu_vendor" in result
        assert result["cpu_model"] == "Intel(R) Core(TM) i5-8250U CPU @ 1.60GHz"
        assert result["cpu_vendor"] == "GenuineIntel"
    
    async def test_collect_cpu_info_failure(self):
        """測試 CPU 資訊收集失敗"""
        # 模擬指令執行失敗
        mock_result = CommandResult(
            command="lscpu",
            command_type=CommandType.HARDWARE_INFO,
            status=ExecutionStatus.FAILED,
            error_message="Command not found"
        )
        
        self.mock_executor.execute_predefined_command = AsyncMock(return_value=mock_result)
        
        config = SSHConnectionConfig(host="localhost", username="test")
        result = await self.collector.collect_cpu_info(config)
        
        assert result["collection_status"] == "failed" or result["core_count"] == 0
    
    def test_parse_cpuinfo(self):
        """測試解析 /proc/cpuinfo"""
        cpuinfo_output = """processor	: 0
vendor_id	: GenuineIntel
cpu family	: 6
model		: 142
model name	: Intel(R) Core(TM) i5-8250U CPU @ 1.60GHz
stepping	: 10
microcode	: 0xca
cpu MHz		: 1800.000
cache size	: 6144 KB
flags		: fpu vme de pse tsc msr

processor	: 1
vendor_id	: GenuineIntel
cpu family	: 6
model		: 142
model name	: Intel(R) Core(TM) i5-8250U CPU @ 1.60GHz"""
        
        result = self.collector._parse_cpuinfo(cpuinfo_output)
        
        assert "cpu_model" in result
        assert "cpu_vendor" in result
        assert "processors" in result
        assert result["cpu_model"] == "Intel(R) Core(TM) i5-8250U CPU @ 1.60GHz"
        assert result["cpu_vendor"] == "GenuineIntel"
        assert len(result["processors"]) == 2
    
    async def test_collect_memory_info_success(self):
        """測試成功收集記憶體資訊"""
        mock_memory_result = CommandResult(
            command="free -m",
            command_type=CommandType.SYSTEM_METRICS,
            status=ExecutionStatus.SUCCESS,
            stdout="              total        used        free\nMem:           8192        4096        4096",
            parsed_data={"total": 8192, "used": 4096, "free": 4096, "unit": "MB"}
        )
        
        mock_meminfo_result = CommandResult(
            command="cat /proc/meminfo",
            command_type=CommandType.SYSTEM_METRICS,
            status=ExecutionStatus.SUCCESS,
            stdout="""MemTotal:        8388608 kB
MemFree:         4194304 kB
MemAvailable:    6291456 kB
Buffers:          524288 kB
Cached:          1048576 kB"""
        )
        
        self.mock_executor.execute_predefined_command = AsyncMock(
            side_effect=[mock_memory_result, mock_meminfo_result]
        )
        self.mock_executor.execute_command = AsyncMock(return_value=CommandResult(
            command="dmidecode -t memory",
            command_type=CommandType.HARDWARE_INFO,
            status=ExecutionStatus.SUCCESS,
            stdout="Memory Device info..."
        ))
        
        config = SSHConnectionConfig(host="localhost", username="test")
        result = await self.collector.collect_memory_info(config)
        
        assert result["collection_status"] == "success"
        assert "basic_info" in result
        assert "detailed_info" in result
        assert result["basic_info"]["total"] == 8192
    
    def test_parse_meminfo(self):
        """測試解析 /proc/meminfo"""
        meminfo_output = """MemTotal:        8388608 kB
MemFree:         4194304 kB
MemAvailable:    6291456 kB
Buffers:          524288 kB
Cached:          1048576 kB
SwapTotal:       2097152 kB
SwapFree:        2097152 kB"""
        
        result = self.collector._parse_meminfo(meminfo_output)
        
        assert "detailed_info" in result
        meminfo = result["detailed_info"]
        assert "memtotal" in meminfo
        assert "memfree" in meminfo
        assert meminfo["memtotal"]["value"] == 8388608
        assert meminfo["memtotal"]["unit"] == "kB"
    
    async def test_collect_storage_info_success(self):
        """測試成功收集儲存資訊"""
        mock_disk_result = CommandResult(
            command="df -h",
            command_type=CommandType.SYSTEM_METRICS,
            status=ExecutionStatus.SUCCESS,
            parsed_data={"filesystems": [
                {"filesystem": "/dev/sda1", "size": "50G", "used": "20G", "use_percent": "42%", "mounted_on": "/"}
            ]}
        )
        
        mock_lsblk_result = CommandResult(
            command="lsblk -J",
            command_type=CommandType.STORAGE,
            status=ExecutionStatus.SUCCESS,
            stdout='{"blockdevices": [{"name": "sda", "size": "100G", "type": "disk"}]}'
        )
        
        self.mock_executor.execute_predefined_command = AsyncMock(
            side_effect=[mock_disk_result, None]  # 第二個呼叫不會用到
        )
        self.mock_executor.execute_command = AsyncMock(
            side_effect=[mock_lsblk_result, CommandResult(command="mount", command_type=CommandType.STORAGE, status=ExecutionStatus.SUCCESS, stdout="/dev/sda1 on / type ext4"), CommandResult(command="cat /proc/diskstats", command_type=CommandType.SYSTEM_METRICS, status=ExecutionStatus.SUCCESS, stdout="8 0 sda 1000 0 8000 5000")]
        )
        
        config = SSHConnectionConfig(host="localhost", username="test")
        result = await self.collector.collect_storage_info(config)
        
        assert result["collection_status"] == "success"
        assert "disk_usage" in result
        assert "block_devices" in result


class TestOperatingSystemCollector:
    """測試作業系統資訊收集器"""
    
    def setup_method(self):
        """設置測試環境"""
        self.mock_executor = Mock(spec=CommandExecutor)
        self.collector = OperatingSystemCollector(self.mock_executor)
    
    async def test_collect_os_info_success(self):
        """測試成功收集作業系統資訊"""
        mock_uname_result = CommandResult(
            command="uname -a",
            command_type=CommandType.SYSTEM_INFO,
            status=ExecutionStatus.SUCCESS,
            parsed_data={"kernel_name": "Linux", "hostname": "web-server", "kernel_release": "5.4.0-42-generic"}
        )
        
        mock_hostname_result = CommandResult(
            command="hostname",
            command_type=CommandType.SYSTEM_INFO,
            status=ExecutionStatus.SUCCESS,
            stdout="web-server"
        )
        
        mock_os_release_result = CommandResult(
            command="lsb_release -a",
            command_type=CommandType.SYSTEM_INFO,
            status=ExecutionStatus.SUCCESS,
            stdout="""Distributor ID:	Ubuntu
Description:	Ubuntu 20.04 LTS
Release:	20.04
Codename:	focal"""
        )
        
        self.mock_executor.execute_predefined_command = AsyncMock(
            side_effect=[mock_uname_result, mock_hostname_result, mock_os_release_result, None]  # uptime 結果
        )
        self.mock_executor.execute_command = AsyncMock(return_value=CommandResult(
            command="cat /proc/version",
            command_type=CommandType.SYSTEM_INFO,
            status=ExecutionStatus.SUCCESS,
            stdout="Linux version 5.4.0-42-generic"
        ))
        
        config = SSHConnectionConfig(host="localhost", username="test")
        result = await self.collector.collect_os_info(config)
        
        assert result["collection_status"] == "success"
        assert "kernel_info" in result
        assert "hostname" in result
        assert "os_release" in result
        assert result["hostname"] == "web-server"
    
    def test_parse_os_release(self):
        """測試解析作業系統版本資訊"""
        # 測試 lsb_release 格式
        lsb_output = """Distributor ID:	Ubuntu
Description:	Ubuntu 20.04 LTS
Release:	20.04
Codename:	focal"""
        
        result = self.collector._parse_os_release(lsb_output)
        
        assert "distributor_id" in result
        assert "description" in result
        assert "release" in result
        assert result["distributor_id"] == "Ubuntu"
        assert result["description"] == "Ubuntu 20.04 LTS"
        
        # 測試 os-release 格式
        os_release_output = """NAME="Ubuntu"
VERSION="20.04 LTS (Focal Fossa)"
ID=ubuntu
ID_LIKE=debian
PRETTY_NAME="Ubuntu 20.04 LTS"
VERSION_ID="20.04"
HOME_URL="https://www.ubuntu.com/"
SUPPORT_URL="https://help.ubuntu.com/" """
        
        result = self.collector._parse_os_release(os_release_output)
        
        assert "name" in result
        assert "version" in result
        assert "id" in result
        assert result["name"] == "Ubuntu"
        assert result["id"] == "ubuntu"


class TestRuntimeStatusCollector:
    """測試運行狀態收集器"""
    
    def setup_method(self):
        """設置測試環境"""
        self.mock_executor = Mock(spec=CommandExecutor)
        self.collector = RuntimeStatusCollector(self.mock_executor)
    
    async def test_collect_runtime_status_success(self):
        """測試成功收集運行狀態"""
        mock_load_result = CommandResult(
            command="cat /proc/loadavg",
            command_type=CommandType.SYSTEM_METRICS,
            status=ExecutionStatus.SUCCESS,
            stdout="0.15 0.10 0.05 1/123 456"
        )
        
        mock_cpu_stat_result = CommandResult(
            command="cat /proc/stat | head -1",
            command_type=CommandType.SYSTEM_METRICS,
            status=ExecutionStatus.SUCCESS,
            stdout="cpu  1000 200 300 5000 100 50 25 0 0 0"
        )
        
        self.mock_executor.execute_predefined_command = AsyncMock(
            side_effect=[mock_load_result, mock_cpu_stat_result, None]  # memory_info 結果
        )
        self.mock_executor.execute_command = AsyncMock(
            side_effect=[
                CommandResult(command="ps aux --no-headers | wc -l", command_type=CommandType.PROCESS_INFO, status=ExecutionStatus.SUCCESS, stdout="150"),
                CommandResult(command="ss -tuln | wc -l", command_type=CommandType.NETWORK_INFO, status=ExecutionStatus.SUCCESS, stdout="25"),
                CommandResult(command="who | wc -l", command_type=CommandType.SYSTEM_INFO, status=ExecutionStatus.SUCCESS, stdout="2")
            ]
        )
        
        config = SSHConnectionConfig(host="localhost", username="test")
        result = await self.collector.collect_runtime_status(config)
        
        assert result["collection_status"] == "success"
        assert "load_average" in result
        assert "cpu_stat" in result
        assert "process_count" in result
        assert result["process_count"] == 150
        assert result["network_connections"] == 24  # 25 - 1 (標題行)
        assert result["logged_users"] == 2
    
    def test_parse_load_average(self):
        """測試解析負載平均值"""
        load_output = "0.15 0.10 0.05 1/123 456"
        result = self.collector._parse_load_average(load_output)
        
        assert result["1min"] == 0.15
        assert result["5min"] == 0.10
        assert result["15min"] == 0.05
        assert result["running_processes"] == "1/123"
        assert result["last_pid"] == 456
    
    def test_parse_cpu_stat(self):
        """測試解析 CPU 統計"""
        cpu_stat_output = "cpu  1000 200 300 5000 100 50 25 0 0 0"
        result = self.collector._parse_cpu_stat(cpu_stat_output)
        
        assert result["user"] == 1000
        assert result["nice"] == 200
        assert result["system"] == 300
        assert result["idle"] == 5000
        assert result["iowait"] == 100
        assert "total_time" in result
        assert result["total_time"] == sum([1000, 200, 300, 5000, 100, 50, 25, 0, 0, 0])


class TestNetworkInfoCollector:
    """測試網路資訊收集器"""
    
    def setup_method(self):
        """設置測試環境"""
        self.mock_executor = Mock(spec=CommandExecutor)
        self.collector = NetworkInfoCollector(self.mock_executor)
    
    async def test_collect_network_info_success(self):
        """測試成功收集網路資訊"""
        mock_netdev_result = CommandResult(
            command="cat /proc/net/dev",
            command_type=CommandType.NETWORK_INFO,
            status=ExecutionStatus.SUCCESS,
            stdout="""Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 1000000    1000    0    0    0     0          0         0  1000000    1000    0    0    0     0       0          0
  eth0: 5000000    5000    0    0    0     0          0         0  2000000    2000    0    0    0     0       0          0"""
        )
        
        self.mock_executor.execute_predefined_command = AsyncMock(return_value=mock_netdev_result)
        self.mock_executor.execute_command = AsyncMock(
            side_effect=[
                CommandResult(command="ip addr show", command_type=CommandType.NETWORK_INFO, status=ExecutionStatus.SUCCESS, stdout="1: lo: <LOOPBACK,UP,LOWER_UP>\n    inet 127.0.0.1/8 scope host lo\n2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP>\n    inet 192.168.1.100/24 scope global eth0"),
                CommandResult(command="ip route show", command_type=CommandType.NETWORK_INFO, status=ExecutionStatus.SUCCESS, stdout="default via 192.168.1.1 dev eth0\n192.168.1.0/24 dev eth0 scope link")
            ]
        )
        
        config = SSHConnectionConfig(host="localhost", username="test")
        result = await self.collector.collect_network_info(config)
        
        assert result["collection_status"] == "success"
        assert "interfaces" in result
        assert "ip_addresses" in result
        assert "routes" in result
    
    def test_parse_net_dev(self):
        """測試解析 /proc/net/dev"""
        netdev_output = """Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 1000000    1000    0    0    0     0          0         0  1000000    1000    0    0    0     0       0          0
  eth0: 5000000    5000    0    0    0     0          0         0  2000000    2000    0    0    0     0       0          0"""
        
        result = self.collector._parse_net_dev(netdev_output)
        
        assert "lo" in result
        assert "eth0" in result
        
        lo_stats = result["lo"]
        assert lo_stats["rx_bytes"] == 1000000
        assert lo_stats["rx_packets"] == 1000
        assert lo_stats["tx_bytes"] == 1000000
        assert lo_stats["tx_packets"] == 1000
        
        eth0_stats = result["eth0"]
        assert eth0_stats["rx_bytes"] == 5000000
        assert eth0_stats["tx_bytes"] == 2000000
    
    def test_parse_ip_addr(self):
        """測試解析 ip addr 輸出"""
        ip_output = """1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
    inet6 ::1/128 scope host
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP
    link/ether aa:bb:cc:dd:ee:ff brd ff:ff:ff:ff:ff:ff
    inet 192.168.1.100/24 brd 192.168.1.255 scope global eth0
    inet6 fe80::a8bb:ccff:fedd:eeff/64 scope link"""
        
        result = self.collector._parse_ip_addr(ip_output)
        
        assert len(result) == 2
        
        lo_interface = result[0]
        assert lo_interface["name"] == "lo"
        assert lo_interface["state"] == "UP"
        assert len(lo_interface["addresses"]) == 2  # IPv4 and IPv6
        
        eth0_interface = result[1]
        assert eth0_interface["name"] == "eth0"
        assert eth0_interface["state"] == "UP"
        assert len(eth0_interface["addresses"]) == 2


class TestSystemInfoCollector:
    """測試系統資訊收集器主類"""
    
    def setup_method(self):
        """設置測試環境"""
        self.mock_executor = Mock(spec=CommandExecutor)
        self.collector = SystemInfoCollector(self.mock_executor)
    
    @patch('app.services.system_collector.asyncio.gather')
    async def test_collect_complete_system_info(self, mock_gather):
        """測試收集完整系統資訊"""
        # 模擬各個收集器的結果
        mock_hardware_info = SystemInfo(
            info_type=SystemInfoType.HARDWARE,
            data={"cpu": {"core_count": 4}, "memory": {"total": 8192}},
            collection_time=1.5
        )
        
        mock_os_info = SystemInfo(
            info_type=SystemInfoType.OPERATING_SYSTEM,
            data={"hostname": "test-server", "os_release": {"name": "Ubuntu"}},
            collection_time=0.8
        )
        
        # 模擬 asyncio.gather 返回結果
        mock_gather.return_value = [mock_hardware_info, mock_os_info, None, None, None]
        
        config = SSHConnectionConfig(host="localhost", username="test")
        result = await self.collector.collect_complete_system_info(config)
        
        assert isinstance(result, dict)
        # 由於我們模擬了 gather，具體的結果取決於模擬設置
    
    async def test_collect_basic_system_info(self):
        """測試收集基本系統資訊"""
        # 模擬各個預定義指令的結果
        mock_results = [
            CommandResult(command="hostname", command_type=CommandType.SYSTEM_INFO, status=ExecutionStatus.SUCCESS, stdout="test-server"),
            CommandResult(command="uptime", command_type=CommandType.SYSTEM_INFO, status=ExecutionStatus.SUCCESS, parsed_data={"uptime_string": "1 day"}),
            CommandResult(command="lsb_release -a", command_type=CommandType.SYSTEM_INFO, status=ExecutionStatus.SUCCESS, stdout="Ubuntu 20.04"),
            CommandResult(command="free -m", command_type=CommandType.SYSTEM_METRICS, status=ExecutionStatus.SUCCESS, parsed_data={"total": 8192}),
            CommandResult(command="df -h", command_type=CommandType.SYSTEM_METRICS, status=ExecutionStatus.SUCCESS, parsed_data={"filesystems": []})
        ]
        
        with patch('asyncio.gather', return_value=mock_results):
            config = SSHConnectionConfig(host="localhost", username="test")
            result = await self.collector.collect_basic_system_info(config)
            
            assert "hostname" in result
            assert "uptime" in result
            assert "os_info" in result
            assert "memory" in result
            assert "disk" in result


class TestSystemInfo:
    """測試系統資訊數據結構"""
    
    def test_system_info_creation(self):
        """測試建立系統資訊對象"""
        timestamp = datetime.now()
        
        info = SystemInfo(
            info_type=SystemInfoType.HARDWARE,
            data={"cpu_count": 4, "memory_gb": 16},
            timestamp=timestamp,
            collection_time=2.5,
            server_info={"host": "localhost", "port": "22"}
        )
        
        assert info.info_type == SystemInfoType.HARDWARE
        assert info.data["cpu_count"] == 4
        assert info.data["memory_gb"] == 16
        assert info.timestamp == timestamp
        assert info.collection_time == 2.5
        assert info.server_info["host"] == "localhost"


# 整合測試
class TestSystemCollectorIntegration:
    """系統資訊收集器整合測試"""
    
    @pytest.mark.asyncio
    async def test_full_collection_flow(self):
        """測試完整的資訊收集流程"""
        # 這個測試需要實際的 SSH 連接，通常在整合測試中運行
        pass
    
    @pytest.mark.asyncio
    async def test_parallel_collection(self):
        """測試並行收集多種資訊"""
        # 測試同時收集多種系統資訊的性能和正確性
        pass
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self):
        """測試錯誤處理和恢復機制"""
        # 測試在部分收集失敗時的處理機制
        pass


if __name__ == "__main__":
    # 執行測試
    pytest.main([__file__, "-v"])