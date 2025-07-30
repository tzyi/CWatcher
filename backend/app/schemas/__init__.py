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
    DiskMetrics,
    NetworkMetrics,
    AllMetrics,
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
    CollectionInfo,
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
    "DiskMetrics",
    "NetworkMetrics",
    "AllMetrics",
    "CollectionInfo",
    
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