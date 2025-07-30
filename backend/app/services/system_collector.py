"""
CWatcher 系統資訊收集器

專門收集Linux系統的硬體資訊、作業系統資訊和運行狀態
支援結構化數據輸出和緩存機制
"""

import asyncio
import logging
import re
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from services.command_executor import CommandExecutor, CommandResult, ExecutionStatus
from services.ssh_manager import SSHConnectionConfig, ssh_manager
from core.config import settings


# 設定日誌
logger = logging.getLogger(__name__)


class SystemInfoType(Enum):
    """系統資訊類型"""
    HARDWARE = "hardware"
    OPERATING_SYSTEM = "operating_system"
    RUNTIME_STATUS = "runtime_status"
    NETWORK = "network"
    STORAGE = "storage"


@dataclass
class SystemInfo:
    """系統資訊結構"""
    info_type: SystemInfoType
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    collection_time: float = 0.0
    server_info: Optional[Dict[str, str]] = None


class HardwareInfoCollector:
    """硬體資訊收集器"""
    
    def __init__(self, executor: CommandExecutor):
        self.executor = executor
    
    async def collect_cpu_info(self, config: SSHConnectionConfig) -> Dict[str, Any]:
        """收集 CPU 資訊"""
        try:
            # 基本 CPU 資訊
            cpu_result = await self.executor.execute_predefined_command(config, "cpu_info")
            cores_result = await self.executor.execute_predefined_command(config, "cpu_cores")
            
            cpu_data = {
                "collection_status": "success",
                "details": cpu_result.parsed_data if cpu_result.parsed_data else {},
                "core_count": 0,
                "raw_info": cpu_result.stdout if cpu_result.status == ExecutionStatus.SUCCESS else ""
            }
            
            # 解析核心數
            if cores_result.status == ExecutionStatus.SUCCESS:
                try:
                    cpu_data["core_count"] = int(cores_result.stdout.strip())
                except ValueError:
                    cpu_data["core_count"] = 0
            
            # 從 /proc/cpuinfo 獲取詳細資訊
            cpuinfo_result = await self.executor.execute_command(
                config, "cat /proc/cpuinfo", timeout=15
            )
            
            if cpuinfo_result.status == ExecutionStatus.SUCCESS:
                cpu_data.update(self._parse_cpuinfo(cpuinfo_result.stdout))
            
            return cpu_data
            
        except Exception as e:
            logger.error(f"收集 CPU 資訊失敗: {e}")
            return {"collection_status": "failed", "error": str(e)}
    
    def _parse_cpuinfo(self, cpuinfo_output: str) -> Dict[str, Any]:
        """解析 /proc/cpuinfo"""
        try:
            processors = []
            current_processor = {}
            
            for line in cpuinfo_output.split('\n'):
                line = line.strip()
                if not line:
                    if current_processor:
                        processors.append(current_processor)
                        current_processor = {}
                    continue
                
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().replace(' ', '_').lower()
                    value = value.strip()
                    current_processor[key] = value
            
            # 添加最後一個處理器
            if current_processor:
                processors.append(current_processor)
            
            # 提取關鍵資訊
            if processors:
                first_cpu = processors[0]
                return {
                    "cpu_model": first_cpu.get("model_name", "Unknown"),
                    "cpu_vendor": first_cpu.get("vendor_id", "Unknown"),
                    "cpu_family": first_cpu.get("cpu_family", "Unknown"),
                    "cpu_stepping": first_cpu.get("stepping", "Unknown"),
                    "cpu_microcode": first_cpu.get("microcode", "Unknown"),
                    "cpu_cache_size": first_cpu.get("cache_size", "Unknown"),
                    "cpu_flags": first_cpu.get("flags", "").split(),
                    "cpu_mhz": first_cpu.get("cpu_mhz", "0"),
                    "processors": processors
                }
        except Exception as e:
            logger.warning(f"解析 /proc/cpuinfo 失敗: {e}")
        
        return {}
    
    async def collect_memory_info(self, config: SSHConnectionConfig) -> Dict[str, Any]:
        """收集記憶體資訊"""
        try:
            # 基本記憶體資訊
            memory_result = await self.executor.execute_predefined_command(config, "memory_info")
            
            memory_data = {
                "collection_status": "success",
                "basic_info": memory_result.parsed_data if memory_result.parsed_data else {},
                "raw_info": memory_result.stdout if memory_result.status == ExecutionStatus.SUCCESS else ""
            }
            
            # 詳細記憶體資訊
            meminfo_result = await self.executor.execute_predefined_command(config, "memory_detailed")
            
            if meminfo_result.status == ExecutionStatus.SUCCESS:
                memory_data.update(self._parse_meminfo(meminfo_result.stdout))
            
            # 記憶體硬體資訊（如果可用）
            dmidecode_result = await self.executor.execute_command(
                config, "dmidecode -t memory 2>/dev/null | head -50", timeout=20
            )
            
            if dmidecode_result.status == ExecutionStatus.SUCCESS:
                memory_data["hardware_info"] = self._parse_memory_hardware(dmidecode_result.stdout)
            
            return memory_data
            
        except Exception as e:
            logger.error(f"收集記憶體資訊失敗: {e}")
            return {"collection_status": "failed", "error": str(e)}
    
    def _parse_meminfo(self, meminfo_output: str) -> Dict[str, Any]:
        """解析 /proc/meminfo"""
        try:
            meminfo = {}
            for line in meminfo_output.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower().replace(' ', '_')
                    value = value.strip()
                    
                    # 嘗試提取數值（kB 單位）
                    if 'kb' in value.lower():
                        try:
                            num = int(re.search(r'\d+', value).group())
                            meminfo[key] = {"value": num, "unit": "kB", "bytes": num * 1024}
                        except:
                            meminfo[key] = value
                    else:
                        meminfo[key] = value
            
            return {"detailed_info": meminfo}
            
        except Exception as e:
            logger.warning(f"解析 /proc/meminfo 失敗: {e}")
            return {}
    
    def _parse_memory_hardware(self, dmidecode_output: str) -> Dict[str, Any]:
        """解析記憶體硬體資訊"""
        try:
            # 簡單解析 dmidecode 輸出
            hardware_info = {
                "slots": [],
                "total_slots": 0,
                "occupied_slots": 0
            }
            
            # 這裡可以進一步解析 dmidecode 輸出
            # 提取記憶體條的詳細資訊
            if "Memory Device" in dmidecode_output:
                hardware_info["dmidecode_available"] = True
                hardware_info["raw_output"] = dmidecode_output[:500]  # 限制長度
            
            return hardware_info
            
        except Exception as e:
            logger.warning(f"解析記憶體硬體資訊失敗: {e}")
            return {}
    
    async def collect_storage_info(self, config: SSHConnectionConfig) -> Dict[str, Any]:
        """收集儲存裝置資訊"""
        try:
            storage_data = {"collection_status": "success"}
            
            # 磁碟使用情況
            disk_result = await self.executor.execute_predefined_command(config, "disk_usage")
            if disk_result.status == ExecutionStatus.SUCCESS:
                storage_data["disk_usage"] = disk_result.parsed_data
            
            # 磁碟分割資訊
            lsblk_result = await self.executor.execute_command(
                config, "lsblk -J 2>/dev/null || lsblk", timeout=15
            )
            if lsblk_result.status == ExecutionStatus.SUCCESS:
                storage_data["block_devices"] = self._parse_lsblk(lsblk_result.stdout)
            
            # 檔案系統資訊
            mount_result = await self.executor.execute_command(
                config, "mount | grep '^/'", timeout=10
            )
            if mount_result.status == ExecutionStatus.SUCCESS:
                storage_data["mounted_filesystems"] = self._parse_mount(mount_result.stdout)
            
            # 磁碟 I/O 統計
            diskstats_result = await self.executor.execute_predefined_command(config, "disk_io")
            if diskstats_result.status == ExecutionStatus.SUCCESS:
                storage_data["io_stats"] = self._parse_diskstats(diskstats_result.stdout)
            
            return storage_data
            
        except Exception as e:
            logger.error(f"收集儲存資訊失敗: {e}")
            return {"collection_status": "failed", "error": str(e)}
    
    def _parse_lsblk(self, lsblk_output: str) -> Dict[str, Any]:
        """解析 lsblk 輸出"""
        try:
            # 嘗試解析 JSON 格式
            if lsblk_output.strip().startswith('{'):
                return json.loads(lsblk_output)
            
            # 解析文字格式
            devices = []
            for line in lsblk_output.split('\n')[1:]:  # 跳過標題
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 4:
                        device = {
                            "name": parts[0],
                            "size": parts[3] if len(parts) > 3 else "",
                            "type": parts[5] if len(parts) > 5 else "",
                            "mountpoint": parts[6] if len(parts) > 6 else ""
                        }
                        devices.append(device)
            
            return {"blockdevices": devices}
            
        except Exception as e:
            logger.warning(f"解析 lsblk 失敗: {e}")
            return {"raw_output": lsblk_output}
    
    def _parse_mount(self, mount_output: str) -> List[Dict[str, str]]:
        """解析 mount 輸出"""
        filesystems = []
        for line in mount_output.split('\n'):
            if line.strip():
                parts = line.split()
                if len(parts) >= 6:
                    fs = {
                        "device": parts[0],
                        "mountpoint": parts[2],
                        "filesystem": parts[4],
                        "options": parts[5][1:-1]  # 移除括號
                    }
                    filesystems.append(fs)
        return filesystems
    
    def _parse_diskstats(self, diskstats_output: str) -> Dict[str, Any]:
        """解析 /proc/diskstats"""
        try:
            stats = {}
            for line in diskstats_output.split('\n'):
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 14:
                        device = parts[2]
                        if not device.startswith('loop'):  # 忽略 loop 設備
                            stats[device] = {
                                "reads_completed": int(parts[3]),
                                "reads_merged": int(parts[4]),
                                "sectors_read": int(parts[5]),
                                "time_reading": int(parts[6]),
                                "writes_completed": int(parts[7]),
                                "writes_merged": int(parts[8]),
                                "sectors_written": int(parts[9]),
                                "time_writing": int(parts[10])
                            }
            return stats
            
        except Exception as e:
            logger.warning(f"解析 diskstats 失敗: {e}")
            return {}


