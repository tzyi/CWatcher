"""
CWatcher 系統指標模型

定義系統監控指標的時間序列資料庫模型
包含 CPU、記憶體、磁碟、網路等核心指標
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey,
    Index, Text, BigInteger, Boolean
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db.base import Base


class SystemMetrics(Base):
    """
    系統指標表
    
    儲存時間序列的系統監控數據
    支援 CPU、記憶體、磁碟、網路指標
    """
    __tablename__ = "system_metrics"
    
    # 主鍵
    id = Column(Integer, primary_key=True, autoincrement=True, comment="指標記錄唯一識別碼")
    
    # 外鍵關係
    server_id = Column(
        Integer,
        ForeignKey("servers.id", ondelete="CASCADE"),
        nullable=False,
        comment="關聯的伺服器ID"
    )
    
    # 時間戳記
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="數據收集時間"
    )
    
    # CPU 指標
    cpu_usage_percent = Column(Float, nullable=True, comment="CPU使用率百分比")
    cpu_user_percent = Column(Float, nullable=True, comment="用戶態CPU使用率")
    cpu_system_percent = Column(Float, nullable=True, comment="系統態CPU使用率")
    cpu_idle_percent = Column(Float, nullable=True, comment="CPU空閒率")
    cpu_iowait_percent = Column(Float, nullable=True, comment="IO等待時間百分比")
    cpu_count = Column(Integer, nullable=True, comment="CPU核心數")
    cpu_frequency_mhz = Column(Float, nullable=True, comment="CPU頻率(MHz)")
    load_average_1m = Column(Float, nullable=True, comment="1分鐘平均負載")
    load_average_5m = Column(Float, nullable=True, comment="5分鐘平均負載")  
    load_average_15m = Column(Float, nullable=True, comment="15分鐘平均負載")
    
    # 記憶體指標
    memory_total_mb = Column(Integer, nullable=True, comment="總記憶體(MB)")
    memory_used_mb = Column(Integer, nullable=True, comment="已用記憶體(MB)")
    memory_available_mb = Column(Integer, nullable=True, comment="可用記憶體(MB)")
    memory_free_mb = Column(Integer, nullable=True, comment="空閒記憶體(MB)")
    memory_cached_mb = Column(Integer, nullable=True, comment="快取記憶體(MB)")
    memory_buffers_mb = Column(Integer, nullable=True, comment="緩衝區記憶體(MB)")
    memory_usage_percent = Column(Float, nullable=True, comment="記憶體使用率百分比")
    
    # Swap 指標
    swap_total_mb = Column(Integer, nullable=True, comment="總Swap空間(MB)")
    swap_used_mb = Column(Integer, nullable=True, comment="已用Swap空間(MB)")
    swap_free_mb = Column(Integer, nullable=True, comment="空閒Swap空間(MB)")
    swap_usage_percent = Column(Float, nullable=True, comment="Swap使用率百分比")
    
    # 磁碟指標 (主要分割區)
    disk_total_gb = Column(Float, nullable=True, comment="磁碟總容量(GB)")
    disk_used_gb = Column(Float, nullable=True, comment="磁碟已用空間(GB)")
    disk_free_gb = Column(Float, nullable=True, comment="磁碟可用空間(GB)")
    disk_usage_percent = Column(Float, nullable=True, comment="磁碟使用率百分比")
    
    # 磁碟 I/O 指標
    disk_read_bytes_per_sec = Column(BigInteger, nullable=True, comment="磁碟讀取速度(bytes/s)")
    disk_write_bytes_per_sec = Column(BigInteger, nullable=True, comment="磁碟寫入速度(bytes/s)")
    disk_read_iops = Column(Integer, nullable=True, comment="磁碟讀取IOPS")
    disk_write_iops = Column(Integer, nullable=True, comment="磁碟寫入IOPS")
    
    # 網路指標 (主要網路介面)
    network_interface = Column(String(50), nullable=True, comment="網路介面名稱")
    network_bytes_sent_per_sec = Column(BigInteger, nullable=True, comment="網路發送速度(bytes/s)")
    network_bytes_recv_per_sec = Column(BigInteger, nullable=True, comment="網路接收速度(bytes/s)")
    network_packets_sent_per_sec = Column(Integer, nullable=True, comment="網路發送封包數/秒")
    network_packets_recv_per_sec = Column(Integer, nullable=True, comment="網路接收封包數/秒")
    network_errors_in = Column(Integer, nullable=True, comment="網路接收錯誤數")
    network_errors_out = Column(Integer, nullable=True, comment="網路發送錯誤數")
    
    # 系統指標
    uptime_seconds = Column(BigInteger, nullable=True, comment="系統運行時間(秒)")
    processes_total = Column(Integer, nullable=True, comment="總程序數")
    processes_running = Column(Integer, nullable=True, comment="運行中程序數")
    processes_sleeping = Column(Integer, nullable=True, comment="睡眠程序數")
    processes_zombie = Column(Integer, nullable=True, comment="僵屍程序數")
    
    # 狀態指標
    collection_duration_ms = Column(Integer, nullable=True, comment="數據收集耗時(毫秒)")
    collection_success = Column(Boolean, nullable=False, default=True, comment="數據收集是否成功")
    error_message = Column(Text, nullable=True, comment="收集錯誤訊息")
    
    # 關聯關係
    server = relationship("Server", back_populates="system_metrics")
    
    # 表約束和索引
    __table_args__ = (
        # 複合索引 - 查詢效能優化
        Index('idx_metrics_server_timestamp', 'server_id', 'timestamp'),
        Index('idx_metrics_timestamp', 'timestamp'),
        Index('idx_metrics_server_success', 'server_id', 'collection_success'),
        
        # 時間範圍查詢索引
        Index('idx_metrics_server_time_range', 'server_id', 'timestamp', 'collection_success'),
        
        # 表註釋
        {'comment': '系統指標表 - 儲存時間序列的監控數據'}
    )
    
    def __repr__(self) -> str:
        return f"<SystemMetrics(id={self.id}, server_id={self.server_id}, timestamp='{self.timestamp}')>"
    
    def __str__(self) -> str:
        return f"Metrics for Server {self.server_id} at {self.timestamp}"
    
    @property
    def cpu_usage_status(self) -> str:
        """取得 CPU 使用率狀態"""
        if self.cpu_usage_percent is None:
            return "unknown"
        elif self.cpu_usage_percent >= 90:
            return "critical"
        elif self.cpu_usage_percent >= 80:
            return "warning"
        else:
            return "normal"
    
    @property
    def memory_usage_status(self) -> str:
        """取得記憶體使用率狀態"""
        if self.memory_usage_percent is None:
            return "unknown"
        elif self.memory_usage_percent >= 95:
            return "critical"
        elif self.memory_usage_percent >= 85:
            return "warning"
        else:
            return "normal"
    
    @property
    def disk_usage_status(self) -> str:
        """取得磁碟使用率狀態"""
        if self.disk_usage_percent is None:
            return "unknown"
        elif self.disk_usage_percent >= 95:
            return "critical"
        elif self.disk_usage_percent >= 90:
            return "warning"
        else:
            return "normal"
    
    @property
    def overall_status(self) -> str:
        """計算整體系統狀態"""
        statuses = [
            self.cpu_usage_status,
            self.memory_usage_status, 
            self.disk_usage_status
        ]
        
        if "critical" in statuses:
            return "critical"
        elif "warning" in statuses:
            return "warning"
        elif "unknown" in statuses:
            return "unknown"
        else:
            return "normal"
            
    def to_dict(self) -> dict:
        """轉換為字典格式"""
        return {
            'id': self.id,
            'server_id': self.server_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'cpu': {
                'usage_percent': self.cpu_usage_percent,
                'user_percent': self.cpu_user_percent,
                'system_percent': self.cpu_system_percent,
                'idle_percent': self.cpu_idle_percent,
                'count': self.cpu_count,
                'frequency_mhz': self.cpu_frequency_mhz,
                'load_avg': {
                    '1m': self.load_average_1m,
                    '5m': self.load_average_5m,
                    '15m': self.load_average_15m
                }
            },
            'memory': {
                'total_mb': self.memory_total_mb,
                'used_mb': self.memory_used_mb,
                'available_mb': self.memory_available_mb,
                'usage_percent': self.memory_usage_percent,
                'cached_mb': self.memory_cached_mb
            },
            'disk': {
                'total_gb': self.disk_total_gb,
                'used_gb': self.disk_used_gb,
                'free_gb': self.disk_free_gb,
                'usage_percent': self.disk_usage_percent,
                'read_bytes_per_sec': self.disk_read_bytes_per_sec,
                'write_bytes_per_sec': self.disk_write_bytes_per_sec
            },
            'network': {
                'interface': self.network_interface,
                'bytes_sent_per_sec': self.network_bytes_sent_per_sec,
                'bytes_recv_per_sec': self.network_bytes_recv_per_sec,
                'errors_in': self.network_errors_in,
                'errors_out': self.network_errors_out
            },
            'collection': {
                'duration_ms': self.collection_duration_ms,
                'success': self.collection_success,
                'error_message': self.error_message
            }
        }