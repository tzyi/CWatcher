"""
CWatcher WebSocket 訊息協議 Schema

定義 WebSocket 通訊的訊息格式、驗證規則和協議標準
確保前後端通訊的一致性和可靠性
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum


class WSMessageType(str, Enum):
    """WebSocket 訊息類型"""
    # 基礎控制訊息
    PING = "ping"
    PONG = "pong" 
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    ERROR = "error"
    
    # 監控數據訊息
    MONITORING_UPDATE = "monitoring_update"
    STATUS_CHANGE = "status_change"
    SERVER_ONLINE = "server_online"
    SERVER_OFFLINE = "server_offline"
    
    # 系統訊息
    CONNECTION_INFO = "connection_info"
    SUBSCRIPTION_ACK = "subscription_ack"
    HEARTBEAT = "heartbeat"


class WSAlertLevel(str, Enum):
    """警告等級"""
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class WSMetricType(str, Enum):
    """監控指標類型"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    ALL = "all"


# ==================== 基礎訊息結構 ====================

class WSBaseMessage(BaseModel):
    """WebSocket 基礎訊息結構"""
    type: WSMessageType = Field(..., description="訊息類型")
    message_id: str = Field(..., description="訊息唯一ID")
    timestamp: datetime = Field(default_factory=datetime.now, description="訊息時間戳")
    data: Dict[str, Any] = Field(default_factory=dict, description="訊息數據")
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ==================== 控制訊息 ====================

class WSSubscriptionFilter(BaseModel):
    """訂閱過濾器"""
    server_ids: Optional[List[int]] = Field(None, description="訂閱的伺服器ID列表，為空表示全部")
    metric_types: List[WSMetricType] = Field(
        default=["cpu", "memory", "disk", "network"], 
        description="訂閱的指標類型"
    )
    alert_levels: List[WSAlertLevel] = Field(
        default=["ok", "warning", "critical"], 
        description="訂閱的警告等級"
    )
    update_interval: int = Field(
        default=30, 
        ge=10, 
        le=300, 
        description="更新間隔（秒），範圍10-300"
    )
    
    @validator('server_ids')
    def validate_server_ids(cls, v):
        if v is not None and len(v) == 0:
            return None
        return v


class WSSubscribeRequest(BaseModel):
    """訂閱請求"""
    type: WSMessageType = Field(default=WSMessageType.SUBSCRIBE, const=True)
    data: WSSubscriptionFilter = Field(..., description="訂閱設定")


class WSUnsubscribeRequest(BaseModel):
    """取消訂閱請求"""
    type: WSMessageType = Field(default=WSMessageType.UNSUBSCRIBE, const=True)
    data: Dict[str, Any] = Field(default_factory=dict, description="取消訂閱設定")


class WSSubscriptionAck(BaseModel):
    """訂閱確認回應"""
    type: WSMessageType = Field(default=WSMessageType.SUBSCRIPTION_ACK, const=True)
    data: Dict[str, Any] = Field(..., description="訂閱確認數據")
    
    class Data(BaseModel):
        success: bool = Field(..., description="訂閱是否成功")
        subscription: Optional[WSSubscriptionFilter] = Field(None, description="當前訂閱設定")
        error: Optional[str] = Field(None, description="錯誤訊息")


# ==================== 監控數據訊息 ====================

class WSCPUMetrics(BaseModel):
    """CPU 監控數據"""
    usage_percent: float = Field(..., ge=0, le=100, description="CPU 使用率百分比")
    core_count: Optional[int] = Field(None, ge=1, description="CPU 核心數")
    frequency_mhz: Optional[float] = Field(None, ge=0, description="CPU 頻率 (MHz)")
    load_average: Dict[str, float] = Field(
        default_factory=dict, 
        description="負載平均值 {1min, 5min, 15min}"
    )
    model_name: Optional[str] = Field(None, description="CPU 型號")
    alert_level: WSAlertLevel = Field(..., description="警告等級")
    alert_message: Optional[str] = Field(None, description="警告訊息")


class WSMemoryMetrics(BaseModel):
    """記憶體監控數據"""
    usage_percent: float = Field(..., ge=0, le=100, description="記憶體使用率百分比")
    total_gb: float = Field(..., ge=0, description="總記憶體 (GB)")
    used_gb: float = Field(..., ge=0, description="已使用記憶體 (GB)")
    free_gb: float = Field(..., ge=0, description="可用記憶體 (GB)")
    cached_gb: Optional[float] = Field(None, ge=0, description="快取記憶體 (GB)")
    swap_usage_percent: Optional[float] = Field(None, ge=0, le=100, description="Swap 使用率")
    alert_level: WSAlertLevel = Field(..., description="警告等級")
    alert_message: Optional[str] = Field(None, description="警告訊息")


