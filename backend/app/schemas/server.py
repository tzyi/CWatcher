"""
CWatcher 伺服器相關 Pydantic Schema

定義伺服器管理的 API 請求和回應資料結構
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator, ConfigDict


class ServerBase(BaseModel):
    """伺服器基礎資料結構"""
    name: str = Field(..., min_length=1, max_length=100, description="伺服器名稱")
    ip_address: str = Field(..., min_length=7, max_length=45, description="IP位址")
    description: Optional[str] = Field(None, max_length=1000, description="伺服器描述")
    ssh_port: int = Field(22, ge=1, le=65535, description="SSH連接埠")
    username: str = Field(..., min_length=1, max_length=50, description="SSH用戶名")
    
    # 連接設定
    connection_timeout: int = Field(10, ge=1, le=300, description="連接超時時間（秒）")
    command_timeout: int = Field(30, ge=1, le=600, description="指令執行超時時間（秒）")
    max_connections: int = Field(3, ge=1, le=10, description="最大並發連接數")
    
    # 監控設定
    monitoring_enabled: bool = Field(True, description="是否啟用監控")
    monitoring_interval: int = Field(30, ge=10, le=300, description="監控間隔（秒）")


class ServerCreate(ServerBase):
    """創建伺服器請求資料結構"""
    password: Optional[str] = Field(None, min_length=1, description="SSH密碼")
    private_key: Optional[str] = Field(None, min_length=1, description="SSH私鑰")
    
    @validator('password', 'private_key')
    def validate_auth_method(cls, v, values):
        """驗證至少提供一種認證方式"""
        password = values.get('password')
        private_key = v if 'private_key' in values else values.get('private_key')
        
        if not password and not private_key:
            raise ValueError('必須提供密碼或私鑰其中一種認證方式')
        return v


class ServerUpdate(BaseModel):
    """更新伺服器請求資料結構"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="伺服器名稱")
    description: Optional[str] = Field(None, max_length=1000, description="伺服器描述")
    ssh_port: Optional[int] = Field(None, ge=1, le=65535, description="SSH連接埠")
    username: Optional[str] = Field(None, min_length=1, max_length=50, description="SSH用戶名")
    password: Optional[str] = Field(None, min_length=1, description="SSH密碼")
    private_key: Optional[str] = Field(None, min_length=1, description="SSH私鑰")
    
    # 連接設定
    connection_timeout: Optional[int] = Field(None, ge=1, le=300, description="連接超時時間（秒）")
    command_timeout: Optional[int] = Field(None, ge=1, le=600, description="指令執行超時時間（秒）")
    max_connections: Optional[int] = Field(None, ge=1, le=10, description="最大並發連接數")
    
    # 監控設定
    monitoring_enabled: Optional[bool] = Field(None, description="是否啟用監控")
    monitoring_interval: Optional[int] = Field(None, ge=10, le=300, description="監控間隔（秒）")


class ServerResponse(ServerBase):
    """伺服器回應資料結構"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="伺服器唯一識別碼")
    status: str = Field(..., description="伺服器狀態")
    last_connected_at: Optional[datetime] = Field(None, description="最後連接時間")
    last_error: Optional[str] = Field(None, description="最後錯誤訊息")
    connection_attempts: int = Field(..., description="連續連接失敗次數")
    created_at: datetime = Field(..., description="創建時間")
    updated_at: datetime = Field(..., description="更新時間")


class ServerListResponse(BaseModel):
    """伺服器列表回應資料結構"""
    servers: List[ServerResponse] = Field(..., description="伺服器列表")
    total: int = Field(..., description="總數量")
    page: int = Field(..., description="當前頁數")
    size: int = Field(..., description="每頁大小")


class ServerStatusUpdate(BaseModel):
    """伺服器狀態更新資料結構"""
    status: str = Field(..., description="新狀態")
    error_message: Optional[str] = Field(None, description="錯誤訊息")


class ServerConnectionTest(BaseModel):
    """伺服器連接測試回應資料結構"""
    success: bool = Field(..., description="連接是否成功")
    message: str = Field(..., description="連接結果訊息")
    latency_ms: Optional[int] = Field(None, description="連接延遲（毫秒）")
    server_info: Optional[dict] = Field(None, description="伺服器基本資訊")


class ServerStats(BaseModel):
    """伺服器統計資料結構"""
    total_servers: int = Field(..., description="總伺服器數")
    online_servers: int = Field(..., description="在線伺服器數")
    offline_servers: int = Field(..., description="離線伺服器數")
    warning_servers: int = Field(..., description="警告狀態伺服器數")
    error_servers: int = Field(..., description="錯誤狀態伺服器數")


# 錯誤回應結構
class ErrorResponse(BaseModel):
    """通用錯誤回應結構"""
    error: str = Field(..., description="錯誤類型")
    detail: str = Field(..., description="錯誤詳細資訊")
    status_code: int = Field(..., description="HTTP 狀態碼")


class ValidationErrorResponse(BaseModel):
    """驗證錯誤回應結構"""
    error: str = Field("Validation Error", description="錯誤類型")
    detail: List[dict] = Field(..., description="驗證錯誤詳細資訊")
    status_code: int = Field(422, description="HTTP 狀態碼")


# 分頁查詢參數
class ServerQueryParams(BaseModel):
    """伺服器查詢參數"""
    page: int = Field(1, ge=1, description="頁數")
    size: int = Field(20, ge=1, le=100, description="每頁大小")
    status: Optional[str] = Field(None, description="狀態篩選")
    search: Optional[str] = Field(None, min_length=1, max_length=100, description="搜尋關鍵字")
    monitoring_enabled: Optional[bool] = Field(None, description="監控狀態篩選")
    
    
# WebSocket 訊息結構
class WebSocketMessage(BaseModel):
    """WebSocket 訊息結構"""
    type: str = Field(..., description="訊息類型")
    data: dict = Field(..., description="訊息資料")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="訊息時間戳")


class ServerMonitoringMessage(WebSocketMessage):
    """伺服器監控 WebSocket 訊息"""
    type: str = Field("server_monitoring", description="訊息類型")
    server_id: int = Field(..., description="伺服器ID")
    metrics: dict = Field(..., description="監控指標資料")