class OperatingSystemCollector:
    """作業系統資訊收集器"""
    
    def __init__(self, executor: CommandExecutor):
        self.executor = executor
    
    async def collect_os_info(self, config: SSHConnectionConfig) -> Dict[str, Any]:
        """收集作業系統資訊"""
        try:
            os_data = {"collection_status": "success"}
            
            # 基本系統資訊
            uname_result = await self.executor.execute_predefined_command(config, "uname")
            if uname_result.status == ExecutionStatus.SUCCESS:
                os_data["kernel_info"] = uname_result.parsed_data
            
            # 主機名稱
            hostname_result = await self.executor.execute_predefined_command(config, "hostname")
            if hostname_result.status == ExecutionStatus.SUCCESS:
                os_data["hostname"] = hostname_result.stdout.strip()
            
            # 作業系統版本
            os_release_result = await self.executor.execute_predefined_command(config, "os_release")
            if os_release_result.status == ExecutionStatus.SUCCESS:
                os_data["os_release"] = self._parse_os_release(os_release_result.stdout)
            
            # 核心版本詳情
            version_result = await self.executor.execute_command(
                config, "cat /proc/version", timeout=10
            )
            if version_result.status == ExecutionStatus.SUCCESS:
                os_data["kernel_version"] = version_result.stdout.strip()
            
            # 系統啟動時間
            uptime_result = await self.executor.execute_predefined_command(config, "uptime")
            if uptime_result.status == ExecutionStatus.SUCCESS:
                os_data["uptime_info"] = uptime_result.parsed_data
            
            return os_data
            
        except Exception as e:
            logger.error(f"收集作業系統資訊失敗: {e}")
            return {"collection_status": "failed", "error": str(e)}
    
    def _parse_os_release(self, os_release_output: str) -> Dict[str, str]:
        """解析作業系統版本資訊"""
        try:
            os_info = {}
            
            # 解析 lsb_release 或 os-release 格式
            for line in os_release_output.split('\n'):
                line = line.strip()
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip().lower()
                    value = value.strip().strip('"')
                    os_info[key] = value
                elif ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower().replace(' ', '_')
                    value = value.strip()
                    os_info[key] = value
            
            return os_info
            
        except Exception as e:
            logger.warning(f"解析作業系統版本失敗: {e}")
            return {"raw_output": os_release_output}


