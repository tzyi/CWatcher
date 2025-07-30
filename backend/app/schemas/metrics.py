"""
CWatcher 監控數據的 Pydantic 模型定義

定義監控數據的請求和回應格式
支援各種監控指標的結構化數據傳輸
"""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum


class MetricTypeFilter(str, Enum):
    """監控指標類型過濾器"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"


class AlertLevelEnum(str, Enum):
    """警告等級枚舉"""
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


# === 監控數據結構模型 ===

class CPUMetrics(BaseModel):
    """CPU 監控數據模型"""
    usage_percent: float = Field(..., description="CPU使用率 (%)")
    core_count: int = Field(..., description="CPU核心數")
    frequency_mhz: float = Field(..., description="CPU頻率 (MHz)")
    load_average: Dict[str, float] = Field(..., description="負載平均值")
    model_name: str = Field(..., description="CPU型號")
    alert_level: AlertLevelEnum = Field(..., description="警告等級")
    alert_message: Optional[str] = Field(None, description="警告訊息")

    model_config = {'protected_namespaces': ()}


class MemoryMetrics(BaseModel):
    """記憶體監控數據模型"""
    usage_percent: float = Field(..., description="記憶體使用率 (%)")
    total_gb: float = Field(..., description="總記憶體 (GB)")
    used_gb: float = Field(..., description="已使用記憶體 (GB)")
    free_gb: float = Field(..., description="可用記憶體 (GB)")
    cached_gb: float = Field(..., description="快取記憶體 (GB)")
    swap_usage_percent: float = Field(..., description="Swap使用率 (%)")
    alert_level: AlertLevelEnum = Field(..., description="警告等級")
    alert_message: Optional[str] = Field(None, description="警告訊息")


class FilesystemInfo(BaseModel):
    """文件系統資訊"""
    filesystem: str = Field(..., description="文件系統設備")
    mountpoint: str = Field(..., description="掛載點")
    total_bytes: int = Field(..., description="總容量 (bytes)")
    used_bytes: int = Field(..., description="已用容量 (bytes)")
    free_bytes: int = Field(..., description="可用容量 (bytes)")
    usage_percent: float = Field(..., description="使用率 (%)")


class DiskMetrics(BaseModel):
    """磁碟監控數據模型"""
    usage_percent: float = Field(..., description="整體磁碟使用率 (%)")
    total_gb: float = Field(..., description="總容量 (GB)")
    used_gb: float = Field(..., description="已用容量 (GB)")
    free_gb: float = Field(..., description="可用容量 (GB)")
    read_mb_per_sec: float = Field(..., description="讀取速度 (MB/s)")
    write_mb_per_sec: float = Field(..., description="寫入速度 (MB/s)")
    filesystems: List[FilesystemInfo] = Field(..., description="文件系統列表")
    alert_level: AlertLevelEnum = Field(..., description="警告等級")
    alert_message: Optional[str] = Field(None, description="警告訊息")


class NetworkInterfaceInfo(BaseModel):
    """網路介面資訊"""
    name: str = Field(..., description="介面名稱")
    rx_bytes: int = Field(..., description="接收位元組數")
    tx_bytes: int = Field(..., description="傳送位元組數")
    rx_packets: int = Field(..., description="接收封包數")
    tx_packets: int = Field(..., description="傳送封包數")
    rx_errors: int = Field(..., description="接收錯誤數")
    tx_errors: int = Field(..., description="傳送錯誤數")
    rx_speed_bps: float = Field(..., description="接收速度 (bytes/s)")
    tx_speed_bps: float = Field(..., description="傳送速度 (bytes/s)")
    rx_speed_mbps: float = Field(..., description="接收速度 (MB/s)")
    tx_speed_mbps: float = Field(..., description="傳送速度 (MB/s)")


class NetworkMetrics(BaseModel):
    """網路監控數據模型"""
    download_mb_per_sec: float = Field(..., description="下載速度 (MB/s)")
    upload_mb_per_sec: float = Field(..., description="上傳速度 (MB/s)")
    total_traffic_gb: float = Field(..., description="總流量 (GB)")
    active_connections: int = Field(..., description="活躍連接數")
    interfaces: Dict[str, NetworkInterfaceInfo] = Field(..., description="網路介面詳情")
    alert_level: AlertLevelEnum = Field(..., description="警告等級")
    alert_message: Optional[str] = Field(None, description="警告訊息")


class AllMetrics(BaseModel):
    """完整監控數據模型"""
    cpu: CPUMetrics = Field(..., description="CPU監控數據")
    memory: MemoryMetrics = Field(..., description="記憶體監控數據")
    disk: DiskMetrics = Field(..., description="磁碟監控數據")
    network: NetworkMetrics = Field(..., description="網路監控數據")


# === 監控數據摘要模型 (符合UI需求) ===

class MonitoringSummary(BaseModel):
    """監控數據摘要 - 符合UI原型需求"""
    server_id: Optional[int] = Field(None, description="伺服器ID")
    timestamp: str = Field(..., description="數據收集時間")
    collection_status: str = Field(..., description="收集狀態")
    overall_alert_level: AlertLevelEnum = Field(..., description="整體警告等級")
    connection_status: Optional[str] = Field(None, description="連接狀態")
    metrics: Dict[str, Any] = Field(..., description="監控指標數據")
    
    class Config:
        json_schema_extra = {
            "example": {
                "server_id": 1,
                "timestamp": "2024-01-15T10:30:00",
                "collection_status": "success",
                "overall_alert_level": "ok",
                "connection_status": "success",
                "metrics": {
                    "cpu": {
                        "usage_percent": 42.0,
                        "core_count": 4,
                        "frequency_mhz": 2400.0,
                        "load_average": {"1min": 0.38, "5min": 0.45, "15min": 0.52},
                        "model_name": "Intel Core i5",
                        "alert_level": "ok"
                    },
                    "memory": {
                        "usage_percent": 68.0,
                        "total_gb": 8.0,
                        "used_gb": 5.4,
                        "free_gb": 1.4,
                        "cached_gb": 1.2,
                        "swap_usage_percent": 0.0,
                        "alert_level": "ok"
                    },
                    "disk": {
                        "usage_percent": 76.0,
                        "total_gb": 500.0,
                        "used_gb": 380.0,
                        "free_gb": 120.0,
                        "read_mb_per_sec": 12.4,
                        "write_mb_per_sec": 8.7,
                        "alert_level": "ok"
                    },
                    "network": {
                        "download_mb_per_sec": 2.4,
                        "upload_mb_per_sec": 0.8,
                        "total_traffic_gb": 1.2,
                        "active_connections": 45,
                        "alert_level": "ok"
                    }
                }
            }
        }


# === 警告相關模型 ===

class AlertInfo(BaseModel):
    """警告資訊模型"""
    metric_type: MetricTypeFilter = Field(..., description="監控指標類型")
    alert_level: AlertLevelEnum = Field(..., description="警告等級")
    alert_message: Optional[str] = Field(None, description="警告訊息")
    timestamp: str = Field(..., description="警告時間")
    data_summary: Dict[str, Any] = Field(..., description="相關數據摘要")


class ServerAlerts(BaseModel):
    """伺服器警告狀態模型"""
    server_id: int = Field(..., description="伺服器ID")
    alert_count: int = Field(..., description="警告數量")
    alerts: List[AlertInfo] = Field(..., description="警告列表")
    timestamp: str = Field(..., description="查詢時間")


# === 閾值設定模型 ===

class MonitoringThresholdsUpdate(BaseModel):
    """監控閾值更新模型"""
    cpu_warning: float = Field(80.0, ge=0, le=100, description="CPU警告閾值 (%)")
    cpu_critical: float = Field(90.0, ge=0, le=100, description="CPU嚴重閾值 (%)")
    memory_warning: float = Field(85.0, ge=0, le=100, description="記憶體警告閾值 (%)")
    memory_critical: float = Field(95.0, ge=0, le=100, description="記憶體嚴重閾值 (%)")
    disk_warning: float = Field(85.0, ge=0, le=100, description="磁碟警告閾值 (%)")
    disk_critical: float = Field(95.0, ge=0, le=100, description="磁碟嚴重閾值 (%)")
    load_warning: float = Field(5.0, ge=0, description="負載警告閾值")
    load_critical: float = Field(10.0, ge=0, description="負載嚴重閾值")
    
    @validator('cpu_critical')
    def cpu_critical_must_be_greater_than_warning(cls, v, values):
        if 'cpu_warning' in values and v <= values['cpu_warning']:
            raise ValueError('CPU嚴重閾值必須大於警告閾值')
        return v
    
    @validator('memory_critical')
    def memory_critical_must_be_greater_than_warning(cls, v, values):
        if 'memory_warning' in values and v <= values['memory_warning']:
            raise ValueError('記憶體嚴重閾值必須大於警告閾值')
        return v
    
    @validator('disk_critical')
    def disk_critical_must_be_greater_than_warning(cls, v, values):
        if 'disk_warning' in values and v <= values['disk_warning']:
            raise ValueError('磁碟嚴重閾值必須大於警告閾值')
        return v
    
    @validator('load_critical')
    def load_critical_must_be_greater_than_warning(cls, v, values):
        if 'load_warning' in values and v <= values['load_warning']:
            raise ValueError('負載嚴重閾值必須大於警告閾值')
        return v


class MonitoringThresholdsResponse(BaseModel):
    """監控閾值查詢回應模型"""
    cpu_warning: float = Field(..., description="CPU警告閾值 (%)")
    cpu_critical: float = Field(..., description="CPU嚴重閾值 (%)")
    memory_warning: float = Field(..., description="記憶體警告閾值 (%)")
    memory_critical: float = Field(..., description="記憶體嚴重閾值 (%)")
    disk_warning: float = Field(..., description="磁碟警告閾值 (%)")
    disk_critical: float = Field(..., description="磁碟嚴重閾值 (%)")
    load_warning: float = Field(..., description="負載警告閾值")
    load_critical: float = Field(..., description="負載嚴重閾值")
    updated_at: Optional[str] = Field(None, description="更新時間")


# === API 回應模型 ===

class MonitoringDataResponse(BaseModel):
    """監控數據 API 回應模型"""
    success: bool = Field(..., description="請求是否成功")
    data: Dict[str, Any] = Field(..., description="監控數據")
    message: str = Field(..., description="回應訊息")
    timestamp: Optional[str] = Field(None, description="回應時間")


class MonitoringSummaryResponse(BaseModel):
    """監控摘要 API 回應模型"""
    success: bool = Field(..., description="請求是否成功")
    data: MonitoringSummary = Field(..., description="監控摘要數據")
    message: str = Field(..., description="回應訊息")
    timestamp: Optional[str] = Field(None, description="回應時間")


class BatchMonitoringResponse(BaseModel):
    """批量監控 API 回應模型"""
    success: bool = Field(..., description="請求是否成功")
    data: Dict[str, Any] = Field(..., description="批量監控數據")
    message: str = Field(..., description="回應訊息")
    timestamp: Optional[str] = Field(None, description="回應時間")


class ServerMonitoringStatus(BaseModel):
    """伺服器監控狀態模型"""
    server_id: int = Field(..., description="伺服器ID")
    server_name: str = Field(..., description="伺服器名稱")
    host: str = Field(..., description="主機地址")
    status: str = Field(..., description="監控狀態")
    summary: Optional[MonitoringSummary] = Field(None, description="監控摘要")
    metrics: Optional[Dict[str, Any]] = Field(None, description="詳細監控數據")
    error: Optional[str] = Field(None, description="錯誤訊息")


class BatchMonitoringSummary(BaseModel):
    """批量監控摘要模型"""
    total_servers: int = Field(..., description="總伺服器數")
    success_count: int = Field(..., description="成功數量")
    failed_count: int = Field(..., description="失敗數量")
    collection_time: str = Field(..., description="收集時間")


class BatchMonitoringData(BaseModel):
    """批量監控數據模型"""  
    servers: List[ServerMonitoringStatus] = Field(..., description="伺服器監控狀態列表")
    summary: BatchMonitoringSummary = Field(..., description="批量監控摘要")


# === 歷史數據相關模型 (預留) ===

class TimeRangeFilter(str, Enum):
    """時間範圍過濾器"""
    HOUR_1 = "1h"
    HOUR_6 = "6h"
    HOUR_24 = "24h"
    DAY_7 = "7d"
    DAY_30 = "30d"


class HistoricalDataRequest(BaseModel):
    """歷史數據請求模型"""
    server_id: int = Field(..., description="伺服器ID")
    metric_types: List[MetricTypeFilter] = Field(..., description="監控指標類型列表")
    time_range: TimeRangeFilter = Field(..., description="時間範圍")
    start_time: Optional[datetime] = Field(None, description="開始時間")
    end_time: Optional[datetime] = Field(None, description="結束時間")
    aggregation: Optional[str] = Field("avg", description="聚合方式 (avg/max/min)")


class DataPoint(BaseModel):
    """數據點模型"""
    timestamp: str = Field(..., description="時間戳")
    value: float = Field(..., description="數值")
    alert_level: Optional[AlertLevelEnum] = Field(None, description="警告等級")


class HistoricalMetricData(BaseModel):
    """歷史監控數據模型"""
    metric_type: MetricTypeFilter = Field(..., description="監控指標類型")
    metric_name: str = Field(..., description="指標名稱")
    unit: str = Field(..., description="單位")
    data_points: List[DataPoint] = Field(..., description="數據點列表")
    summary: Dict[str, float] = Field(..., description="統計摘要")


class HistoricalDataResponse(BaseModel):
    """歷史數據回應模型"""
    success: bool = Field(..., description="請求是否成功")
    data: List[HistoricalMetricData] = Field(..., description="歷史監控數據")
    query_info: Dict[str, Any] = Field(..., description="查詢資訊")
    message: str = Field(..., description="回應訊息")