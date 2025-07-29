"""
CWatcher 指令執行相關的 Pydantic 模型

定義指令執行請求、回應和系統資訊的數據結構
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator
from enum import Enum


class CommandType(str, Enum):
    """指令類型枚舉"""
    SYSTEM_INFO = "system_info"
    SYSTEM_METRICS = "system_metrics"
    HARDWARE_INFO = "hardware_info"
    NETWORK_INFO = "network_info"
    PROCESS_INFO = "process_info"
    CUSTOM = "custom"


class ExecutionStatus(str, Enum):
    """執行狀態枚舉"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SECURITY_BLOCKED = "security_blocked"


class SystemInfoType(str, Enum):
    """系統資訊類型枚舉"""
    HARDWARE = "hardware"
    OPERATING_SYSTEM = "operating_system"
    RUNTIME_STATUS = "runtime_status"
    NETWORK = "network"
    STORAGE = "storage"


# 請求模型
class CommandExecuteRequest(BaseModel):
    """指令執行請求"""
    command: str = Field(..., description="要執行的指令", min_length=1, max_length=500)
    command_type: CommandType = Field(default=CommandType.CUSTOM, description="指令類型")
    timeout: Optional[int] = Field(default=30, description="執行超時時間（秒）", ge=1, le=300)
    use_cache: bool = Field(default=True, description="是否使用快取")
    
    @validator('command')
    def validate_command(cls, v):
        """驗證指令格式"""
        if not v or not v.strip():
            raise ValueError('指令不能為空')
        
        # 基本安全檢查
        dangerous_chars = ['|', '&&', '||', ';', '`']
        for char in dangerous_chars:
            if char in v:
                raise ValueError(f'指令包含危險字符: {char}')
        
        return v.strip()


class PredefinedCommandRequest(BaseModel):
    """預定義指令執行請求"""
    command_name: str = Field(..., description="預定義指令名稱", min_length=1, max_length=100)
    use_cache: bool = Field(default=True, description="是否使用快取")
    
    @validator('command_name')
    def validate_command_name(cls, v):
        """驗證指令名稱格式"""
        if not v or not v.strip():
            raise ValueError('指令名稱不能為空')
        
        # 只允許字母、數字和下劃線
        import re
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', v):
            raise ValueError('指令名稱格式無效')
        
        return v.strip()


class SystemInfoRequest(BaseModel):
    """系統資訊收集請求"""
    info_types: Optional[List[SystemInfoType]] = Field(
        default=None, 
        description="要收集的資訊類型，為空則收集所有類型"
    )
    include_details: bool = Field(default=True, description="是否包含詳細資訊")
    use_cache: bool = Field(default=True, description="是否使用快取")


# 回應模型
class CommandResult(BaseModel):
    """指令執行結果"""
    command: str = Field(..., description="執行的指令")
    command_type: CommandType = Field(..., description="指令類型")
    status: ExecutionStatus = Field(..., description="執行狀態")
    stdout: str = Field(default="", description="標準輸出")
    stderr: str = Field(default="", description="標準錯誤")
    exit_code: int = Field(default=0, description="退出碼")
    execution_time: float = Field(default=0.0, description="執行時間（秒）")
    timestamp: datetime = Field(..., description="執行時間戳")
    parsed_data: Optional[Dict[str, Any]] = Field(default=None, description="解析後的數據")
    error_message: Optional[str] = Field(default=None, description="錯誤訊息")
    server_info: Optional[Dict[str, str]] = Field(default=None, description="伺服器資訊")
    
    class Config:
        use_enum_values = True


class PredefinedCommand(BaseModel):
    """預定義指令資訊"""
    name: str = Field(..., description="指令名稱")
    command: str = Field(..., description="實際指令")
    command_type: CommandType = Field(..., description="指令類型")
    description: str = Field(..., description="指令描述")
    timeout: int = Field(..., description="超時時間（秒）")
    cache_ttl: int = Field(..., description="快取時間（秒）")
    security_level: str = Field(..., description="安全等級")
    
    class Config:
        use_enum_values = True


class CommandStatistics(BaseModel):
    """指令執行統計"""
    total_executions: int = Field(..., description="總執行次數")
    success_rate: float = Field(..., description="成功率（%）")
    cache_hit_rate: float = Field(..., description="快取命中率（%）")
    statistics: Dict[str, int] = Field(..., description="詳細統計")
    cache_size: int = Field(..., description="快取大小")
    predefined_commands: int = Field(..., description="預定義指令數量")