class RuntimeStatusCollector:
    """運行狀態收集器"""
    
    def __init__(self, executor: CommandExecutor):
        self.executor = executor
    
    async def collect_runtime_status(self, config: SSHConnectionConfig) -> Dict[str, Any]:
        """收集系統運行狀態"""
        try:
            runtime_data = {"collection_status": "success"}
            
            # 系統負載
            load_result = await self.executor.execute_predefined_command(config, "load_average")
            if load_result.status == ExecutionStatus.SUCCESS:
                runtime_data["load_average"] = self._parse_load_average(load_result.stdout)
            
            # CPU 統計
            cpu_stat_result = await self.executor.execute_predefined_command(config, "cpu_stat")
            if cpu_stat_result.status == ExecutionStatus.SUCCESS:
                runtime_data["cpu_stat"] = self._parse_cpu_stat(cpu_stat_result.stdout)
            
            # 記憶體使用狀況
            memory_result = await self.executor.execute_predefined_command(config, "memory_info")
            if memory_result.status == ExecutionStatus.SUCCESS:
                runtime_data["memory_usage"] = memory_result.parsed_data
            
            # 進程統計
            ps_result = await self.executor.execute_command(
                config, "ps aux --no-headers | wc -l", timeout=10
            )
            if ps_result.status == ExecutionStatus.SUCCESS:
                try:
                    runtime_data["process_count"] = int(ps_result.stdout.strip())
                except ValueError:
                    runtime_data["process_count"] = 0
            
            # 網路連接統計
            netstat_result = await self.executor.execute_command(
                config, "ss -tuln | wc -l", timeout=10
            )
            if netstat_result.status == ExecutionStatus.SUCCESS:
                try:
                    runtime_data["network_connections"] = int(netstat_result.stdout.strip()) - 1  # 減去標題行
                except ValueError:
                    runtime_data["network_connections"] = 0
            
            # 系統用戶
            users_result = await self.executor.execute_command(
                config, "who | wc -l", timeout=5
            )
            if users_result.status == ExecutionStatus.SUCCESS:
                try:
                    runtime_data["logged_users"] = int(users_result.stdout.strip())
                except ValueError:
                    runtime_data["logged_users"] = 0
            
            return runtime_data
            
        except Exception as e:
            logger.error(f"收集運行狀態失敗: {e}")
            return {"collection_status": "failed", "error": str(e)}
    
    def _parse_load_average(self, load_output: str) -> Dict[str, float]:
        """解析負載平均值"""
        try:
            # /proc/loadavg 格式: 0.15 0.10 0.05 1/123 456
            parts = load_output.strip().split()
            if len(parts) >= 3:
                return {
                    "1min": float(parts[0]),
                    "5min": float(parts[1]),
                    "15min": float(parts[2]),
                    "running_processes": parts[3] if len(parts) > 3 else "0/0",
                    "last_pid": int(parts[4]) if len(parts) > 4 else 0
                }
        except Exception as e:
            logger.warning(f"解析負載平均值失敗: {e}")
        
        return {"raw_output": load_output}
    
    def _parse_cpu_stat(self, cpu_stat_output: str) -> Dict[str, Any]:
        """解析 CPU 統計資訊"""
        try:
            # /proc/stat 第一行格式: cpu user nice system idle iowait irq softirq steal guest guest_nice
            parts = cpu_stat_output.strip().split()
            if len(parts) >= 8 and parts[0] == 'cpu':
                total_time = sum(int(x) for x in parts[1:])
                return {
                    "user": int(parts[1]),
                    "nice": int(parts[2]),
                    "system": int(parts[3]),
                    "idle": int(parts[4]),
                    "iowait": int(parts[5]),
                    "irq": int(parts[6]),
                    "softirq": int(parts[7]),
                    "steal": int(parts[8]) if len(parts) > 8 else 0,
                    "guest": int(parts[9]) if len(parts) > 9 else 0,
                    "guest_nice": int(parts[10]) if len(parts) > 10 else 0,
                    "total_time": total_time
                }
        except Exception as e:
            logger.warning(f"解析 CPU 統計失敗: {e}")
        
        return {"raw_output": cpu_stat_output}