class WSDiskMetrics(BaseModel):
    """磁碟監控數據"""
    usage_percent: float = Field(..., ge=0, le=100, description="磁碟使用率百分比")
    total_gb: float = Field(..., ge=0, description="總磁碟空間 (GB)")
    used_gb: float = Field(..., ge=0, description="已使用空間 (GB)")
    free_gb: float = Field(..., ge=0, description="可用空間 (GB)")
    read_mb_per_sec: Optional[float] = Field(None, ge=0, description="讀取速度 (MB/s)")
    write_mb_per_sec: Optional[float] = Field(None, ge=0, description="寫入速度 (MB/s)")
    filesystems: Optional[List[Dict[str, Any]]] = Field(None, description="文件系統詳情")
    alert_level: WSAlertLevel = Field(..., description="警告等級")
    alert_message: Optional[str] = Field(None, description="警告訊息")


class WSNetworkMetrics(BaseModel):
    """網路監控數據"""
    download_mb_per_sec: float = Field(..., ge=0, description="下載速度 (MB/s)")
    upload_mb_per_sec: float = Field(..., ge=0, description="上傳速度 (MB/s)")
    total_traffic_gb: Optional[float] = Field(None, ge=0, description="總流量 (GB)")
    active_connections: Optional[int] = Field(None, ge=0, description="活躍連接數")
    interfaces: Optional[Dict[str, Any]] = Field(None, description="網路介面詳情")
    alert_level: WSAlertLevel = Field(..., description="警告等級")
    alert_message: Optional[str] = Field(None, description="警告訊息")


class WSMonitoringData(BaseModel):
    """完整監控數據"""
    server_id: int = Field(..., description="伺服器ID")
    timestamp: datetime = Field(..., description="數據時間戳")
    collection_status: str = Field(..., description="收集狀態")
    overall_alert_level: WSAlertLevel = Field(..., description="整體警告等級")
    metrics: Dict[str, Any] = Field(..., description="監控指標數據")
    
    class Metrics(BaseModel):
        cpu: Optional[WSCPUMetrics] = None
        memory: Optional[WSMemoryMetrics] = None
        disk: Optional[WSDiskMetrics] = None
        network: Optional[WSNetworkMetrics] = None


class WSMonitoringUpdate(BaseModel):
    """監控數據更新訊息"""
    type: WSMessageType = Field(default=WSMessageType.MONITORING_UPDATE, const=True)
    data: WSMonitoringData = Field(..., description="監控數據")


# ==================== 狀態變化訊息 ====================

class WSServerStatus(str, Enum):
    """伺服器狀態"""
    ONLINE = "online"
    WARNING = "warning"
    OFFLINE = "offline"
    ERROR = "error"
    UNKNOWN = "unknown"


class WSStatusChangeData(BaseModel):
    """狀態變化數據"""
    server_id: int = Field(..., description="伺服器ID")
    old_status: WSServerStatus = Field(..., description="舊狀態")
    new_status: WSServerStatus = Field(..., description="新狀態")
    reason: Optional[str] = Field(None, description="狀態變化原因")
    timestamp: datetime = Field(default_factory=datetime.now, description="變化時間")


class WSStatusChange(BaseModel):
    """狀態變化訊息"""
    type: WSMessageType = Field(default=WSMessageType.STATUS_CHANGE, const=True)
    data: WSStatusChangeData = Field(..., description="狀態變化數據")


# ==================== 系統訊息 ====================

class WSConnectionInfo(BaseModel):
    """連接資訊"""
    connection_id: str = Field(..., description="連接ID")
    server_time: datetime = Field(..., description="伺服器時間")
    supported_message_types: List[str] = Field(..., description="支援的訊息類型")
    heartbeat_interval: int = Field(default=30, description="心跳間隔（秒）")
    max_idle_time: int = Field(default=300, description="最大閒置時間（秒）")


class WSConnectionInfoMessage(BaseModel):
    """連接資訊訊息"""
    type: WSMessageType = Field(default=WSMessageType.CONNECTION_INFO, const=True)
    data: WSConnectionInfo = Field(..., description="連接資訊")


class WSErrorData(BaseModel):
    """錯誤數據"""
    error: str = Field(..., description="錯誤訊息")
    error_code: Optional[str] = Field(None, description="錯誤代碼")
    details: Optional[Dict[str, Any]] = Field(None, description="錯誤詳情")
    timestamp: datetime = Field(default_factory=datetime.now, description="錯誤時間")