# 系統資訊相關模型
class CPUInfo(BaseModel):
    """CPU 資訊"""
    collection_status: str = Field(..., description="收集狀態")
    core_count: int = Field(default=0, description="核心數量")
    cpu_model: Optional[str] = Field(default=None, description="CPU 型號")
    cpu_vendor: Optional[str] = Field(default=None, description="CPU 廠商")
    cpu_mhz: Optional[str] = Field(default=None, description="CPU 頻率")
    cpu_cache_size: Optional[str] = Field(default=None, description="快取大小")
    cpu_flags: Optional[List[str]] = Field(default=None, description="CPU 特性")
    details: Optional[Dict[str, Any]] = Field(default=None, description="詳細資訊")
    raw_info: Optional[str] = Field(default=None, description="原始資訊")
    error: Optional[str] = Field(default=None, description="錯誤訊息")


class MemoryInfo(BaseModel):
    """記憶體資訊"""
    collection_status: str = Field(..., description="收集狀態")
    basic_info: Optional[Dict[str, Any]] = Field(default=None, description="基本資訊")
    detailed_info: Optional[Dict[str, Any]] = Field(default=None, description="詳細資訊")
    hardware_info: Optional[Dict[str, Any]] = Field(default=None, description="硬體資訊")
    raw_info: Optional[str] = Field(default=None, description="原始資訊")
    error: Optional[str] = Field(default=None, description="錯誤訊息")


class StorageInfo(BaseModel):
    """儲存資訊"""
    collection_status: str = Field(..., description="收集狀態")
    disk_usage: Optional[Dict[str, Any]] = Field(default=None, description="磁碟使用情況")
    block_devices: Optional[Dict[str, Any]] = Field(default=None, description="塊設備資訊")
    mounted_filesystems: Optional[List[Dict[str, str]]] = Field(default=None, description="掛載的檔案系統")
    io_stats: Optional[Dict[str, Any]] = Field(default=None, description="I/O 統計")
    error: Optional[str] = Field(default=None, description="錯誤訊息")


class HardwareInfo(BaseModel):
    """硬體資訊"""
    cpu: CPUInfo = Field(..., description="CPU 資訊")
    memory: MemoryInfo = Field(..., description="記憶體資訊")


class OperatingSystemInfo(BaseModel):
    """作業系統資訊"""
    collection_status: str = Field(..., description="收集狀態")
    kernel_info: Optional[Dict[str, Any]] = Field(default=None, description="核心資訊")
    hostname: Optional[str] = Field(default=None, description="主機名稱")
    os_release: Optional[Dict[str, str]] = Field(default=None, description="作業系統版本")
    kernel_version: Optional[str] = Field(default=None, description="核心版本詳情")
    uptime_info: Optional[Dict[str, Any]] = Field(default=None, description="運行時間資訊")
    error: Optional[str] = Field(default=None, description="錯誤訊息")


class RuntimeStatusInfo(BaseModel):
    """運行狀態資訊"""
    collection_status: str = Field(..., description="收集狀態")
    load_average: Optional[Dict[str, float]] = Field(default=None, description="負載平均值")
    cpu_stat: Optional[Dict[str, Any]] = Field(default=None, description="CPU 統計")
    memory_usage: Optional[Dict[str, Any]] = Field(default=None, description="記憶體使用情況")
    process_count: Optional[int] = Field(default=None, description="進程數量")
    network_connections: Optional[int] = Field(default=None, description="網路連接數")
    logged_users: Optional[int] = Field(default=None, description="登入用戶數")
    error: Optional[str] = Field(default=None, description="錯誤訊息")


class NetworkInfo(BaseModel):
    """網路資訊"""
    collection_status: str = Field(..., description="收集狀態")
    interfaces: Optional[Dict[str, Dict[str, int]]] = Field(default=None, description="網路介面統計")
    ip_addresses: Optional[List[Dict[str, Any]]] = Field(default=None, description="IP 地址資訊")
    routes: Optional[List[Dict[str, str]]] = Field(default=None, description="路由表")
    error: Optional[str] = Field(default=None, description="錯誤訊息")


class SystemInfoData(BaseModel):
    """系統資訊數據"""
    info_type: SystemInfoType = Field(..., description="資訊類型")
    data: Dict[str, Any] = Field(..., description="資訊數據")
    timestamp: datetime = Field(..., description="收集時間戳")
    collection_time: float = Field(..., description="收集耗時（秒）")
    server_info: Optional[Dict[str, str]] = Field(default=None, description="伺服器資訊")
    
    class Config:
        use_enum_values = True