class NetworkInfoCollector:
    """網路資訊收集器"""
    
    def __init__(self, executor: CommandExecutor):
        self.executor = executor
    
    async def collect_network_info(self, config: SSHConnectionConfig) -> Dict[str, Any]:
        """收集網路資訊"""
        try:
            network_data = {"collection_status": "success"}
            
            # 網路介面統計
            netdev_result = await self.executor.execute_predefined_command(config, "network_interfaces")
            if netdev_result.status == ExecutionStatus.SUCCESS:
                network_data["interfaces"] = self._parse_net_dev(netdev_result.stdout)
            
            # IP 地址資訊
            ip_result = await self.executor.execute_command(
                config, "ip addr show", timeout=10
            )
            if ip_result.status == ExecutionStatus.SUCCESS:
                network_data["ip_addresses"] = self._parse_ip_addr(ip_result.stdout)
            
            # 路由表
            route_result = await self.executor.execute_command(
                config, "ip route show", timeout=10
            )
            if route_result.status == ExecutionStatus.SUCCESS:
                network_data["routes"] = self._parse_routes(route_result.stdout)
            
            return network_data
            
        except Exception as e:
            logger.error(f"收集網路資訊失敗: {e}")
            return {"collection_status": "failed", "error": str(e)}
    
    def _parse_net_dev(self, netdev_output: str) -> Dict[str, Dict[str, int]]:
        """解析 /proc/net/dev"""
        try:
            interfaces = {}
            lines = netdev_output.strip().split('\n')[2:]  # 跳過前兩行標題
            
            for line in lines:
                if ':' in line:
                    interface, stats = line.split(':', 1)
                    interface = interface.strip()
                    stats = stats.split()
                    
                    if len(stats) >= 16:
                        interfaces[interface] = {
                            "rx_bytes": int(stats[0]),
                            "rx_packets": int(stats[1]),
                            "rx_errors": int(stats[2]),
                            "rx_dropped": int(stats[3]),
                            "tx_bytes": int(stats[8]),
                            "tx_packets": int(stats[9]),
                            "tx_errors": int(stats[10]),
                            "tx_dropped": int(stats[11])
                        }
            
            return interfaces
            
        except Exception as e:
            logger.warning(f"解析網路介面統計失敗: {e}")
            return {}
    
    def _parse_ip_addr(self, ip_output: str) -> List[Dict[str, Any]]:
        """解析 ip addr 輸出"""
        try:
            interfaces = []
            current_interface = None
            
            for line in ip_output.split('\n'):
                line = line.strip()
                
                # 介面行
                if re.match(r'^\d+:', line):
                    if current_interface:
                        interfaces.append(current_interface)
                    
                    parts = line.split()
                    interface_name = parts[1].rstrip(':')
                    current_interface = {
                        "name": interface_name,
                        "state": "UP" if "UP" in line else "DOWN",
                        "addresses": []
                    }
                
                # IP 地址行
                elif line.startswith('inet ') or line.startswith('inet6 '):
                    if current_interface:
                        parts = line.split()
                        if len(parts) >= 2:
                            current_interface["addresses"].append({
                                "type": "ipv4" if line.startswith('inet ') else "ipv6",
                                "address": parts[1],
                                "scope": parts[3] if len(parts) > 3 else ""
                            })
            
            # 添加最後一個介面
            if current_interface:
                interfaces.append(current_interface)
            
            return interfaces
        
        except Exception as e:
            logger.warning(f"解析 IP 地址失敗: {e}")
            return []
    
    def _parse_routes(self, route_output: str) -> List[Dict[str, str]]:
        """解析路由表"""
        try:
            routes = []
            for line in route_output.split('\n'):
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 3:
                        route = {
                            "destination": parts[0],
                            "via": "",
                            "dev": "",
                            "scope": ""
                        }
                        
                        # 解析路由參數
                        for i, part in enumerate(parts):
                            if part == "via" and i + 1 < len(parts):
                                route["via"] = parts[i + 1]
                            elif part == "dev" and i + 1 < len(parts):
                                route["dev"] = parts[i + 1]
                            elif part == "scope" and i + 1 < len(parts):
                                route["scope"] = parts[i + 1]
                        
                        routes.append(route)
            
            return routes
            
        except Exception as e:
            logger.warning(f"解析路由表失敗: {e}")
            return []


