"""
CWatcher 系統資訊 Pydantic Schema

定義系統詳細資訊的 API 請求和回應資料結構
"""

from datetime import datetime
from typing import Optional, Dict, List
from pydantic import BaseModel, Field, ConfigDict


class OSInfo(BaseModel):
    """作業系統資訊"""
    name: Optional[str] = Field(None, description="作業系統名稱")
    version: Optional[str] = Field(None, description="作業系統版本")
    release: Optional[str] = Field(None, description="作業系統發行版")
    architecture: Optional[str] = Field(None, description="系統架構")
    kernel_version: Optional[str] = Field(None, description="核心版本")
    full_name: Optional[str] = Field(None, description="完整作業系統名稱")


class CPUInfo(BaseModel):
    """CPU 硬體資訊"""
    model: Optional[str] = Field(None, description="CPU型號")
    vendor: Optional[str] = Field(None, description="CPU廠商")
    architecture: Optional[str] = Field(None, description="CPU架構")
    cores_physical: Optional[int] = Field(None, description="實體核心數")
    cores_logical: Optional[int] = Field(None, description="邏輯核心數")
    threads_per_core: Optional[int] = Field(None, description="每核心執行緒數")
    frequency_base_mhz: Optional[float] = Field(None, description="基礎時脈頻率(MHz)")
    frequency_max_mhz: Optional[float] = Field(None, description="最大時脈頻率(MHz)")
    cache_l1_kb: Optional[int] = Field(None, description="L1快取大小(KB)")
    cache_l2_kb: Optional[int] = Field(None, description="L2快取大小(KB)")
    cache_l3_kb: Optional[int] = Field(None, description="L3快取大小(KB)")
    full_name: Optional[str] = Field(None, description="完整CPU名稱")
    core_info: Optional[str] = Field(None, description="核心資訊字串")


class MemoryInfo(BaseModel):
    """記憶體硬體資訊"""
    total_mb: Optional[int] = Field(None, description="總實體記憶體(MB)")
    total_gb: Optional[float] = Field(None, description="總實體記憶體(GB)")
    slots_total: Optional[int] = Field(None, description="記憶體插槽總數")
    slots_used: Optional[int] = Field(None, description="已使用記憶體插槽數")
    type: Optional[str] = Field(None, description="記憶體類型(DDR3/DDR4等)")
    speed_mhz: Optional[int] = Field(None, description="記憶體速度(MHz)")


class DiskInfo(BaseModel):
    """磁碟硬體資訊"""
    total_gb: Optional[float] = Field(None, description="總磁碟容量(GB)")
    count: Optional[int] = Field(None, description="磁碟數量")
    type: Optional[str] = Field(None, description="主要磁碟類型(HDD/SSD)")
    filesystems: Optional[Dict] = Field(None, description="檔案系統資訊")
    mount_points: Optional[Dict] = Field(None, description="掛載點資訊")


class NetworkInfo(BaseModel):
    """網路硬體資訊"""
    interfaces: Optional[Dict] = Field(None, description="網路介面資訊")
    interfaces_count: Optional[int] = Field(None, description="網路介面數量")
    primary_interface: Optional[str] = Field(None, description="主要網路介面名稱")
    primary_ip_address: Optional[str] = Field(None, description="主要IP位址")


class VirtualizationInfo(BaseModel):
    """虛擬化資訊"""
    is_virtual: Optional[bool] = Field(None, description="是否為虛擬機")
    type: Optional[str] = Field(None, description="虛擬化類型")
    hypervisor: Optional[str] = Field(None, description="虛擬化平台")


class SystemStatus(BaseModel):
    """系統狀態資訊"""
    boot_time: Optional[datetime] = Field(None, description="系統啟動時間")
    uptime_seconds: Optional[int] = Field(None, description="系統運行時間(秒)")
    uptime_formatted: Optional[str] = Field(None, description="格式化運行時間")
    timezone: Optional[str] = Field(None, description="系統時區")


class HardwareInfo(BaseModel):
    """硬體序號資訊"""
    system_serial: Optional[str] = Field(None, description="系統序號")
    motherboard_serial: Optional[str] = Field(None, description="主機板序號")
    bios_version: Optional[str] = Field(None, description="BIOS版本")
    bios_date: Optional[str] = Field(None, description="BIOS日期")


class CollectionInfo(BaseModel):
    """資料收集資訊"""
    last_updated: Optional[datetime] = Field(None, description="最後更新時間")
    version: Optional[str] = Field(None, description="收集程式版本")
    method: Optional[str] = Field(None, description="收集方法")