class WSError(BaseModel):
    """錯誤訊息"""
    type: WSMessageType = Field(default=WSMessageType.ERROR, const=True)
    data: WSErrorData = Field(..., description="錯誤數據")


# ==================== 心跳訊息 ====================

class WSPing(BaseModel):
    """Ping 訊息"""
    type: WSMessageType = Field(default=WSMessageType.PING, const=True)
    data: Dict[str, Any] = Field(default_factory=dict)


class WSPong(BaseModel):
    """Pong 訊息"""
    type: WSMessageType = Field(default=WSMessageType.PONG, const=True)
    data: Dict[str, Any] = Field(default_factory=dict)


class WSHeartbeat(BaseModel):
    """心跳訊息"""
    type: WSMessageType = Field(default=WSMessageType.HEARTBEAT, const=True)
    data: Dict[str, Any] = Field(default_factory=dict)


# ==================== 訊息聯合類型 ====================

WSMessage = Union[
    WSSubscribeRequest,
    WSUnsubscribeRequest,
    WSSubscriptionAck,
    WSMonitoringUpdate,
    WSStatusChange,
    WSConnectionInfoMessage,
    WSError,
    WSPing,
    WSPong,
    WSHeartbeat
]


# ==================== 協議工具函數 ====================

def create_monitoring_update_message(
    server_id: int,
    monitoring_data: Dict[str, Any]
) -> WSMonitoringUpdate:
    """建立監控數據更新訊息"""
    return WSMonitoringUpdate(
        data=WSMonitoringData(
            server_id=server_id,
            timestamp=datetime.now(),
            collection_status=monitoring_data.get("collection_status", "success"),
            overall_alert_level=WSAlertLevel(monitoring_data.get("overall_alert_level", "ok")),
            metrics=monitoring_data.get("metrics", {})
        )
    )


def create_status_change_message(
    server_id: int,
    old_status: str,
    new_status: str,
    reason: str = None
) -> WSStatusChange:
    """建立狀態變化訊息"""
    return WSStatusChange(
        data=WSStatusChangeData(
            server_id=server_id,
            old_status=WSServerStatus(old_status),
            new_status=WSServerStatus(new_status),
            reason=reason
        )
    )


def create_error_message(
    error: str,
    error_code: str = None,
    details: Dict[str, Any] = None
) -> WSError:
    """建立錯誤訊息"""
    return WSError(
        data=WSErrorData(
            error=error,
            error_code=error_code,
            details=details
        )
    )


def create_subscription_ack_message(
    success: bool,
    subscription: WSSubscriptionFilter = None,
    error: str = None
) -> WSSubscriptionAck:
    """建立訂閱確認訊息"""
    return WSSubscriptionAck(
        data={
            "success": success,
            "subscription": subscription.dict() if subscription else None,
            "error": error
        }
    )


def validate_message_format(message_data: Dict[str, Any]) -> bool:
    """驗證訊息格式是否正確"""
    try:
        # 檢查必要欄位
        required_fields = ["type", "message_id", "timestamp", "data"]
        for field in required_fields:
            if field not in message_data:
                return False
        
        # 檢查訊息類型是否有效
        message_type = message_data.get("type")
        if message_type not in [t.value for t in WSMessageType]:
            return False
        
        return True
        
    except Exception:
        return False


def get_message_schema(message_type: WSMessageType) -> type:
    """根據訊息類型取得對應的 Schema 類別"""
    schema_map = {
        WSMessageType.SUBSCRIBE: WSSubscribeRequest,
        WSMessageType.UNSUBSCRIBE: WSUnsubscribeRequest,
        WSMessageType.SUBSCRIPTION_ACK: WSSubscriptionAck,
        WSMessageType.MONITORING_UPDATE: WSMonitoringUpdate,
        WSMessageType.STATUS_CHANGE: WSStatusChange,
        WSMessageType.CONNECTION_INFO: WSConnectionInfoMessage,
        WSMessageType.ERROR: WSError,
        WSMessageType.PING: WSPing,
        WSMessageType.PONG: WSPong,
        WSMessageType.HEARTBEAT: WSHeartbeat
    }
    
    return schema_map.get(message_type, WSBaseMessage)


# ==================== 協議版本資訊 ====================

WEBSOCKET_PROTOCOL_VERSION = "1.0"
SUPPORTED_MESSAGE_TYPES = [t.value for t in WSMessageType]
DEFAULT_HEARTBEAT_INTERVAL = 30
DEFAULT_MAX_IDLE_TIME = 300
MAX_MESSAGE_SIZE = 1024 * 1024  # 1MB
MAX_SUBSCRIPTION_SERVERS = 100