class SystemInfoCollector:
    """系統資訊收集器主類"""
    
    def __init__(self, executor: CommandExecutor):
        self.executor = executor
        self.hardware_collector = HardwareInfoCollector(executor)
        self.os_collector = OperatingSystemCollector(executor)
        self.runtime_collector = RuntimeStatusCollector(executor)
        self.network_collector = NetworkInfoCollector(executor)
    
    async def collect_complete_system_info(
        self, 
        config: SSHConnectionConfig
    ) -> Dict[SystemInfoType, SystemInfo]:
        """收集完整的系統資訊"""
        results = {}
        server_info = {
            "host": config.host,
            "port": str(config.port),
            "username": config.username
        }
        
        # 並行收集各類資訊
        tasks = {
            SystemInfoType.HARDWARE: self._collect_hardware_info(config, server_info),
            SystemInfoType.OPERATING_SYSTEM: self._collect_os_info(config, server_info),
            SystemInfoType.RUNTIME_STATUS: self._collect_runtime_info(config, server_info),
            SystemInfoType.NETWORK: self._collect_network_info(config, server_info),
            SystemInfoType.STORAGE: self._collect_storage_info(config, server_info)
        }
        
        # 等待所有任務完成
        completed_tasks = await asyncio.gather(*tasks.values(), return_exceptions=True)
        
        # 組織結果
        for i, (info_type, task) in enumerate(tasks.items()):
            result = completed_tasks[i]
            if isinstance(result, Exception):
                logger.error(f"收集 {info_type.value} 資訊失敗: {result}")
                results[info_type] = SystemInfo(
                    info_type=info_type,
                    data={"collection_status": "failed", "error": str(result)},
                    server_info=server_info
                )
            else:
                results[info_type] = result
        
        return results
    
    async def _collect_hardware_info(self, config: SSHConnectionConfig, server_info: Dict[str, str]) -> SystemInfo:
        """收集硬體資訊"""
        start_time = time.time()
        
        # 並行收集硬體資訊
        cpu_task = self.hardware_collector.collect_cpu_info(config)
        memory_task = self.hardware_collector.collect_memory_info(config)
        
        cpu_info, memory_info = await asyncio.gather(cpu_task, memory_task, return_exceptions=True)
        
        data = {
            "cpu": cpu_info if not isinstance(cpu_info, Exception) else {"collection_status": "failed", "error": str(cpu_info)},
            "memory": memory_info if not isinstance(memory_info, Exception) else {"collection_status": "failed", "error": str(memory_info)}
        }
        
        return SystemInfo(
            info_type=SystemInfoType.HARDWARE,
            data=data,
            collection_time=time.time() - start_time,
            server_info=server_info
        )
    
    async def _collect_os_info(self, config: SSHConnectionConfig, server_info: Dict[str, str]) -> SystemInfo:
        """收集作業系統資訊"""
        start_time = time.time()
        data = await self.os_collector.collect_os_info(config)
        
        return SystemInfo(
            info_type=SystemInfoType.OPERATING_SYSTEM,
            data=data,
            collection_time=time.time() - start_time,
            server_info=server_info
        )
    
    async def _collect_runtime_info(self, config: SSHConnectionConfig, server_info: Dict[str, str]) -> SystemInfo:
        """收集運行狀態資訊"""
        start_time = time.time()
        data = await self.runtime_collector.collect_runtime_status(config)
        
        return SystemInfo(
            info_type=SystemInfoType.RUNTIME_STATUS,
            data=data,
            collection_time=time.time() - start_time,
            server_info=server_info
        )
    
    async def _collect_network_info(self, config: SSHConnectionConfig, server_info: Dict[str, str]) -> SystemInfo:
        """收集網路資訊"""
        start_time = time.time()
        data = await self.network_collector.collect_network_info(config)
        
        return SystemInfo(
            info_type=SystemInfoType.NETWORK,
            data=data,
            collection_time=time.time() - start_time,
            server_info=server_info
        )
    
    async def _collect_storage_info(self, config: SSHConnectionConfig, server_info: Dict[str, str]) -> SystemInfo:
        """收集儲存資訊"""
        start_time = time.time()
        data = await self.hardware_collector.collect_storage_info(config)
        
        return SystemInfo(
            info_type=SystemInfoType.STORAGE,
            data=data,
            collection_time=time.time() - start_time,
            server_info=server_info
        )
    
    async def collect_basic_system_info(self, config: SSHConnectionConfig) -> Dict[str, Any]:
        """收集基本系統資訊（快速版本）"""
        try:
            # 只收集最基本的資訊
            basic_commands = {
                "hostname": self.executor.execute_predefined_command(config, "hostname"),
                "uptime": self.executor.execute_predefined_command(config, "uptime"),
                "os_info": self.executor.execute_predefined_command(config, "os_release"),
                "memory": self.executor.execute_predefined_command(config, "memory_info"),
                "disk": self.executor.execute_predefined_command(config, "disk_usage")
            }
            
            results = await asyncio.gather(*basic_commands.values(), return_exceptions=True)
            
            basic_info = {}
            for key, result in zip(basic_commands.keys(), results):
                if isinstance(result, Exception):
                    basic_info[key] = {"status": "failed", "error": str(result)}
                elif result.status == ExecutionStatus.SUCCESS:
                    basic_info[key] = {
                        "status": "success",
                        "data": result.parsed_data or result.stdout.strip()
                    }
                else:
                    basic_info[key] = {
                        "status": "failed",
                        "error": result.error_message or "執行失敗"
                    }
            
            return basic_info
            
        except Exception as e:
            logger.error(f"收集基本系統資訊失敗: {e}")
            return {"collection_status": "failed", "error": str(e)}


