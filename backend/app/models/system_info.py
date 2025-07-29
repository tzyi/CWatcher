"""
CWatcher 系統資訊模型

定義系統詳細資訊的資料庫模型
包含硬體規格、作業系統、軟體環境等相對靜態的資訊
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey,
    Index, Boolean, Float, BigInteger
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db.base import Base


class SystemInfo(Base):
    """
    系統資訊表
    
    儲存伺服器的詳細系統資訊
    相對靜態的資料，不頻繁更新
    """
    __tablename__ = "system_info"
    
    # 主鍵
    id = Column(Integer, primary_key=True, autoincrement=True, comment="系統資訊唯一識別碼")
    
    # 外鍵關係
    server_id = Column(
        Integer,
        ForeignKey("servers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # 一對一關係
        comment="關聯的伺服器ID"
    )
    
    # 基本系統資訊
    hostname = Column(String(255), nullable=True, comment="主機名稱")
    fqdn = Column(String(255), nullable=True, comment="完全限定域名")
    
    # 作業系統資訊
    os_name = Column(String(100), nullable=True, comment="作業系統名稱")
    os_version = Column(String(100), nullable=True, comment="作業系統版本")
    os_release = Column(String(100), nullable=True, comment="作業系統發行版")
    os_architecture = Column(String(20), nullable=True, comment="系統架構")
    kernel_version = Column(String(100), nullable=True, comment="核心版本")
    
    # CPU 硬體資訊
    cpu_model = Column(String(255), nullable=True, comment="CPU型號")
    cpu_vendor = Column(String(100), nullable=True, comment="CPU廠商")
    cpu_architecture = Column(String(20), nullable=True, comment="CPU架構")  
    cpu_cores_physical = Column(Integer, nullable=True, comment="實體核心數")
    cpu_cores_logical = Column(Integer, nullable=True, comment="邏輯核心數")
    cpu_threads_per_core = Column(Integer, nullable=True, comment="每核心執行緒數")
    cpu_frequency_base_mhz = Column(Float, nullable=True, comment="基礎時脈頻率(MHz)")
    cpu_frequency_max_mhz = Column(Float, nullable=True, comment="最大時脈頻率(MHz)")
    cpu_cache_l1_kb = Column(Integer, nullable=True, comment="L1快取大小(KB)")
    cpu_cache_l2_kb = Column(Integer, nullable=True, comment="L2快取大小(KB)")
    cpu_cache_l3_kb = Column(Integer, nullable=True, comment="L3快取大小(KB)")
    
    # 記憶體硬體資訊
    memory_total_mb = Column(Integer, nullable=True, comment="總實體記憶體(MB)")
    memory_slots_total = Column(Integer, nullable=True, comment="記憶體插槽總數")
    memory_slots_used = Column(Integer, nullable=True, comment="已使用記憶體插槽數")
    memory_type = Column(String(20), nullable=True, comment="記憶體類型(DDR3/DDR4等)")
    memory_speed_mhz = Column(Integer, nullable=True, comment="記憶體速度(MHz)")
    
    # 磁碟硬體資訊
    disk_total_gb = Column(Float, nullable=True, comment="總磁碟容量(GB)")
    disk_count = Column(Integer, nullable=True, comment="磁碟數量")
    disk_type = Column(String(20), nullable=True, comment="主要磁碟類型(HDD/SSD)")
    filesystems = Column(Text, nullable=True, comment="檔案系統資訊(JSON)")
    mount_points = Column(Text, nullable=True, comment="掛載點資訊(JSON)")
    
    # 網路硬體資訊
    network_interfaces = Column(Text, nullable=True, comment="網路介面資訊(JSON)")
    network_interfaces_count = Column(Integer, nullable=True, comment="網路介面數量")
    primary_interface = Column(String(50), nullable=True, comment="主要網路介面名稱")
    primary_ip_address = Column(String(45), nullable=True, comment="主要IP位址")
    
    # 軟體環境資訊
    python_version = Column(String(20), nullable=True, comment="Python版本")
    docker_installed = Column(Boolean, nullable=True, comment="是否安裝Docker")
    docker_version = Column(String(50), nullable=True, comment="Docker版本")
    
    # 虛擬化資訊
    virtualization_type = Column(String(50), nullable=True, comment="虛擬化類型")
    hypervisor = Column(String(100), nullable=True, comment="虛擬化平台")
    is_virtual = Column(Boolean, nullable=True, comment="是否為虛擬機")
    
    # 系統狀態
    boot_time = Column(DateTime(timezone=True), nullable=True, comment="系統啟動時間")
    uptime_seconds = Column(BigInteger, nullable=True, comment="系統運行時間(秒)")
    timezone = Column(String(50), nullable=True, comment="系統時區")
    
    # 硬體序號資訊
    system_serial = Column(String(100), nullable=True, comment="系統序號")
    motherboard_serial = Column(String(100), nullable=True, comment="主機板序號")
    bios_version = Column(String(100), nullable=True, comment="BIOS版本")
    bios_date = Column(String(20), nullable=True, comment="BIOS日期")
    
    # 資料收集資訊
    last_updated = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="最後更新時間"
    )
    collection_version = Column(String(20), nullable=True, comment="收集程式版本")
    collection_method = Column(String(50), nullable=True, comment="收集方法")
    raw_data = Column(Text, nullable=True, comment="原始收集數據(JSON)")
    
    # 時間戳記
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="建立時間"
    )
    
    # 關聯關係
    server = relationship("Server", back_populates="system_info")
    
    # 表約束和索引
    __table_args__ = (
        # 索引
        Index('idx_system_info_server', 'server_id'),
        Index('idx_system_info_updated', 'last_updated'),
        Index('idx_system_info_hostname', 'hostname'),
        Index('idx_system_info_os', 'os_name', 'os_version'),
        
        # 表註釋
        {'comment': '系統資訊表 - 儲存伺服器的詳細硬體和軟體資訊'}
    )
    
    def __repr__(self) -> str:
        return f"<SystemInfo(id={self.id}, server_id={self.server_id}, hostname='{self.hostname}')>"
    
    def __str__(self) -> str:
        return f"System Info for {self.hostname or f'Server {self.server_id}'}"
    
    @property
    def os_full_name(self) -> str:
        """取得完整作業系統名稱"""
        parts = []
        if self.os_name:
            parts.append(self.os_name)
        if self.os_version:
            parts.append(self.os_version)
        if self.os_release:
            parts.append(f"({self.os_release})")
        return " ".join(parts) if parts else "Unknown"
    
    @property
    def cpu_full_name(self) -> str:
        """取得完整 CPU 名稱"""
        if self.cpu_model:
            return self.cpu_model
        elif self.cpu_vendor:
            return f"{self.cpu_vendor} CPU"
        else:
            return "Unknown CPU"
    
    @property
    def memory_gb(self) -> float:
        """取得記憶體容量(GB)"""
        return round(self.memory_total_mb / 1024, 2) if self.memory_total_mb else 0
    
    @property
    def cpu_core_info(self) -> str:
        """取得 CPU 核心資訊字串"""
        if self.cpu_cores_physical and self.cpu_cores_logical:
            if self.cpu_cores_physical == self.cpu_cores_logical:
                return f"{self.cpu_cores_physical} cores"
            else:
                return f"{self.cpu_cores_physical} cores / {self.cpu_cores_logical} threads"
        elif self.cpu_cores_logical:
            return f"{self.cpu_cores_logical} cores"
        else:
            return "Unknown"
    
    @property
    def uptime_formatted(self) -> str:
        """格式化系統運行時間"""
        if not self.uptime_seconds:
            return "Unknown"
        
        days = self.uptime_seconds // 86400
        hours = (self.uptime_seconds % 86400) // 3600
        minutes = (self.uptime_seconds % 3600) // 60
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    def to_dict(self) -> dict:
        """轉換為字典格式"""
        return {
            'id': self.id,
            'server_id': self.server_id,
            'hostname': self.hostname,
            'fqdn': self.fqdn,
            'os': {
                'name': self.os_name,
                'version': self.os_version,
                'release': self.os_release,
                'architecture': self.os_architecture,
                'kernel_version': self.kernel_version,
                'full_name': self.os_full_name
            },
            'cpu': {
                'model': self.cpu_model,
                'vendor': self.cpu_vendor,
                'architecture': self.cpu_architecture,
                'cores_physical': self.cpu_cores_physical,
                'cores_logical': self.cpu_cores_logical,
                'frequency_base_mhz': self.cpu_frequency_base_mhz,
                'frequency_max_mhz': self.cpu_frequency_max_mhz,
                'full_name': self.cpu_full_name,
                'core_info': self.cpu_core_info
            },
            'memory': {
                'total_mb': self.memory_total_mb,
                'total_gb': self.memory_gb,
                'type': self.memory_type,
                'speed_mhz': self.memory_speed_mhz,
                'slots_total': self.memory_slots_total,
                'slots_used': self.memory_slots_used
            },
            'disk': {
                'total_gb': self.disk_total_gb,
                'count': self.disk_count,
                'type': self.disk_type
            },
            'network': {
                'interfaces_count': self.network_interfaces_count,
                'primary_interface': self.primary_interface,
                'primary_ip': self.primary_ip_address
            },
            'virtualization': {
                'is_virtual': self.is_virtual,
                'type': self.virtualization_type,
                'hypervisor': self.hypervisor
            },
            'system': {
                'boot_time': self.boot_time.isoformat() if self.boot_time else None,
                'uptime_seconds': self.uptime_seconds,
                'uptime_formatted': self.uptime_formatted,
                'timezone': self.timezone
            },
            'collection': {
                'last_updated': self.last_updated.isoformat() if self.last_updated else None,
                'version': self.collection_version,
                'method': self.collection_method
            }
        }