"""
CWatcher SSH 指令執行引擎

提供結構化的指令執行、結果解析和錯誤處理框架
支援指令安全檢查、結果快取和執行統計
"""

import asyncio
import logging
import re
import time
from typing import Dict, List, Optional, Any, Union, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
import json
import hashlib

from services.ssh_manager import SSHManager, SSHConnectionConfig, ssh_manager
from core.config import settings


# 設定日誌
logger = logging.getLogger(__name__)


class CommandType(Enum):
    """指令類型枚舉"""
    SYSTEM_INFO = "system_info"
    SYSTEM_METRICS = "system_metrics"
    HARDWARE_INFO = "hardware_info"
    NETWORK_INFO = "network_info"
    PROCESS_INFO = "process_info"
    CUSTOM = "custom"


class ExecutionStatus(Enum):
    """執行狀態枚舉"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SECURITY_BLOCKED = "security_blocked"


@dataclass
class CommandResult:
    """指令執行結果"""
    command: str
    command_type: CommandType
    status: ExecutionStatus
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    parsed_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    server_info: Optional[Dict[str, str]] = None


@dataclass
class CommandDefinition:
    """指令定義"""
    name: str
    command: str
    command_type: CommandType
    description: str
    parser: Optional[Callable[[str], Dict[str, Any]]] = None
    timeout: int = 30
    required_permissions: List[str] = field(default_factory=list)
    security_level: str = "safe"  # safe, moderate, dangerous
    cache_ttl: int = 0  # 快取時間（秒），0表示不快取


class CommandSecurityChecker:
    """指令安全檢查器"""
    
    def __init__(self):
        # 危險指令模式
        self.dangerous_patterns = [
            r'\brm\s+.*-rf\b',  # rm -rf
            r'\bmkfs\b',  # 格式化
            r'\bdd\s+.*of=',  # dd 寫入
            r'\bfdisk\b',  # 磁碟分割
            r'\bparted\b',  # 磁碟分割
            r'\bshutdown\b',  # 關機
            r'\breboot\b',  # 重啟
            r'\bhalt\b',  # 停機
            r'\binit\s+[06]\b',  # 重啟/關機
            r'\bkillall\b',  # 殺死所有進程
            r'\bpkill\s+.*-9\b',  # 強制殺死進程
            r'>\s*/dev/s[dr]\w*',  # 寫入裸設備
            r'\biptables\s+.*-F\b',  # 清空防火牆規則
            r'\bufw\s+.*--force\b',  # 強制防火牆操作
            r'\bsudo\s+.*passwd\b',  # 修改密碼
            r'\bchmod\s+777\b',  # 危險權限
            r'\bchown\s+.*root\b',  # 改變所有者為root
        ]
        
        # 可疑指令模式
        self.suspicious_patterns = [
            r'\bwget\s+.*\|\s*sh\b',  # 下載並執行
            r'\bcurl\s+.*\|\s*sh\b',  # 下載並執行
            r'\becho\s+.*>\s*/etc/',  # 寫入系統配置
            r'\bcat\s+.*>\s*/etc/',  # 寫入系統配置
            r'\bcp\s+.*\s+/etc/',  # 複製到系統目錄
            r'\bmv\s+.*\s+/etc/',  # 移動到系統目錄
            r'\bln\s+.*\s+/etc/',  # 連結到系統目錄
            r'\btar\s+.*xf.*-C\s*/\b',  # 解壓到根目錄
            r'\bunzip\s+.*-d\s*/\b',  # 解壓到根目錄
            r'\bcrontab\s+-r\b',  # 清空定時任務
            r'\bservice\s+.*stop\b',  # 停止服務
            r'\bsystemctl\s+.*disable\b',  # 禁用服務
        ]
        
        # 允許的安全指令白名單
        self.safe_commands = {
            # 系統資訊
            'uptime', 'uname', 'whoami', 'id', 'hostname', 'date',
            'cat /proc/version', 'cat /proc/cpuinfo', 'cat /proc/meminfo',
            'cat /proc/loadavg', 'cat /proc/stat', 'cat /proc/diskstats',
            'cat /proc/net/dev', 'lsb_release -a',
            
            # 硬體資訊
            'lscpu', 'lsmem', 'lsblk', 'lsusb', 'lspci', 'lshw',
            'dmidecode', 'hdparm -I',
            
            # 資源監控
            'free', 'df', 'du', 'iostat', 'vmstat', 'top', 'htop',
            'ps', 'netstat', 'ss', 'lsof', 'iftop',
            
            # 網路資訊
            'ip addr', 'ip route', 'ip link', 'ifconfig', 
            'ping -c', 'traceroute', 'nslookup', 'dig',
            
            # 磁碟資訊
            'fdisk -l', 'parted -l', 'mount', 'findmnt', 'blkid',
            
            # 系統狀態
            'systemctl status', 'service status', 'chkconfig --list',
            'crontab -l', 'last', 'w', 'who', 'history',
            
            # 檔案系統（只讀）
            'ls', 'find', 'locate', 'which', 'whereis', 'file', 'stat',
            'head', 'tail', 'grep', 'awk', 'sed', 'sort', 'uniq', 'wc',
        }
    
    def is_command_safe(self, command: str) -> Tuple[bool, str]:
        """
        檢查指令是否安全
        
        Args:
            command: 要檢查的指令
            
        Returns:
            (is_safe, reason)
        """
        # 清理指令
        clean_command = command.strip().lower()
        
        # 檢查是否為空
        if not clean_command:
            return False, "空指令"
        
        # 檢查危險模式
        for pattern in self.dangerous_patterns:
            if re.search(pattern, clean_command, re.IGNORECASE):
                return False, f"包含危險操作模式: {pattern}"
        
        # 檢查可疑模式
        for pattern in self.suspicious_patterns:
            if re.search(pattern, clean_command, re.IGNORECASE):
                return False, f"包含可疑操作模式: {pattern}"
        
        # 檢查基本指令是否在白名單中
        base_command = clean_command.split()[0] if clean_command.split() else ""
        
        # 特殊檢查：cat 只能讀取 /proc 和 /sys
        if base_command == 'cat':
            if 'cat' in clean_command:
                file_path = clean_command.split('cat', 1)[1].strip()
                if not (file_path.startswith('/proc/') or file_path.startswith('/sys/')):
                    return False, "cat 指令只允許讀取 /proc 和 /sys 目錄"
        
        # 檢查是否為完全匹配的安全指令
        for safe_cmd in self.safe_commands:
            if clean_command.startswith(safe_cmd.lower()):
                return True, "指令在安全白名單中"
        
        # 如果不在白名單中，則認為不安全
        return False, f"指令不在安全白名單中: {base_command}"
    
    def validate_command_syntax(self, command: str) -> Tuple[bool, str]:
        """
        驗證指令語法
        
        Args:
            command: 要驗證的指令
            
        Returns:
            (is_valid, reason)
        """
        # 檢查特殊字符
        dangerous_chars = ['|', '>', '<', '&', ';', '`', '$']
        for char in dangerous_chars:
            if char in command and char not in ['|', '>', '<']:  # 允許部分管道和重定向
                return False, f"包含危險字符: {char}"
        
        # 檢查命令注入嘗試
        injection_patterns = [
            r';\s*\w+',  # 命令分隔符
            r'&&\s*\w+',  # 邏輯與
            r'\|\|\s*\w+',  # 邏輯或
            r'`[^`]*`',  # 反引號執行
            r'\$\([^)]*\)',  # 命令替換
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, command):
                return False, f"可能的命令注入: {pattern}"
        
        return True, "語法檢查通過"


class CommandParser:
    """指令結果解析器"""
    
    @staticmethod
    def parse_uptime(output: str) -> Dict[str, Any]:
        """解析 uptime 輸出"""
        try:
            # 示例: " 16:30:01 up 10 days,  1:23,  2 users,  load average: 0.15, 0.10, 0.05"
            pattern = r'up\s+(.+?),\s+\d+\s+users?,\s+load average:\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)'
            match = re.search(pattern, output)
            
            if match:
                uptime_str = match.group(1)
                load_avg = [float(match.group(2)), float(match.group(3)), float(match.group(4))]
                
                return {
                    "uptime_string": uptime_str,
                    "load_average": {
                        "1min": load_avg[0],
                        "5min": load_avg[1],
                        "15min": load_avg[2]
                    }
                }
        except Exception as e:
            logger.warning(f"解析 uptime 失敗: {e}")
        
        return {"raw_output": output}
    
    @staticmethod
    def parse_free_memory(output: str) -> Dict[str, Any]:
        """解析 free -m 輸出"""
        try:
            lines = output.strip().split('\n')
            if len(lines) >= 2:
                # Mem: 行
                mem_line = lines[1].split()
                if len(mem_line) >= 7:
                    return {
                        "total": int(mem_line[1]),
                        "used": int(mem_line[2]),
                        "free": int(mem_line[3]),
                        "shared": int(mem_line[4]),
                        "buff_cache": int(mem_line[5]),
                        "available": int(mem_line[6]),
                        "unit": "MB"
                    }
        except Exception as e:
            logger.warning(f"解析 free 失敗: {e}")
        
        return {"raw_output": output}
    
    @staticmethod
    def parse_df_disk(output: str) -> Dict[str, Any]:
        """解析 df -h 輸出"""
        try:
            lines = output.strip().split('\n')[1:]  # 跳過標題行
            filesystems = []
            
            for line in lines:
                parts = line.split()
                if len(parts) >= 6:
                    filesystem = {
                        "filesystem": parts[0],
                        "size": parts[1],
                        "used": parts[2],
                        "available": parts[3],
                        "use_percent": parts[4],
                        "mounted_on": parts[5]
                    }
                    filesystems.append(filesystem)
            
            return {"filesystems": filesystems}
            
        except Exception as e:
            logger.warning(f"解析 df 失敗: {e}")
        
        return {"raw_output": output}
    
    @staticmethod
    def parse_lscpu(output: str) -> Dict[str, Any]:
        """解析 lscpu 輸出"""
        try:
            cpu_info = {}
            for line in output.strip().split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    cpu_info[key.strip().lower().replace(' ', '_')] = value.strip()
            
            return cpu_info
            
        except Exception as e:
            logger.warning(f"解析 lscpu 失敗: {e}")
        
        return {"raw_output": output}
    
    @staticmethod
    def parse_uname(output: str) -> Dict[str, Any]:
        """解析 uname -a 輸出"""
        try:
            parts = output.strip().split()
            if len(parts) >= 6:
                return {
                    "kernel_name": parts[0],
                    "hostname": parts[1],
                    "kernel_release": parts[2],
                    "kernel_version": parts[3],
                    "machine": parts[4],
                    "processor": parts[5] if len(parts) > 5 else "",
                    "operating_system": parts[6] if len(parts) > 6 else ""
                }
        except Exception as e:
            logger.warning(f"解析 uname 失敗: {e}")
        
        return {"raw_output": output}


class CommandCache:
    """指令結果快取"""
    
    def __init__(self):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_times: Dict[str, datetime] = {}
    
    def _get_cache_key(self, server_key: str, command: str) -> str:
        """生成快取鍵"""
        return hashlib.md5(f"{server_key}:{command}".encode()).hexdigest()
    
    def get(self, server_key: str, command: str, ttl: int) -> Optional[CommandResult]:
        """從快取獲取結果"""
        if ttl <= 0:
            return None
        
        cache_key = self._get_cache_key(server_key, command)
        
        if cache_key in self.cache:
            cache_time = self.cache_times.get(cache_key)
            if cache_time and datetime.now() - cache_time < timedelta(seconds=ttl):
                cached_data = self.cache[cache_key]
                return CommandResult(**cached_data)
        
        return None
    
    def set(self, server_key: str, command: str, result: CommandResult):
        """設定快取"""
        cache_key = self._get_cache_key(server_key, command)
        
        # 將結果轉換為可序列化的字典
        cache_data = {
            'command': result.command,
            'command_type': result.command_type,
            'status': result.status,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'exit_code': result.exit_code,
            'execution_time': result.execution_time,
            'timestamp': result.timestamp,
            'parsed_data': result.parsed_data,
            'error_message': result.error_message,
            'server_info': result.server_info
        }
        
        self.cache[cache_key] = cache_data
        self.cache_times[cache_key] = datetime.now()
    
    def clear_expired(self):
        """清理過期快取"""
        current_time = datetime.now()
        expired_keys = []
        
        for key, cache_time in self.cache_times.items():
            if current_time - cache_time > timedelta(hours=1):  # 1小時後清理
                expired_keys.append(key)
        
        for key in expired_keys:
            self.cache.pop(key, None)
            self.cache_times.pop(key, None)


class CommandExecutor:
    """SSH 指令執行引擎"""
    
    def __init__(self, ssh_manager: SSHManager):
        self.ssh_manager = ssh_manager
        self.security_checker = CommandSecurityChecker()
        self.parser = CommandParser()
        self.cache = CommandCache()
        
        # 執行統計
        self.execution_stats = defaultdict(int)
        
        # 預定義指令
        self.predefined_commands = self._init_predefined_commands()
    
    def _init_predefined_commands(self) -> Dict[str, CommandDefinition]:
        """初始化預定義指令"""
        commands = {
            # 系統資訊
            "uptime": CommandDefinition(
                name="uptime",
                command="uptime",
                command_type=CommandType.SYSTEM_INFO,
                description="獲取系統運行時間和負載",
                parser=self.parser.parse_uptime,
                timeout=10,
                cache_ttl=60
            ),
            "uname": CommandDefinition(
                name="uname",
                command="uname -a",
                command_type=CommandType.SYSTEM_INFO,
                description="獲取核心和系統資訊",
                parser=self.parser.parse_uname,
                timeout=10,
                cache_ttl=3600
            ),
            "hostname": CommandDefinition(
                name="hostname",
                command="hostname",
                command_type=CommandType.SYSTEM_INFO,
                description="獲取主機名",
                timeout=5,
                cache_ttl=3600
            ),
            "os_release": CommandDefinition(
                name="os_release",
                command="lsb_release -a 2>/dev/null || cat /etc/os-release",
                command_type=CommandType.SYSTEM_INFO,
                description="獲取作業系統版本資訊",
                timeout=10,
                cache_ttl=3600
            ),
            
            # 硬體資訊
            "cpu_info": CommandDefinition(
                name="cpu_info",
                command="lscpu",
                command_type=CommandType.HARDWARE_INFO,
                description="獲取 CPU 詳細資訊",
                parser=self.parser.parse_lscpu,
                timeout=15,
                cache_ttl=3600
            ),
            "cpu_cores": CommandDefinition(
                name="cpu_cores",
                command="cat /proc/cpuinfo | grep processor | wc -l",
                command_type=CommandType.HARDWARE_INFO,
                description="獲取 CPU 核心數",
                timeout=10,
                cache_ttl=3600
            ),
            "memory_info": CommandDefinition(
                name="memory_info",
                command="free -m",
                command_type=CommandType.SYSTEM_METRICS,
                description="獲取記憶體使用情況",
                parser=self.parser.parse_free_memory,
                timeout=10,
                cache_ttl=30
            ),
            "disk_usage": CommandDefinition(
                name="disk_usage",
                command="df -h",
                command_type=CommandType.SYSTEM_METRICS,
                description="獲取磁碟使用情況",
                parser=self.parser.parse_df_disk,
                timeout=15,
                cache_ttl=60
            ),
            
            # 系統狀況監控
            "load_average": CommandDefinition(
                name="load_average",
                command="cat /proc/loadavg",
                command_type=CommandType.SYSTEM_METRICS,
                description="獲取系統負載平均值",
                timeout=5,
                cache_ttl=10
            ),
            "cpu_stat": CommandDefinition(
                name="cpu_stat",
                command="cat /proc/stat | head -1",
                command_type=CommandType.SYSTEM_METRICS,
                description="獲取 CPU 統計資訊",
                timeout=5,
                cache_ttl=5
            ),
            "memory_detailed": CommandDefinition(
                name="memory_detailed",
                command="cat /proc/meminfo",
                command_type=CommandType.SYSTEM_METRICS,
                description="獲取詳細記憶體資訊",
                timeout=10,
                cache_ttl=30
            ),
            "disk_io": CommandDefinition(
                name="disk_io",
                command="cat /proc/diskstats",
                command_type=CommandType.SYSTEM_METRICS,
                description="獲取磁碟 I/O 統計",
                timeout=10,
                cache_ttl=10
            ),
            "network_interfaces": CommandDefinition(
                name="network_interfaces",
                command="cat /proc/net/dev",
                command_type=CommandType.NETWORK_INFO,
                description="獲取網路介面統計",
                timeout=10,
                cache_ttl=10
            ),
        }
        
        return commands
    
    async def execute_command(
        self,
        config: SSHConnectionConfig,
        command: str,
        command_type: CommandType = CommandType.CUSTOM,
        timeout: Optional[int] = None,
        use_cache: bool = True
    ) -> CommandResult:
        """
        執行 SSH 指令
        
        Args:
            config: SSH 連接配置
            command: 要執行的指令
            command_type: 指令類型
            timeout: 超時時間
            use_cache: 是否使用快取
            
        Returns:
            CommandResult: 執行結果
        """
        server_key = f"{config.username}@{config.host}:{config.port}"
        start_time = time.time()
        
        # 建立結果對象
        result = CommandResult(
            command=command,
            command_type=command_type,
            status=ExecutionStatus.PENDING,
            server_info={
                "host": config.host,
                "port": str(config.port),
                "username": config.username
            }
        )
        
        try:
            # 安全檢查
            is_safe, reason = self.security_checker.is_command_safe(command)
            if not is_safe:
                result.status = ExecutionStatus.SECURITY_BLOCKED
                result.error_message = f"安全檢查失敗: {reason}"
                self.execution_stats["security_blocked"] += 1
                return result
            
            # 語法檢查
            is_valid, reason = self.security_checker.validate_command_syntax(command)
            if not is_valid:
                result.status = ExecutionStatus.SECURITY_BLOCKED
                result.error_message = f"語法檢查失敗: {reason}"
                self.execution_stats["syntax_error"] += 1
                return result
            
            # 檢查快取
            if use_cache:
                cached_result = self.cache.get(server_key, command, 300)  # 預設5分鐘快取
                if cached_result:
                    self.execution_stats["cache_hit"] += 1
                    logger.debug(f"使用快取結果: {command}")
                    return cached_result
            
            # 執行指令
            result.status = ExecutionStatus.RUNNING
            logger.info(f"執行指令: {command} on {server_key}")
            
            stdout, stderr, exit_code = await self.ssh_manager.execute_command(
                config, command, timeout
            )
            
            # 記錄執行時間
            result.execution_time = time.time() - start_time
            result.stdout = stdout
            result.stderr = stderr
            result.exit_code = exit_code
            
            # 判斷執行狀態
            if exit_code == 0:
                result.status = ExecutionStatus.SUCCESS
                self.execution_stats["success"] += 1
            else:
                result.status = ExecutionStatus.FAILED
                result.error_message = f"指令執行失敗，退出碼: {exit_code}"
                self.execution_stats["failed"] += 1
            
            # 嘗試解析結果
            if result.status == ExecutionStatus.SUCCESS and stdout:
                try:
                    # 檢查是否有預定義的解析器
                    predefined = self.predefined_commands.get(command)
                    if predefined and predefined.parser:
                        result.parsed_data = predefined.parser(stdout)
                    else:
                        # 基本解析：將輸出按行分割
                        lines = stdout.strip().split('\n')
                        result.parsed_data = {
                            "lines": lines,
                            "line_count": len(lines)
                        }
                except Exception as e:
                    logger.warning(f"解析指令結果失敗: {e}")
                    result.parsed_data = {"raw_output": stdout}
            
            # 設定快取
            if use_cache and result.status == ExecutionStatus.SUCCESS:
                self.cache.set(server_key, command, result)
            
            logger.info(
                f"指令執行完成: {command}, 狀態: {result.status.value}, "
                f"耗時: {result.execution_time:.2f}s"
            )
            
            return result
            
        except asyncio.TimeoutError:
            result.status = ExecutionStatus.TIMEOUT
            result.error_message = f"指令執行超時 ({timeout}s)"
            result.execution_time = time.time() - start_time
            self.execution_stats["timeout"] += 1
            logger.warning(f"指令執行超時: {command}")
            return result
            
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error_message = f"執行異常: {str(e)}"
            result.execution_time = time.time() - start_time
            self.execution_stats["error"] += 1
            logger.error(f"指令執行異常: {command}, 錯誤: {e}")
            return result
    
    async def execute_predefined_command(
        self,
        config: SSHConnectionConfig,
        command_name: str,
        use_cache: bool = True
    ) -> CommandResult:
        """
        執行預定義指令
        
        Args:
            config: SSH 連接配置
            command_name: 預定義指令名稱
            use_cache: 是否使用快取
            
        Returns:
            CommandResult: 執行結果
        """
        if command_name not in self.predefined_commands:
            return CommandResult(
                command=command_name,
                command_type=CommandType.CUSTOM,
                status=ExecutionStatus.FAILED,
                error_message=f"未找到預定義指令: {command_name}"
            )
        
        cmd_def = self.predefined_commands[command_name]
        server_key = f"{config.username}@{config.host}:{config.port}"
        
        # 檢查快取
        if use_cache and cmd_def.cache_ttl > 0:
            cached_result = self.cache.get(server_key, cmd_def.command, cmd_def.cache_ttl)
            if cached_result:
                self.execution_stats["cache_hit"] += 1
                return cached_result
        
        # 執行指令
        result = await self.execute_command(
            config=config,
            command=cmd_def.command,
            command_type=cmd_def.command_type,
            timeout=cmd_def.timeout,
            use_cache=False  # 已經在這裡處理快取了
        )
        
        # 設定快取
        if use_cache and cmd_def.cache_ttl > 0 and result.status == ExecutionStatus.SUCCESS:
            self.cache.set(server_key, cmd_def.command, result)
        
        return result
    
    def get_predefined_commands(self) -> Dict[str, Dict[str, Any]]:
        """獲取所有預定義指令"""
        return {
            name: {
                "name": cmd.name,
                "command": cmd.command,
                "command_type": cmd.command_type.value,
                "description": cmd.description,
                "timeout": cmd.timeout,
                "cache_ttl": cmd.cache_ttl,
                "security_level": cmd.security_level
            }
            for name, cmd in self.predefined_commands.items()
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """獲取執行統計"""
        total_commands = sum(self.execution_stats.values())
        
        return {
            "total_executions": total_commands,
            "success_rate": (
                self.execution_stats["success"] / total_commands * 100
                if total_commands > 0 else 0
            ),
            "cache_hit_rate": (
                self.execution_stats["cache_hit"] / total_commands * 100
                if total_commands > 0 else 0
            ),
            "statistics": dict(self.execution_stats),
            "cache_size": len(self.cache.cache),
            "predefined_commands": len(self.predefined_commands)
        }
    
    def clear_cache(self):
        """清理快取"""
        self.cache.cache.clear()
        self.cache.cache_times.clear()
        logger.info("指令快取已清理")


# 全域指令執行器實例
command_executor = CommandExecutor(ssh_manager)


# 便利函數
async def execute_system_command(
    server_data: Dict[str, Any],
    command_name: str,
    use_cache: bool = True
) -> CommandResult:
    """執行系統指令的便利函數"""
    config = ssh_manager.decrypt_server_credentials(server_data)
    return await command_executor.execute_predefined_command(config, command_name, use_cache)


async def execute_custom_command(
    server_data: Dict[str, Any],
    command: str,
    timeout: Optional[int] = None
) -> CommandResult:
    """執行自訂指令的便利函數"""
    config = ssh_manager.decrypt_server_credentials(server_data)
    return await command_executor.execute_command(
        config, command, CommandType.CUSTOM, timeout, use_cache=False
    )


if __name__ == "__main__":
    # 測試指令執行器
    import asyncio
    
    async def test_command_executor():
        print("🚀 測試指令執行器...")
        
        # 測試配置
        test_config = SSHConnectionConfig(
            host="localhost",
            port=22,
            username="test",
            password="test123"
        )
        
        try:
            # 測試預定義指令
            result = await command_executor.execute_predefined_command(
                test_config, "uptime"
            )
            print(f"uptime 結果: {result.status.value}")
            if result.parsed_data:
                print(f"解析結果: {result.parsed_data}")
            
            # 測試自訂指令
            result = await command_executor.execute_command(
                test_config, "echo 'Hello World'"
            )
            print(f"自訂指令結果: {result.stdout.strip()}")
            
            # 顯示統計
            stats = command_executor.get_statistics()
            print(f"執行統計: {stats}")
            
            # 顯示預定義指令
            commands = command_executor.get_predefined_commands()
            print(f"預定義指令數量: {len(commands)}")
            
        except Exception as e:
            print(f"測試失敗: {e}")
    
    # 執行測試
    asyncio.run(test_command_executor())