# 全域系統資訊收集器實例
from services.command_executor import command_executor
system_collector = SystemInfoCollector(command_executor)


# 便利函數
async def collect_server_system_info(server_data: Dict[str, Any]) -> Dict[SystemInfoType, SystemInfo]:
    """收集伺服器系統資訊的便利函數"""
    config = ssh_manager.decrypt_server_credentials(server_data)
    return await system_collector.collect_complete_system_info(config)


async def collect_server_basic_info(server_data: Dict[str, Any]) -> Dict[str, Any]:
    """收集伺服器基本資訊的便利函數"""
    config = ssh_manager.decrypt_server_credentials(server_data)
    return await system_collector.collect_basic_system_info(config)


async def update_server_system_info(server_id: int) -> Dict[str, Any]:
    """更新特定伺服器的系統資訊"""
    try:
        # 檢查SSH連接
        if not ssh_manager.is_connected(server_id):
            await ssh_manager.connect_to_server(server_id)
        
        # 取得伺服器配置
        config = ssh_manager.get_server_config(server_id)
        if not config:
            raise ValueError(f"無法取得伺服器 {server_id} 的配置")
        
        # 收集基本系統資訊（較快速的更新）
        basic_info = await system_collector.collect_basic_system_info(config)
        
        result = {
            "server_id": server_id,
            "update_time": datetime.now().isoformat(),
            "info_collected": len(basic_info),
            "status": "success"
        }
        
        logger.debug(f"伺服器 {server_id} 系統資訊更新完成")
        return result
        
    except Exception as e:
        logger.error(f"更新伺服器 {server_id} 系統資訊失敗: {e}")
        return {
            "server_id": server_id,
            "update_time": datetime.now().isoformat(),
            "status": "failed",
            "error": str(e)
        }


if __name__ == "__main__":
    # 測試系統資訊收集器
    import asyncio
    
    async def test_system_collector():
        print("📊 測試系統資訊收集器...")
        
        # 測試配置
        test_config = SSHConnectionConfig(
            host="localhost",
            port=22,
            username="test",
            password="test123"
        )
        
        try:
            # 測試基本資訊收集
            basic_info = await system_collector.collect_basic_system_info(test_config)
            print(f"基本資訊收集完成: {len(basic_info)} 項")
            
            # 測試完整資訊收集
            complete_info = await system_collector.collect_complete_system_info(test_config)
            print(f"完整資訊收集完成: {len(complete_info)} 類別")
            
            for info_type, info in complete_info.items():
                print(f"- {info_type.value}: 收集時間 {info.collection_time:.2f}s")
            
        except Exception as e:
            print(f"測試失敗: {e}")
    
    # 執行測試
    asyncio.run(test_system_collector())