"""
CWatcher Pydantic Schemas

/e@	 API ǙWI Schema
"""

from schemas.server import (
    ServerBase,
    ServerCreate,
    ServerUpdate,
    ServerResponse,
    ServerListResponse,
    ServerStatusUpdate,
    ServerConnectionTest,
    ServerStats,
    ServerQueryParams,
    WebSocketMessage,
    ServerMonitoringMessage,
    ErrorResponse,
    ValidationErrorResponse,
)

from schemas.metrics import (
    CPUMetrics,
    MemoryMetrics,
    SwapMetrics,
    DiskMetrics,
    NetworkMetrics,
    SystemMetrics,
    CollectionInfo,
    SystemMetricsCreate,
    SystemMetricsResponse,
    MetricsHistoryResponse,
    MetricsQueryParams,
    MetricsSummary,
    RealTimeMetrics,
    AlertThresholds,
    MetricsAlert,
)

from schemas.system_info import (
    OSInfo,
    CPUInfo,
    MemoryInfo,
    DiskInfo,
    NetworkInfo,
    VirtualizationInfo,
    SystemStatus,
    HardwareInfo,
    SystemInfoCreate,
    SystemInfoUpdate,
    SystemInfoResponse,
    SystemSummary,
    SystemComparisonItem,
    SystemComparison,
    SystemInfoStats,
)

__all__ = [
    # Server schemas
    "ServerBase",
    "ServerCreate", 
    "ServerUpdate",
    "ServerResponse",
    "ServerListResponse",
    "ServerStatusUpdate",
    "ServerConnectionTest",
    "ServerStats",
    "ServerQueryParams",
    "WebSocketMessage",
    "ServerMonitoringMessage",
    "ErrorResponse",
    "ValidationErrorResponse",
    
    # Metrics schemas
    "CPUMetrics",
    "MemoryMetrics",
    "SwapMetrics", 
    "DiskMetrics",
    "NetworkMetrics",
    "SystemMetrics",
    "CollectionInfo",
    "SystemMetricsCreate",
    "SystemMetricsResponse",
    "MetricsHistoryResponse",
    "MetricsQueryParams",
    "MetricsSummary",
    "RealTimeMetrics",
    "AlertThresholds",
    "MetricsAlert",
    
    # System info schemas
    "OSInfo",
    "CPUInfo",
    "MemoryInfo",
    "DiskInfo",
    "NetworkInfo", 
    "VirtualizationInfo",
    "SystemStatus",
    "HardwareInfo",
    "SystemInfoCreate",
    "SystemInfoUpdate", 
    "SystemInfoResponse",
    "SystemSummary",
    "SystemComparisonItem",
    "SystemComparison",
    "SystemInfoStats",
]