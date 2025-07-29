"""
CWatcher 監控數據收集器

專門收集 Linux 系統的即時監控數據：CPU、記憶體、磁碟、網路
支援警告閾值檢查、數據聚合和時序數據存儲
"""

import asyncio
import logging
import time
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from app.services.command_executor import CommandExecutor, CommandResult, ExecutionStatus
from app.services.ssh_manager import SSHConnectionConfig, ssh_manager
from app.core.config import settings

# 設定日誌
logger = logging.getLogger(__name__)


class MetricType(Enum):
    """監控指標類型"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"


class AlertLevel(Enum):
    """警告等級"""
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class MonitoringThresholds:
    """監控閾值配置"""
    cpu_warning: float = 80.0     # CPU使用率警告閾值 (%)
    cpu_critical: float = 90.0    # CPU使用率嚴重閾值 (%)
    memory_warning: float = 85.0  # 記憶體使用率警告閾值 (%)
    memory_critical: float = 95.0 # 記憶體使用率嚴重閾值 (%)
    disk_warning: float = 85.0    # 磁碟使用率警告閾值 (%)
    disk_critical: float = 95.0   # 磁碟使用率嚴重閾值 (%)
    load_warning: float = 5.0     # 負載平均值警告閾值
    load_critical: float = 10.0   # 負載平均值嚴重閾值


@dataclass
class MonitoringData:
    """監控數據結構"""
    metric_type: MetricType
    server_id: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)
    alert_level: AlertLevel = AlertLevel.OK
    alert_message: Optional[str] = None
    collection_time: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            "metric_type": self.metric_type.value,
            "server_id": self.server_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "alert_level": self.alert_level.value,
            "alert_message": self.alert_message,
            "collection_time": self.collection_time
        }


class CPUMonitor:
    """CPU 監控器"""
    
    def __init__(self, executor: CommandExecutor, thresholds: MonitoringThresholds):
        self.executor = executor
        self.thresholds = thresholds
        self._last_cpu_stats = {}  # 儲存上次的 CPU 統計數據用於計算使用率
    
    async def collect_cpu_metrics(self, config: SSHConnectionConfig, server_id: Optional[int] = None) -> MonitoringData:
        """收集 CPU 監控數據"""
        start_time = time.time()
        
        try:
            # 並行收集 CPU 相關數據
            tasks = {
                "cpu_stat": self.executor.execute_command(config, "cat /proc/stat", timeout=10),
                "cpu_info": self.executor.execute_command(config, "lscpu", timeout=10),
                "load_avg": self.executor.execute_command(config, "cat /proc/loadavg", timeout=5),
                "uptime": self.executor.execute_command(config, "uptime", timeout=5)
            }
            
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            
            # 解析結果
            cpu_data = {}
            for i, (key, task) in enumerate(tasks.items()):
                result = results[i]
                if isinstance(result, Exception):
                    logger.warning(f"收集 {key} 失敗: {result}")
                    cpu_data[key] = {"status": "failed", "error": str(result)}
                elif result.status == ExecutionStatus.SUCCESS:
                    cpu_data[key] = {"status": "success", "data": result.stdout.strip()}
                else:
                    cpu_data[key] = {"status": "failed", "error": result.error_message}
            
            # 解析和計算 CPU 指標
            processed_data = await self._process_cpu_data(cpu_data, config.host)
            
            # 檢查警告閾值
            alert_level, alert_message = self._check_cpu_alerts(processed_data)
            
            return MonitoringData(
                metric_type=MetricType.CPU,
                server_id=server_id,
                data=processed_data,
                alert_level=alert_level,
                alert_message=alert_message,
                collection_time=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"收集 CPU 監控數據失敗: {e}")
            return MonitoringData(
                metric_type=MetricType.CPU,
                server_id=server_id,
                data={"collection_status": "failed", "error": str(e)},
                alert_level=AlertLevel.UNKNOWN,
                alert_message=f"數據收集失敗: {e}",
                collection_time=time.time() - start_time
            )
    
    async def _process_cpu_data(self, raw_data: Dict[str, Any], host: str) -> Dict[str, Any]:
        """處理和計算 CPU 數據"""
        processed = {
            "collection_status": "success",
            "usage_percent": 0.0,
            "core_count": 0,
            "frequency_mhz": 0.0,
            "load_average": {"1min": 0.0, "5min": 0.0, "15min": 0.0},
            "model_name": "Unknown",
            "architecture": "Unknown",
            "raw_stats": {}
        }
        
        try:
            # 解析 CPU 統計數據計算使用率
            if raw_data.get("cpu_stat", {}).get("status") == "success":
                cpu_stats = self._parse_cpu_stat(raw_data["cpu_stat"]["data"])
                processed["raw_stats"] = cpu_stats
                
                # 計算 CPU 使用率
                cpu_usage = self._calculate_cpu_usage(cpu_stats, host)
                processed["usage_percent"] = round(cpu_usage, 2)
            
            # 解析 CPU 資訊
            if raw_data.get("cpu_info", {}).get("status") == "success":
                cpu_info = self._parse_lscpu(raw_data["cpu_info"]["data"])
                processed.update({
                    "core_count": cpu_info.get("cpu_cores", 0),
                    "frequency_mhz": cpu_info.get("cpu_max_mhz", 0.0),
                    "model_name": cpu_info.get("model_name", "Unknown"),
                    "architecture": cpu_info.get("architecture", "Unknown")
                })
            
            # 解析負載平均值
            if raw_data.get("load_avg", {}).get("status") == "success":
                load_data = self._parse_load_average(raw_data["load_avg"]["data"])
                processed["load_average"] = load_data
            
            # 解析系統運行時間
            if raw_data.get("uptime", {}).get("status") == "success":
                uptime_data = self._parse_uptime(raw_data["uptime"]["data"])
                processed["uptime"] = uptime_data
                
        except Exception as e:
            logger.error(f"處理 CPU 數據失敗: {e}")
            processed["collection_status"] = "partial"
            processed["processing_error"] = str(e)
        
        return processed
    
    def _parse_cpu_stat(self, cpu_stat_output: str) -> Dict[str, Any]:
        """解析 /proc/stat 輸出"""
        try:
            # 第一行是總體 CPU 統計
            first_line = cpu_stat_output.split('\n')[0]
            parts = first_line.split()
            
            if len(parts) >= 8 and parts[0] == 'cpu':
                stats = {
                    "user": int(parts[1]),
                    "nice": int(parts[2]),
                    "system": int(parts[3]),
                    "idle": int(parts[4]),
                    "iowait": int(parts[5]),
                    "irq": int(parts[6]),
                    "softirq": int(parts[7]),
                    "steal": int(parts[8]) if len(parts) > 8 else 0,
                    "guest": int(parts[9]) if len(parts) > 9 else 0,
                    "guest_nice": int(parts[10]) if len(parts) > 10 else 0
                }
                
                # 計算總時間
                stats["total"] = sum(stats.values())
                return stats
        except Exception as e:
            logger.warning(f"解析 CPU 統計失敗: {e}")
        
        return {}
    
    def _parse_lscpu(self, lscpu_output: str) -> Dict[str, Any]:
        """解析 lscpu 輸出"""
        info = {}
        try:
            for line in lscpu_output.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower().replace(' ', '_').replace('(s)', '')
                    value = value.strip()
                    
                    # 處理特定欄位
                    if key == "cpu":
                        try:
                            info["cpu_cores"] = int(value)
                        except ValueError:
                            pass
                    elif key == "cpu_max_mhz":
                        try:
                            info["cpu_max_mhz"] = float(value)
                        except ValueError:
                            pass
                    elif key == "model_name":
                        info["model_name"] = value
                    elif key == "architecture":
                        info["architecture"] = value
                    
                    info[key] = value
        except Exception as e:
            logger.warning(f"解析 lscpu 失敗: {e}")
        
        return info
    
    def _parse_load_average(self, load_output: str) -> Dict[str, float]:
        """解析負載平均值"""
        try:
            # /proc/loadavg 格式: 0.15 0.10 0.05 1/123 456
            parts = load_output.strip().split()
            if len(parts) >= 3:
                return {
                    "1min": float(parts[0]),
                    "5min": float(parts[1]),
                    "15min": float(parts[2])
                }
        except Exception as e:
            logger.warning(f"解析負載平均值失敗: {e}")
        
        return {"1min": 0.0, "5min": 0.0, "15min": 0.0}
    
    def _parse_uptime(self, uptime_output: str) -> Dict[str, Any]:
        """解析系統運行時間"""
        try:
            # uptime 格式示例: " 10:30:00 up 1 day,  2:15,  1 user,  load average: 0.00, 0.01, 0.05"
            uptime_info = {}
            
            if "up " in uptime_output:
                # 提取運行時間部分
                up_part = uptime_output.split("up ")[1].split(",")[0].strip()
                uptime_info["uptime_string"] = up_part
            
            if "user" in uptime_output:
                # 提取用戶數
                import re
                user_match = re.search(r'(\d+)\s+user', uptime_output)
                if user_match:
                    uptime_info["logged_users"] = int(user_match.group(1))
            
            return uptime_info
            
        except Exception as e:
            logger.warning(f"解析 uptime 失敗: {e}")
            return {}
    
    def _calculate_cpu_usage(self, current_stats: Dict[str, Any], host: str) -> float:
        """計算 CPU 使用率"""
        if not current_stats or "total" not in current_stats:
            return 0.0
        
        try:
            # 取得上次的統計數據
            last_stats = self._last_cpu_stats.get(host, {})
            
            if not last_stats or "total" not in last_stats:
                # 第一次收集，無法計算使用率
                self._last_cpu_stats[host] = current_stats
                return 0.0
            
            # 計算時間差
            total_diff = current_stats["total"] - last_stats["total"]
            idle_diff = current_stats["idle"] - last_stats["idle"]
            
            if total_diff <= 0:
                return 0.0
            
            # 計算使用率
            cpu_usage = ((total_diff - idle_diff) / total_diff) * 100
            
            # 更新上次統計數據
            self._last_cpu_stats[host] = current_stats
            
            return max(0.0, min(100.0, cpu_usage))  # 確保在 0-100 範圍內
            
        except Exception as e:
            logger.warning(f"計算 CPU 使用率失敗: {e}")
            return 0.0
    
    def _check_cpu_alerts(self, cpu_data: Dict[str, Any]) -> Tuple[AlertLevel, Optional[str]]:
        """檢查 CPU 警告閾值"""
        try:
            usage = cpu_data.get("usage_percent", 0.0)
            load_1min = cpu_data.get("load_average", {}).get("1min", 0.0)
            
            # 檢查 CPU 使用率
            if usage >= self.thresholds.cpu_critical:
                return AlertLevel.CRITICAL, f"CPU使用率過高: {usage:.1f}%"
            elif usage >= self.thresholds.cpu_warning:
                return AlertLevel.WARNING, f"CPU使用率偏高: {usage:.1f}%"
            
            # 檢查負載平均值
            if load_1min >= self.thresholds.load_critical:
                return AlertLevel.CRITICAL, f"系統負載過高: {load_1min:.2f}"
            elif load_1min >= self.thresholds.load_warning:
                return AlertLevel.WARNING, f"系統負載偏高: {load_1min:.2f}"
            
            return AlertLevel.OK, None
            
        except Exception as e:
            logger.warning(f"檢查 CPU 警告失敗: {e}")
            return AlertLevel.UNKNOWN, f"警告檢查失敗: {e}"


class MemoryMonitor:
    """記憶體監控器"""
    
    def __init__(self, executor: CommandExecutor, thresholds: MonitoringThresholds):
        self.executor = executor
        self.thresholds = thresholds
    
    async def collect_memory_metrics(self, config: SSHConnectionConfig, server_id: Optional[int] = None) -> MonitoringData:
        """收集記憶體監控數據"""
        start_time = time.time()
        
        try:
            # 並行收集記憶體相關數據
            tasks = {
                "meminfo": self.executor.execute_command(config, "cat /proc/meminfo", timeout=10),
                "free": self.executor.execute_command(config, "free -b", timeout=5)
            }
            
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            
            # 解析結果
            memory_data = {}
            for i, (key, task) in enumerate(tasks.items()):
                result = results[i]
                if isinstance(result, Exception):
                    logger.warning(f"收集 {key} 失敗: {result}")
                    memory_data[key] = {"status": "failed", "error": str(result)}
                elif result.status == ExecutionStatus.SUCCESS:
                    memory_data[key] = {"status": "success", "data": result.stdout.strip()}
                else:
                    memory_data[key] = {"status": "failed", "error": result.error_message}
            
            # 處理記憶體數據
            processed_data = await self._process_memory_data(memory_data)
            
            # 檢查警告閾值
            alert_level, alert_message = self._check_memory_alerts(processed_data)
            
            return MonitoringData(
                metric_type=MetricType.MEMORY,
                server_id=server_id,
                data=processed_data,
                alert_level=alert_level,
                alert_message=alert_message,
                collection_time=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"收集記憶體監控數據失敗: {e}")
            return MonitoringData(
                metric_type=MetricType.MEMORY,
                server_id=server_id,
                data={"collection_status": "failed", "error": str(e)},
                alert_level=AlertLevel.UNKNOWN,
                alert_message=f"數據收集失敗: {e}",
                collection_time=time.time() - start_time
            )
    
    async def _process_memory_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """處理記憶體數據"""
        processed = {
            "collection_status": "success",
            "total_bytes": 0,
            "used_bytes": 0,
            "free_bytes": 0,
            "available_bytes": 0,
            "cached_bytes": 0,
            "buffers_bytes": 0,
            "usage_percent": 0.0,
            "swap_total_bytes": 0,
            "swap_used_bytes": 0,
            "swap_free_bytes": 0,
            "swap_usage_percent": 0.0
        }
        
        try:
            # 解析 /proc/meminfo
            if raw_data.get("meminfo", {}).get("status") == "success":
                meminfo = self._parse_meminfo(raw_data["meminfo"]["data"])
                
                # 轉換基本記憶體數據 (從 kB 轉為 bytes)
                processed.update({
                    "total_bytes": meminfo.get("MemTotal", 0) * 1024,
                    "free_bytes": meminfo.get("MemFree", 0) * 1024,
                    "available_bytes": meminfo.get("MemAvailable", meminfo.get("MemFree", 0)) * 1024,
                    "cached_bytes": meminfo.get("Cached", 0) * 1024,
                    "buffers_bytes": meminfo.get("Buffers", 0) * 1024,
                    "swap_total_bytes": meminfo.get("SwapTotal", 0) * 1024,
                    "swap_free_bytes": meminfo.get("SwapFree", 0) * 1024
                })
                
                # 計算使用量
                total = processed["total_bytes"]
                available = processed["available_bytes"]
                processed["used_bytes"] = total - available
                processed["swap_used_bytes"] = processed["swap_total_bytes"] - processed["swap_free_bytes"]
                
                # 計算使用率
                if total > 0:
                    processed["usage_percent"] = round((processed["used_bytes"] / total) * 100, 2)
                
                if processed["swap_total_bytes"] > 0:
                    processed["swap_usage_percent"] = round(
                        (processed["swap_used_bytes"] / processed["swap_total_bytes"]) * 100, 2
                    )
            
            # 解析 free 命令輸出作為驗證
            if raw_data.get("free", {}).get("status") == "success":
                free_data = self._parse_free(raw_data["free"]["data"])
                processed["free_command_data"] = free_data
                
        except Exception as e:
            logger.error(f"處理記憶體數據失敗: {e}")
            processed["collection_status"] = "partial"
            processed["processing_error"] = str(e)
        
        return processed
    
    def _parse_meminfo(self, meminfo_output: str) -> Dict[str, int]:
        """解析 /proc/meminfo"""
        meminfo = {}
        try:
            for line in meminfo_output.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # 提取數值 (通常是 kB)
                    import re
                    num_match = re.search(r'(\d+)', value)
                    if num_match:
                        meminfo[key] = int(num_match.group(1))
        except Exception as e:
            logger.warning(f"解析 meminfo 失敗: {e}")
        
        return meminfo
    
    def _parse_free(self, free_output: str) -> Dict[str, Any]:
        """解析 free 命令輸出"""
        try:
            lines = free_output.strip().split('\n')
            if len(lines) >= 2:
                # 記憶體行
                mem_line = lines[1].split()
                if len(mem_line) >= 7:
                    return {
                        "total": int(mem_line[1]),
                        "used": int(mem_line[2]),
                        "free": int(mem_line[3]),
                        "shared": int(mem_line[4]),
                        "buff_cache": int(mem_line[5]),
                        "available": int(mem_line[6])
                    }
        except Exception as e:
            logger.warning(f"解析 free 輸出失敗: {e}")
        
        return {}
    
    def _check_memory_alerts(self, memory_data: Dict[str, Any]) -> Tuple[AlertLevel, Optional[str]]:
        """檢查記憶體警告閾值"""
        try:
            usage = memory_data.get("usage_percent", 0.0)
            swap_usage = memory_data.get("swap_usage_percent", 0.0)
            
            # 檢查記憶體使用率
            if usage >= self.thresholds.memory_critical:
                return AlertLevel.CRITICAL, f"記憶體使用率過高: {usage:.1f}%"
            elif usage >= self.thresholds.memory_warning:
                return AlertLevel.WARNING, f"記憶體使用率偏高: {usage:.1f}%"
            
            # 檢查 Swap 使用率
            if swap_usage >= 50.0:  # Swap 使用率超過 50% 就警告
                return AlertLevel.WARNING, f"Swap使用率偏高: {swap_usage:.1f}%"
            
            return AlertLevel.OK, None
            
        except Exception as e:
            logger.warning(f"檢查記憶體警告失敗: {e}")
            return AlertLevel.UNKNOWN, f"警告檢查失敗: {e}"


class DiskMonitor:
    """磁碟監控器"""
    
    def __init__(self, executor: CommandExecutor, thresholds: MonitoringThresholds):
        self.executor = executor
        self.thresholds = thresholds
        self._last_io_stats = {}  # 儲存上次的 I/O 統計數據
    
    async def collect_disk_metrics(self, config: SSHConnectionConfig, server_id: Optional[int] = None) -> MonitoringData:
        """收集磁碟監控數據"""
        start_time = time.time()
        
        try:
            # 並行收集磁碟相關數據
            tasks = {
                "df": self.executor.execute_command(config, "df -h", timeout=10),
                "df_bytes": self.executor.execute_command(config, "df -B1", timeout=10),
                "iostat": self.executor.execute_command(config, "iostat -x 1 1 2>/dev/null || cat /proc/diskstats", timeout=15),
                "lsblk": self.executor.execute_command(config, "lsblk -b -P 2>/dev/null || lsblk", timeout=10)
            }
            
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            
            # 解析結果
            disk_data = {}
            for i, (key, task) in enumerate(tasks.items()):
                result = results[i]
                if isinstance(result, Exception):
                    logger.warning(f"收集 {key} 失敗: {result}")
                    disk_data[key] = {"status": "failed", "error": str(result)}
                elif result.status == ExecutionStatus.SUCCESS:
                    disk_data[key] = {"status": "success", "data": result.stdout.strip()}
                else:
                    disk_data[key] = {"status": "failed", "error": result.error_message}
            
            # 處理磁碟數據
            processed_data = await self._process_disk_data(disk_data, config.host)
            
            # 檢查警告閾值
            alert_level, alert_message = self._check_disk_alerts(processed_data)
            
            return MonitoringData(
                metric_type=MetricType.DISK,
                server_id=server_id,
                data=processed_data,
                alert_level=alert_level,
                alert_message=alert_message,
                collection_time=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"收集磁碟監控數據失敗: {e}")
            return MonitoringData(
                metric_type=MetricType.DISK,
                server_id=server_id,
                data={"collection_status": "failed", "error": str(e)},
                alert_level=AlertLevel.UNKNOWN,
                alert_message=f"數據收集失敗: {e}",
                collection_time=time.time() - start_time
            )
    
    async def _process_disk_data(self, raw_data: Dict[str, Any], host: str) -> Dict[str, Any]:
        """處理磁碟數據"""
        processed = {
            "collection_status": "success",
            "filesystems": [],
            "total_space_bytes": 0,
            "used_space_bytes": 0,
            "free_space_bytes": 0,
            "overall_usage_percent": 0.0,
            "io_stats": {},
            "block_devices": []
        }
        
        try:
            # 解析磁碟使用量 (df)
            if raw_data.get("df_bytes", {}).get("status") == "success":
                filesystems = self._parse_df_bytes(raw_data["df_bytes"]["data"])
                processed["filesystems"] = filesystems
                
                # 計算總體使用情況
                total_space = sum(fs.get("total_bytes", 0) for fs in filesystems)
                used_space = sum(fs.get("used_bytes", 0) for fs in filesystems)
                free_space = sum(fs.get("free_bytes", 0) for fs in filesystems)
                
                processed.update({
                    "total_space_bytes": total_space,
                    "used_space_bytes": used_space,
                    "free_space_bytes": free_space,
                    "overall_usage_percent": round((used_space / total_space * 100) if total_space > 0 else 0, 2)
                })
            
            # 解析 I/O 統計
            if raw_data.get("iostat", {}).get("status") == "success":
                io_stats = self._parse_io_stats(raw_data["iostat"]["data"], host)
                processed["io_stats"] = io_stats
            
            # 解析塊設備信息
            if raw_data.get("lsblk", {}).get("status") == "success":
                block_devices = self._parse_lsblk_disk(raw_data["lsblk"]["data"])
                processed["block_devices"] = block_devices
                
        except Exception as e:
            logger.error(f"處理磁碟數據失敗: {e}")
            processed["collection_status"] = "partial"
            processed["processing_error"] = str(e)
        
        return processed
    
    def _parse_df_bytes(self, df_output: str) -> List[Dict[str, Any]]:
        """解析 df 輸出 (bytes 格式)"""
        filesystems = []
        try:
            lines = df_output.strip().split('\n')[1:]  # 跳過標題行
            
            for line in lines:
                parts = line.split()
                if len(parts) >= 6:
                    # 過濾掉特殊文件系統
                    filesystem = parts[0]
                    mountpoint = parts[5]
                    
                    if (not filesystem.startswith('/dev/') or 
                        mountpoint in ['/dev', '/sys', '/proc', '/run'] or
                        'snap' in filesystem):
                        continue
                    
                    try:
                        total_bytes = int(parts[1])
                        used_bytes = int(parts[2])
                        free_bytes = int(parts[3])
                        usage_percent = float(parts[4].rstrip('%'))
                        
                        filesystems.append({
                            "filesystem": filesystem,
                            "mountpoint": mountpoint,
                            "total_bytes": total_bytes,
                            "used_bytes": used_bytes,
                            "free_bytes": free_bytes,
                            "usage_percent": usage_percent
                        })
                    except ValueError:
                        continue
                        
        except Exception as e:
            logger.warning(f"解析 df 輸出失敗: {e}")
        
        return filesystems
    
    def _parse_io_stats(self, iostat_output: str, host: str) -> Dict[str, Any]:
        """解析 I/O 統計數據"""
        io_data = {}
        
        try:
            # 嘗試解析 iostat 輸出
            if "Device" in iostat_output and "r/s" in iostat_output:
                # iostat 格式
                lines = iostat_output.strip().split('\n')
                header_found = False
                
                for line in lines:
                    if "Device" in line:
                        header_found = True
                        continue
                    
                    if header_found and line.strip():
                        parts = line.split()
                        if len(parts) >= 10:
                            device = parts[0]
                            try:
                                io_data[device] = {
                                    "reads_per_sec": float(parts[3]),
                                    "writes_per_sec": float(parts[4]),
                                    "read_kb_per_sec": float(parts[5]),
                                    "write_kb_per_sec": float(parts[6]),
                                    "util_percent": float(parts[9])
                                }
                            except (ValueError, IndexError):
                                continue
            
            else:
                # 解析 /proc/diskstats 格式
                io_data = self._parse_diskstats(iostat_output, host)
            
        except Exception as e:
            logger.warning(f"解析 I/O 統計失敗: {e}")
        
        return io_data
    
    def _parse_diskstats(self, diskstats_output: str, host: str) -> Dict[str, Any]:
        """解析 /proc/diskstats"""
        current_stats = {}
        
        try:
            for line in diskstats_output.split('\n'):
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 14:
                        device = parts[2]
                        
                        # 過濾掉 loop 設備和分區
                        if device.startswith('loop') or device.startswith('ram'):
                            continue
                        
                        current_stats[device] = {
                            "reads_completed": int(parts[3]),
                            "sectors_read": int(parts[5]),
                            "writes_completed": int(parts[7]),
                            "sectors_written": int(parts[9]),
                            "io_time_ms": int(parts[12])
                        }
            
            # 計算速率 (需要與上次數據比較)
            last_stats = self._last_io_stats.get(host, {})
            calculated_stats = {}
            
            for device, stats in current_stats.items():
                if device in last_stats:
                    last = last_stats[device]
                    
                    # 計算差值 (假設間隔為 1 秒)
                    reads_diff = stats["reads_completed"] - last["reads_completed"]
                    writes_diff = stats["writes_completed"] - last["writes_completed"]
                    sectors_read_diff = stats["sectors_read"] - last["sectors_read"]
                    sectors_written_diff = stats["sectors_written"] - last["sectors_written"]
                    
                    calculated_stats[device] = {
                        "reads_per_sec": max(0, reads_diff),
                        "writes_per_sec": max(0, writes_diff),
                        "read_kb_per_sec": max(0, sectors_read_diff * 512 / 1024),  # 扇區轉 KB
                        "write_kb_per_sec": max(0, sectors_written_diff * 512 / 1024),
                        "raw_stats": stats
                    }
            
            # 更新上次統計
            self._last_io_stats[host] = current_stats
            
            return calculated_stats if calculated_stats else current_stats
            
        except Exception as e:
            logger.warning(f"解析 diskstats 失敗: {e}")
            return {}
    
    def _parse_lsblk_disk(self, lsblk_output: str) -> List[Dict[str, Any]]:
        """解析 lsblk 輸出"""
        devices = []
        
        try:
            # 嘗試解析 -P 格式 (key=value)
            if '=' in lsblk_output:
                for line in lsblk_output.split('\n'):
                    if line.strip():
                        device_info = {}
                        # 解析 key="value" 格式
                        import re
                        matches = re.findall(r'(\w+)="([^"]*)"', line)
                        for key, value in matches:
                            device_info[key.lower()] = value
                        
                        if device_info:
                            devices.append(device_info)
            else:
                # 解析標準格式
                lines = lsblk_output.strip().split('\n')
                if len(lines) > 1:
                    for line in lines[1:]:  # 跳過標題
                        parts = line.split()
                        if len(parts) >= 4:
                            devices.append({
                                "name": parts[0],
                                "size": parts[3] if len(parts) > 3 else "",
                                "type": parts[5] if len(parts) > 5 else "",
                                "mountpoint": parts[6] if len(parts) > 6 else ""
                            })
        
        except Exception as e:
            logger.warning(f"解析 lsblk 失敗: {e}")
        
        return devices
    
    def _check_disk_alerts(self, disk_data: Dict[str, Any]) -> Tuple[AlertLevel, Optional[str]]:
        """檢查磁碟警告閾值"""
        try:
            overall_usage = disk_data.get("overall_usage_percent", 0.0)
            filesystems = disk_data.get("filesystems", [])
            
            # 檢查整體使用率
            if overall_usage >= self.thresholds.disk_critical:
                return AlertLevel.CRITICAL, f"磁碟使用率過高: {overall_usage:.1f}%"
            elif overall_usage >= self.thresholds.disk_warning:
                return AlertLevel.WARNING, f"磁碟使用率偏高: {overall_usage:.1f}%"
            
            # 檢查個別文件系統
            for fs in filesystems:
                usage = fs.get("usage_percent", 0.0)
                mountpoint = fs.get("mountpoint", "")
                
                if usage >= self.thresholds.disk_critical:
                    return AlertLevel.CRITICAL, f"文件系統 {mountpoint} 使用率過高: {usage:.1f}%"
                elif usage >= self.thresholds.disk_warning:
                    return AlertLevel.WARNING, f"文件系統 {mountpoint} 使用率偏高: {usage:.1f}%"
            
            return AlertLevel.OK, None
            
        except Exception as e:
            logger.warning(f"檢查磁碟警告失敗: {e}")
            return AlertLevel.UNKNOWN, f"警告檢查失敗: {e}"


class NetworkMonitor:
    """網路監控器"""
    
    def __init__(self, executor: CommandExecutor, thresholds: MonitoringThresholds):
        self.executor = executor
        self.thresholds = thresholds
        self._last_network_stats = {}  # 儲存上次的網路統計數據
    
    async def collect_network_metrics(self, config: SSHConnectionConfig, server_id: Optional[int] = None) -> MonitoringData:
        """收集網路監控數據"""
        start_time = time.time()
        
        try:
            # 並行收集網路相關數據
            tasks = {
                "netdev": self.executor.execute_command(config, "cat /proc/net/dev", timeout=10),
                "ip_addr": self.executor.execute_command(config, "ip addr show", timeout=10),
                "ss": self.executor.execute_command(config, "ss -s", timeout=5),
                "netstat": self.executor.execute_command(config, "netstat -i 2>/dev/null || cat /proc/net/dev", timeout=10)
            }
            
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            
            # 解析結果
            network_data = {}
            for i, (key, task) in enumerate(tasks.items()):
                result = results[i]
                if isinstance(result, Exception):
                    logger.warning(f"收集 {key} 失敗: {result}")
                    network_data[key] = {"status": "failed", "error": str(result)}
                elif result.status == ExecutionStatus.SUCCESS:
                    network_data[key] = {"status": "success", "data": result.stdout.strip()}
                else:
                    network_data[key] = {"status": "failed", "error": result.error_message}
            
            # 處理網路數據
            processed_data = await self._process_network_data(network_data, config.host)
            
            # 檢查警告閾值
            alert_level, alert_message = self._check_network_alerts(processed_data)
            
            return MonitoringData(
                metric_type=MetricType.NETWORK,
                server_id=server_id,
                data=processed_data,
                alert_level=alert_level,
                alert_message=alert_message,
                collection_time=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"收集網路監控數據失敗: {e}")
            return MonitoringData(
                metric_type=MetricType.NETWORK,
                server_id=server_id,
                data={"collection_status": "failed", "error": str(e)},
                alert_level=AlertLevel.UNKNOWN,
                alert_message=f"數據收集失敗: {e}",
                collection_time=time.time() - start_time
            )
    
    async def _process_network_data(self, raw_data: Dict[str, Any], host: str) -> Dict[str, Any]:
        """處理網路數據"""
        processed = {
            "collection_status": "success",
            "interfaces": {},
            "total_rx_bytes": 0,
            "total_tx_bytes": 0,
            "total_rx_packets": 0,
            "total_tx_packets": 0,
            "rx_speed_bps": 0.0,
            "tx_speed_bps": 0.0,
            "active_connections": 0,
            "ip_addresses": []
        }
        
        try:
            # 解析網路介面統計
            if raw_data.get("netdev", {}).get("status") == "success":
                interfaces = self._parse_netdev(raw_data["netdev"]["data"], host)
                processed["interfaces"] = interfaces
                
                # 計算總計 (排除 lo 介面)
                for iface, stats in interfaces.items():
                    if iface != "lo":
                        processed["total_rx_bytes"] += stats.get("rx_bytes", 0)
                        processed["total_tx_bytes"] += stats.get("tx_bytes", 0)
                        processed["total_rx_packets"] += stats.get("rx_packets", 0)
                        processed["total_tx_packets"] += stats.get("tx_packets", 0)
                        processed["rx_speed_bps"] += stats.get("rx_speed_bps", 0.0)
                        processed["tx_speed_bps"] += stats.get("tx_speed_bps", 0.0)
            
            # 解析 IP 地址
            if raw_data.get("ip_addr", {}).get("status") == "success":
                ip_addresses = self._parse_ip_addresses(raw_data["ip_addr"]["data"])
                processed["ip_addresses"] = ip_addresses
            
            # 解析連接統計
            if raw_data.get("ss", {}).get("status") == "success":
                connections = self._parse_ss_stats(raw_data["ss"]["data"])
                processed["active_connections"] = connections.get("total", 0)
                processed["connection_stats"] = connections
            
        except Exception as e:
            logger.error(f"處理網路數據失敗: {e}")
            processed["collection_status"] = "partial"
            processed["processing_error"] = str(e)
        
        return processed
    
    def _parse_netdev(self, netdev_output: str, host: str) -> Dict[str, Dict[str, Any]]:
        """解析 /proc/net/dev"""
        interfaces = {}
        current_stats = {}
        
        try:
            lines = netdev_output.strip().split('\n')[2:]  # 跳過前兩行標題
            
            for line in lines:
                if ':' in line:
                    interface, stats = line.split(':', 1)
                    interface = interface.strip()
                    stats = stats.split()
                    
                    if len(stats) >= 16:
                        current_stats[interface] = {
                            "rx_bytes": int(stats[0]),
                            "rx_packets": int(stats[1]),
                            "rx_errors": int(stats[2]),
                            "rx_dropped": int(stats[3]),
                            "tx_bytes": int(stats[8]),
                            "tx_packets": int(stats[9]),
                            "tx_errors": int(stats[10]),
                            "tx_dropped": int(stats[11])
                        }
            
            # 計算速率 (與上次數據比較)
            last_stats = self._last_network_stats.get(host, {})
            
            for interface, stats in current_stats.items():
                calculated_stats = dict(stats)  # 複製基本統計
                
                if interface in last_stats:
                    last = last_stats[interface]
                    time_diff = 1.0  # 假設 1 秒間隔
                    
                    # 計算速率 (bytes per second)
                    rx_diff = stats["rx_bytes"] - last["rx_bytes"]
                    tx_diff = stats["tx_bytes"] - last["tx_bytes"]
                    
                    calculated_stats.update({
                        "rx_speed_bps": max(0.0, rx_diff / time_diff),
                        "tx_speed_bps": max(0.0, tx_diff / time_diff),
                        "rx_speed_mbps": max(0.0, rx_diff / time_diff / 1024 / 1024),
                        "tx_speed_mbps": max(0.0, tx_diff / time_diff / 1024 / 1024)
                    })
                else:
                    calculated_stats.update({
                        "rx_speed_bps": 0.0,
                        "tx_speed_bps": 0.0,
                        "rx_speed_mbps": 0.0,
                        "tx_speed_mbps": 0.0
                    })
                
                interfaces[interface] = calculated_stats
            
            # 更新上次統計
            self._last_network_stats[host] = current_stats
            
        except Exception as e:
            logger.warning(f"解析網路介面統計失敗: {e}")
        
        return interfaces
    
    def _parse_ip_addresses(self, ip_output: str) -> List[Dict[str, Any]]:
        """解析 ip addr 輸出"""
        interfaces = []
        current_interface = None
        
        try:
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
                        "mtu": 0,
                        "addresses": []
                    }
                    
                    # 提取 MTU
                    if "mtu" in line:
                        try:
                            mtu_idx = parts.index("mtu")
                            if mtu_idx + 1 < len(parts):
                                current_interface["mtu"] = int(parts[mtu_idx + 1])
                        except (ValueError, IndexError):
                            pass
                
                # IP 地址行
                elif line.startswith('inet ') or line.startswith('inet6 '):
                    if current_interface:
                        parts = line.split()
                        if len(parts) >= 2:
                            addr_info = {
                                "type": "ipv4" if line.startswith('inet ') else "ipv6",
                                "address": parts[1],
                                "scope": ""
                            }
                            
                            # 提取 scope
                            if "scope" in parts:
                                try:
                                    scope_idx = parts.index("scope")
                                    if scope_idx + 1 < len(parts):
                                        addr_info["scope"] = parts[scope_idx + 1]
                                except (ValueError, IndexError):
                                    pass
                            
                            current_interface["addresses"].append(addr_info)
            
            # 添加最後一個介面
            if current_interface:
                interfaces.append(current_interface)
                
        except Exception as e:
            logger.warning(f"解析 IP 地址失敗: {e}")
        
        return interfaces
    
    def _parse_ss_stats(self, ss_output: str) -> Dict[str, int]:
        """解析 ss -s 輸出"""
        stats = {"total": 0}
        
        try:
            for line in ss_output.split('\n'):
                line = line.strip().lower()
                
                if "total:" in line:
                    # 提取總連接數
                    import re
                    match = re.search(r'total:\s*(\d+)', line)
                    if match:
                        stats["total"] = int(match.group(1))
                
                elif "tcp:" in line:
                    # TCP 連接統計
                    match = re.search(r'tcp:\s*(\d+)', line)
                    if match:
                        stats["tcp"] = int(match.group(1))
                
                elif "udp:" in line:
                    # UDP 連接統計
                    match = re.search(r'udp:\s*(\d+)', line)
                    if match:
                        stats["udp"] = int(match.group(1))
                        
        except Exception as e:
            logger.warning(f"解析連接統計失敗: {e}")
        
        return stats
    
    def _check_network_alerts(self, network_data: Dict[str, Any]) -> Tuple[AlertLevel, Optional[str]]:
        """檢查網路警告閾值"""
        try:
            # 檢查介面錯誤
            interfaces = network_data.get("interfaces", {})
            
            for iface, stats in interfaces.items():
                if iface == "lo":  # 跳過回環介面
                    continue
                
                rx_errors = stats.get("rx_errors", 0)
                tx_errors = stats.get("tx_errors", 0)
                rx_dropped = stats.get("rx_dropped", 0)
                tx_dropped = stats.get("tx_dropped", 0)
                
                total_errors = rx_errors + tx_errors + rx_dropped + tx_dropped
                
                if total_errors > 100:  # 錯誤數量過多
                    return AlertLevel.WARNING, f"網路介面 {iface} 錯誤數量過多: {total_errors}"
            
            # 檢查網路速度 (可以設定閾值)
            # 這裡可以根據需要添加速度警告邏輯
            
            return AlertLevel.OK, None
            
        except Exception as e:
            logger.warning(f"檢查網路警告失敗: {e}")
            return AlertLevel.UNKNOWN, f"警告檢查失敗: {e}"


# 全域監控閾值設定
default_thresholds = MonitoringThresholds()

# 便利函數
async def collect_cpu_monitoring_data(config: SSHConnectionConfig, server_id: Optional[int] = None) -> MonitoringData:
    """收集 CPU 監控數據的便利函數"""
    from app.services.command_executor import command_executor
    monitor = CPUMonitor(command_executor, default_thresholds)
    return await monitor.collect_cpu_metrics(config, server_id)


async def collect_memory_monitoring_data(config: SSHConnectionConfig, server_id: Optional[int] = None) -> MonitoringData:
    """收集記憶體監控數據的便利函數"""
    from app.services.command_executor import command_executor
    monitor = MemoryMonitor(command_executor, default_thresholds)
    return await monitor.collect_memory_metrics(config, server_id)


async def collect_disk_monitoring_data(config: SSHConnectionConfig, server_id: Optional[int] = None) -> MonitoringData:
    """收集磁碟監控數據的便利函數"""
    from app.services.command_executor import command_executor
    monitor = DiskMonitor(command_executor, default_thresholds)
    return await monitor.collect_disk_metrics(config, server_id)


async def collect_network_monitoring_data(config: SSHConnectionConfig, server_id: Optional[int] = None) -> MonitoringData:
    """收集網路監控數據的便利函數"""
    from app.services.command_executor import command_executor
    monitor = NetworkMonitor(command_executor, default_thresholds)
    return await monitor.collect_network_metrics(config, server_id)


class MonitoringCollectorService:
    """監控數據收集主服務"""
    
    def __init__(self, thresholds: Optional[MonitoringThresholds] = None):
        from app.services.command_executor import command_executor
        self.executor = command_executor
        self.thresholds = thresholds or default_thresholds
        
        # 初始化各監控器
        self.cpu_monitor = CPUMonitor(self.executor, self.thresholds)
        self.memory_monitor = MemoryMonitor(self.executor, self.thresholds)
        self.disk_monitor = DiskMonitor(self.executor, self.thresholds)
        self.network_monitor = NetworkMonitor(self.executor, self.thresholds)
    
    async def collect_all_metrics(
        self, 
        config: SSHConnectionConfig, 
        server_id: Optional[int] = None,
        metrics_types: Optional[List[MetricType]] = None
    ) -> Dict[MetricType, MonitoringData]:
        """收集所有監控數據"""
        
        # 預設收集所有類型
        if metrics_types is None:
            metrics_types = [MetricType.CPU, MetricType.MEMORY, MetricType.DISK, MetricType.NETWORK]
        
        # 建立收集任務
        tasks = {}
        
        if MetricType.CPU in metrics_types:
            tasks[MetricType.CPU] = self.cpu_monitor.collect_cpu_metrics(config, server_id)
        
        if MetricType.MEMORY in metrics_types:
            tasks[MetricType.MEMORY] = self.memory_monitor.collect_memory_metrics(config, server_id)
        
        if MetricType.DISK in metrics_types:
            tasks[MetricType.DISK] = self.disk_monitor.collect_disk_metrics(config, server_id)
        
        if MetricType.NETWORK in metrics_types:
            tasks[MetricType.NETWORK] = self.network_monitor.collect_network_metrics(config, server_id)
        
        # 並行執行所有收集任務
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        
        # 組織結果
        collected_data = {}
        for i, (metric_type, task) in enumerate(tasks.items()):
            result = results[i]
            if isinstance(result, Exception):
                logger.error(f"收集 {metric_type.value} 監控數據失敗: {result}")
                collected_data[metric_type] = MonitoringData(
                    metric_type=metric_type,
                    server_id=server_id,
                    data={"collection_status": "failed", "error": str(result)},
                    alert_level=AlertLevel.UNKNOWN,
                    alert_message=f"收集失敗: {result}"
                )
            else:
                collected_data[metric_type] = result
        
        return collected_data
    
    async def collect_summary_metrics(
        self, 
        config: SSHConnectionConfig, 
        server_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """收集監控數據摘要 (符合UI需求格式)"""
        
        try:
            # 收集所有監控數據
            all_data = await self.collect_all_metrics(config, server_id)
            
            # 建立符合UI原型需求的摘要數據
            summary = {
                "server_id": server_id,
                "timestamp": datetime.now().isoformat(),
                "collection_status": "success",
                "overall_alert_level": AlertLevel.OK.value,
                "metrics": {}
            }
            
            # 處理 CPU 數據
            if MetricType.CPU in all_data:
                cpu_data = all_data[MetricType.CPU]
                summary["metrics"]["cpu"] = {
                    "usage_percent": cpu_data.data.get("usage_percent", 0.0),
                    "core_count": cpu_data.data.get("core_count", 0),
                    "frequency_mhz": cpu_data.data.get("frequency_mhz", 0.0),
                    "load_average": cpu_data.data.get("load_average", {}),
                    "model_name": cpu_data.data.get("model_name", "Unknown"),
                    "alert_level": cpu_data.alert_level.value,
                    "alert_message": cpu_data.alert_message
                }
            
            # 處理記憶體數據
            if MetricType.MEMORY in all_data:
                memory_data = all_data[MetricType.MEMORY]
                total_gb = memory_data.data.get("total_bytes", 0) / (1024**3)
                used_gb = memory_data.data.get("used_bytes", 0) / (1024**3)
                
                summary["metrics"]["memory"] = {
                    "usage_percent": memory_data.data.get("usage_percent", 0.0),
                    "total_gb": round(total_gb, 1),
                    "used_gb": round(used_gb, 1),
                    "free_gb": round(total_gb - used_gb, 1),
                    "cached_gb": round(memory_data.data.get("cached_bytes", 0) / (1024**3), 1),
                    "swap_usage_percent": memory_data.data.get("swap_usage_percent", 0.0),
                    "alert_level": memory_data.alert_level.value,
                    "alert_message": memory_data.alert_message
                }
            
            # 處理磁碟數據
            if MetricType.DISK in all_data:
                disk_data = all_data[MetricType.DISK]
                total_gb = disk_data.data.get("total_space_bytes", 0) / (1024**3)
                used_gb = disk_data.data.get("used_space_bytes", 0) / (1024**3)
                
                # 計算 I/O 速度
                io_stats = disk_data.data.get("io_stats", {})
                total_read_mb_s = sum(stats.get("read_kb_per_sec", 0) for stats in io_stats.values()) / 1024
                total_write_mb_s = sum(stats.get("write_kb_per_sec", 0) for stats in io_stats.values()) / 1024
                
                summary["metrics"]["disk"] = {
                    "usage_percent": disk_data.data.get("overall_usage_percent", 0.0),
                    "total_gb": round(total_gb, 1),
                    "used_gb": round(used_gb, 1),
                    "free_gb": round(total_gb - used_gb, 1),
                    "read_mb_per_sec": round(total_read_mb_s, 1),
                    "write_mb_per_sec": round(total_write_mb_s, 1),
                    "filesystems": disk_data.data.get("filesystems", []),
                    "alert_level": disk_data.alert_level.value,
                    "alert_message": disk_data.alert_message
                }
            
            # 處理網路數據
            if MetricType.NETWORK in all_data:
                network_data = all_data[MetricType.NETWORK]
                
                # 計算速度 (MB/s)
                rx_mb_s = network_data.data.get("rx_speed_bps", 0.0) / (1024**2)
                tx_mb_s = network_data.data.get("tx_speed_bps", 0.0) / (1024**2)
                total_gb = (network_data.data.get("total_rx_bytes", 0) + 
                           network_data.data.get("total_tx_bytes", 0)) / (1024**3)
                
                summary["metrics"]["network"] = {
                    "download_mb_per_sec": round(rx_mb_s, 1),
                    "upload_mb_per_sec": round(tx_mb_s, 1),
                    "total_traffic_gb": round(total_gb, 2),
                    "active_connections": network_data.data.get("active_connections", 0),
                    "interfaces": network_data.data.get("interfaces", {}),
                    "alert_level": network_data.alert_level.value,
                    "alert_message": network_data.alert_message
                }
            
            # 計算整體警告等級
            alert_levels = [data.alert_level for data in all_data.values()]
            if AlertLevel.CRITICAL in alert_levels:
                summary["overall_alert_level"] = AlertLevel.CRITICAL.value
            elif AlertLevel.WARNING in alert_levels:
                summary["overall_alert_level"] = AlertLevel.WARNING.value
            elif AlertLevel.UNKNOWN in alert_levels:
                summary["overall_alert_level"] = AlertLevel.UNKNOWN.value
            
            return summary
            
        except Exception as e:
            logger.error(f"收集監控數據摘要失敗: {e}")
            return {
                "server_id": server_id,
                "timestamp": datetime.now().isoformat(),
                "collection_status": "failed",
                "error": str(e),
                "overall_alert_level": AlertLevel.UNKNOWN.value,
                "metrics": {}
            }
    
    def update_thresholds(self, new_thresholds: MonitoringThresholds):
        """更新監控閾值"""
        self.thresholds = new_thresholds
        self.cpu_monitor.thresholds = new_thresholds
        self.memory_monitor.thresholds = new_thresholds
        self.disk_monitor.thresholds = new_thresholds
        self.network_monitor.thresholds = new_thresholds
    
    async def test_connection_and_collect(
        self, 
        config: SSHConnectionConfig, 
        server_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """測試連接並收集基本監控數據"""
        try:
            # 先測試基本連接
            test_result = await self.executor.execute_command(config, "echo 'connection_test'", timeout=5)
            
            if test_result.status != ExecutionStatus.SUCCESS:
                return {
                    "connection_status": "failed",
                    "error": test_result.error_message,
                    "timestamp": datetime.now().isoformat()
                }
            
            # 收集基本監控數據
            summary = await self.collect_summary_metrics(config, server_id)
            summary["connection_status"] = "success"
            
            return summary
            
        except Exception as e:
            logger.error(f"測試連接並收集數據失敗: {e}")
            return {
                "connection_status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# 全域監控收集服務實例
monitoring_service = MonitoringCollectorService()


# 為服務器數據收集提供的便利函數
async def collect_server_monitoring_data(server_data: Dict[str, Any]) -> Dict[str, Any]:
    """收集伺服器監控數據的便利函數"""
    config = ssh_manager.decrypt_server_credentials(server_data)
    server_id = server_data.get("id")
    return await monitoring_service.collect_summary_metrics(config, server_id)


async def test_server_connection_and_monitoring(server_data: Dict[str, Any]) -> Dict[str, Any]:
    """測試伺服器連接並收集監控數據的便利函數"""
    config = ssh_manager.decrypt_server_credentials(server_data)
    server_id = server_data.get("id")
    return await monitoring_service.test_connection_and_collect(config, server_id)


if __name__ == "__main__":
    # 測試監控數據收集器
    
    async def test_individual_monitors():
        print("📊 測試個別監控器...")
        
        # 測試配置
        test_config = SSHConnectionConfig(
            host="localhost",
            port=22,
            username="test",
            password="test123"
        )
        
        try:
            # 測試 CPU 監控
            print("\n🔥 測試 CPU 監控...")
            cpu_data = await collect_cpu_monitoring_data(test_config)
            print(f"- 狀態: {cpu_data.alert_level.value}")
            print(f"- CPU使用率: {cpu_data.data.get('usage_percent', 0):.2f}%")
            print(f"- 核心數: {cpu_data.data.get('core_count', 0)}")
            print(f"- 負載平均: {cpu_data.data.get('load_average', {})}")
            
            # 測試記憶體監控
            print("\n💾 測試記憶體監控...")
            memory_data = await collect_memory_monitoring_data(test_config)
            print(f"- 狀態: {memory_data.alert_level.value}")
            print(f"- 記憶體使用率: {memory_data.data.get('usage_percent', 0):.2f}%")
            print(f"- 總記憶體: {memory_data.data.get('total_bytes', 0) / (1024**3):.1f}GB")
            
            # 測試磁碟監控
            print("\n💿 測試磁碟監控...")
            disk_data = await collect_disk_monitoring_data(test_config)
            print(f"- 狀態: {disk_data.alert_level.value}")
            print(f"- 磁碟使用率: {disk_data.data.get('overall_usage_percent', 0):.2f}%")
            print(f"- 文件系統數量: {len(disk_data.data.get('filesystems', []))}")
            
            # 測試網路監控
            print("\n🌐 測試網路監控...")
            network_data = await collect_network_monitoring_data(test_config)
            print(f"- 狀態: {network_data.alert_level.value}")
            print(f"- 網路介面數量: {len(network_data.data.get('interfaces', {}))}")
            print(f"- 活躍連接數: {network_data.data.get('active_connections', 0)}")
            
        except Exception as e:
            print(f"個別監控器測試失敗: {e}")
    
    async def test_monitoring_service():
        print("\n🚀 測試監控服務整合...")
        
        # 測試配置
        test_config = SSHConnectionConfig(
            host="localhost",
            port=22,
            username="test",
            password="test123"
        )
        
        try:
            # 測試完整監控數據收集
            print("\n📊 收集完整監控數據...")
            all_data = await monitoring_service.collect_all_metrics(test_config, server_id=1)
            
            print(f"收集到 {len(all_data)} 類監控數據:")
            for metric_type, data in all_data.items():
                print(f"- {metric_type.value}: {data.alert_level.value} (耗時: {data.collection_time:.2f}s)")
            
            # 測試摘要數據收集
            print("\n📈 收集摘要數據...")
            summary = await monitoring_service.collect_summary_metrics(test_config, server_id=1)
            
            print(f"摘要數據收集狀態: {summary['collection_status']}")
            print(f"整體警告等級: {summary['overall_alert_level']}")
            
            if 'metrics' in summary:
                for metric_name, metric_data in summary['metrics'].items():
                    print(f"- {metric_name}: {metric_data.get('alert_level', 'unknown')}")
            
            # 測試連接和監控
            print("\n🔗 測試連接和監控...")
            connection_test = await monitoring_service.test_connection_and_collect(test_config, server_id=1)
            print(f"連接狀態: {connection_test.get('connection_status', 'unknown')}")
            
        except Exception as e:
            print(f"監控服務測試失敗: {e}")
    
    async def test_monitoring_complete():
        """完整的監控測試"""
        print("=" * 50)
        print("🧪 CWatcher 監控數據收集器測試")
        print("=" * 50)
        
        await test_individual_monitors()
        await test_monitoring_service()
        
        print("\n✅ 監控數據收集器測試完成")
    
    # 執行測試
    import asyncio
    asyncio.run(test_monitoring_complete())