class SystemInfoCreate(BaseModel):
    """創建系統資訊請求資料結構"""
    server_id: int = Field(..., description="伺服器ID")
    hostname: Optional[str] = Field(None, description="主機名稱")
    fqdn: Optional[str] = Field(None, description="完全限定域名")
    os: Optional[OSInfo] = Field(None, description="作業系統資訊")
    cpu: Optional[CPUInfo] = Field(None, description="CPU資訊")
    memory: Optional[MemoryInfo] = Field(None, description="記憶體資訊")
    disk: Optional[DiskInfo] = Field(None, description="磁碟資訊")
    network: Optional[NetworkInfo] = Field(None, description="網路資訊")
    virtualization: Optional[VirtualizationInfo] = Field(None, description="虛擬化資訊")
    system: Optional[SystemStatus] = Field(None, description="系統狀態")
    hardware: Optional[HardwareInfo] = Field(None, description="硬體資訊")


class SystemInfoUpdate(BaseModel):
    """更新系統資訊請求資料結構"""
    hostname: Optional[str] = Field(None, description="主機名稱")
    fqdn: Optional[str] = Field(None, description="完全限定域名")
    os: Optional[OSInfo] = Field(None, description="作業系統資訊")
    cpu: Optional[CPUInfo] = Field(None, description="CPU資訊")
    memory: Optional[MemoryInfo] = Field(None, description="記憶體資訊")
    disk: Optional[DiskInfo] = Field(None, description="磁碟資訊")
    network: Optional[NetworkInfo] = Field(None, description="網路資訊")
    virtualization: Optional[VirtualizationInfo] = Field(None, description="虛擬化資訊")
    system: Optional[SystemStatus] = Field(None, description="系統狀態")
    hardware: Optional[HardwareInfo] = Field(None, description="硬體資訊")


class SystemInfoResponse(BaseModel):
    """系統資訊回應資料結構"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="系統資訊ID")
    server_id: int = Field(..., description="伺服器ID")
    hostname: Optional[str] = Field(None, description="主機名稱")
    fqdn: Optional[str] = Field(None, description="完全限定域名")
    
    os: Optional[OSInfo] = Field(None, description="作業系統資訊")
    cpu: Optional[CPUInfo] = Field(None, description="CPU資訊")
    memory: Optional[MemoryInfo] = Field(None, description="記憶體資訊")
    disk: Optional[DiskInfo] = Field(None, description="磁碟資訊")
    network: Optional[NetworkInfo] = Field(None, description="網路資訊")
    virtualization: Optional[VirtualizationInfo] = Field(None, description="虛擬化資訊")
    system: Optional[SystemStatus] = Field(None, description="系統狀態")
    hardware: Optional[HardwareInfo] = Field(None, description="硬體資訊")
    collection: Optional[CollectionInfo] = Field(None, description="收集資訊")
    
    created_at: datetime = Field(..., description="創建時間")


class SystemSummary(BaseModel):
    """系統摘要資訊"""
    hostname: Optional[str] = Field(None, description="主機名稱")
    os_name: Optional[str] = Field(None, description="作業系統")
    cpu_model: Optional[str] = Field(None, description="CPU型號")
    cpu_cores: Optional[int] = Field(None, description="CPU核心數")
    memory_gb: Optional[float] = Field(None, description="記憶體容量(GB)")
    disk_gb: Optional[float] = Field(None, description="磁碟容量(GB)")
    uptime_formatted: Optional[str] = Field(None, description="運行時間")
    is_virtual: Optional[bool] = Field(None, description="是否虛擬機")


class SystemComparisonItem(BaseModel):
    """系統比較項目"""
    server_id: int = Field(..., description="伺服器ID")
    server_name: str = Field(..., description="伺服器名稱")
    summary: SystemSummary = Field(..., description="系統摘要")


class SystemComparison(BaseModel):
    """系統比較結果"""
    servers: List[SystemComparisonItem] = Field(..., description="比較的伺服器列表")
    comparison_fields: List[str] = Field(..., description="比較欄位")


class SystemInfoStats(BaseModel):
    """系統資訊統計"""
    total_servers: int = Field(..., description="總伺服器數")
    os_distribution: Dict[str, int] = Field(..., description="作業系統分佈")
    cpu_vendor_distribution: Dict[str, int] = Field(..., description="CPU廠商分佈")
    virtual_vs_physical: Dict[str, int] = Field(..., description="虛擬機vs實體機統計")
    memory_ranges: Dict[str, int] = Field(..., description="記憶體容量分佈")
    disk_ranges: Dict[str, int] = Field(..., description="磁碟容量分佈")