class CompleteSystemInfo(BaseModel):
    """完整系統資訊"""
    hardware: Optional[SystemInfoData] = Field(default=None, description="硬體資訊")
    operating_system: Optional[SystemInfoData] = Field(default=None, description="作業系統資訊")
    runtime_status: Optional[SystemInfoData] = Field(default=None, description="運行狀態資訊")
    network: Optional[SystemInfoData] = Field(default=None, description="網路資訊")
    storage: Optional[SystemInfoData] = Field(default=None, description="儲存資訊")
    collection_summary: Optional[Dict[str, Any]] = Field(default=None, description="收集摘要")


class BasicSystemInfo(BaseModel):
    """基本系統資訊"""
    hostname: Dict[str, Any] = Field(..., description="主機名稱")
    uptime: Dict[str, Any] = Field(..., description="運行時間")
    os_info: Dict[str, Any] = Field(..., description="作業系統資訊")
    memory: Dict[str, Any] = Field(..., description="記憶體資訊")
    disk: Dict[str, Any] = Field(..., description="磁碟資訊")
    collection_status: Optional[str] = Field(default=None, description="整體收集狀態")


# API 回應模型
class CommandExecuteResponse(BaseModel):
    """指令執行回應"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="回應訊息")
    result: Optional[CommandResult] = Field(default=None, description="執行結果")
    execution_id: Optional[str] = Field(default=None, description="執行ID")


class PredefinedCommandsResponse(BaseModel):
    """預定義指令列表回應"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="回應訊息")
    commands: Dict[str, PredefinedCommand] = Field(..., description="預定義指令字典")
    total_count: int = Field(..., description="總數量")


class SystemInfoResponse(BaseModel):
    """系統資訊回應"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="回應訊息")
    data: Optional[Union[CompleteSystemInfo, BasicSystemInfo]] = Field(default=None, description="系統資訊數據")
    collection_time: Optional[float] = Field(default=None, description="總收集時間（秒）")


class CommandStatisticsResponse(BaseModel):
    """指令統計回應"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="回應訊息")
    statistics: Optional[CommandStatistics] = Field(default=None, description="統計資料")


# 錯誤回應模型
class ErrorResponse(BaseModel):
    """錯誤回應"""
    success: bool = Field(default=False, description="是否成功")
    message: str = Field(..., description="錯誤訊息")
    error_code: Optional[str] = Field(default=None, description="錯誤代碼")
    details: Optional[Dict[str, Any]] = Field(default=None, description="錯誤詳情")
    timestamp: datetime = Field(default_factory=datetime.now, description="錯誤時間戳")


# 驗證函數
def validate_server_id(server_id: int) -> int:
    """驗證伺服器 ID"""
    if server_id <= 0:
        raise ValueError("伺服器 ID 必須大於 0")
    return server_id


def validate_timeout(timeout: int) -> int:
    """驗證超時時間"""
    if timeout < 1 or timeout > 300:
        raise ValueError("超時時間必須在 1-300 秒之間")
    return timeout


# 範例數據
EXAMPLE_COMMAND_RESULT = {
    "command": "uptime",
    "command_type": "system_info",
    "status": "success",
    "stdout": " 16:30:01 up 10 days,  1:23,  2 users,  load average: 0.15, 0.10, 0.05",
    "stderr": "",
    "exit_code": 0,
    "execution_time": 0.25,
    "timestamp": "2024-01-15T16:30:01.123456",
    "parsed_data": {
        "uptime_string": "10 days,  1:23",
        "load_average": {
            "1min": 0.15,
            "5min": 0.10,
            "15min": 0.05
        }
    },
    "error_message": None,
    "server_info": {
        "host": "192.168.1.100",
        "port": "22",
        "username": "admin"
    }
}

EXAMPLE_SYSTEM_INFO = {
    "hardware": {
        "cpu": {
            "collection_status": "success",
            "core_count": 4,
            "cpu_model": "Intel(R) Core(TM) i5-8250U CPU @ 1.60GHz",
            "cpu_vendor": "GenuineIntel",
            "cpu_mhz": "1800.000"
        },
        "memory": {
            "collection_status": "success",
            "basic_info": {
                "total": 8192,
                "used": 4096,
                "free": 4096,
                "unit": "MB"
            }
        }
    },
    "operating_system": {
        "collection_status": "success",
        "hostname": "web-server-01",
        "os_release": {
            "name": "Ubuntu",
            "version": "20.04 LTS",
            "id": "ubuntu"
        }
    }
}