"""
CWatcher 伺服器模型

定義伺服器配置的資料庫模型
包含 SSH 連接資訊、加密憑證存儲和狀態管理
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Column, Integer, String, Text, Enum, DateTime, 
    Boolean, Index, CheckConstraint, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db.base import Base


class Server(Base):
    """
    伺服器配置表
    
    儲存監控目標伺服器的基本資訊和連接配置
    支援密碼和 SSH 金鑰兩種認證方式
    """
    __tablename__ = "servers"
    
    # 主鍵
    id = Column(Integer, primary_key=True, autoincrement=True, comment="伺服器唯一識別碼")
    
    # 基本資訊
    name = Column(String(100), nullable=False, comment="伺服器顯示名稱")
    ip_address = Column(String(45), nullable=False, comment="IP位址（支援IPv4/IPv6）")
    description = Column(Text, nullable=True, comment="伺服器描述")
    
    # SSH 連接配置
    ssh_port = Column(Integer, default=22, nullable=False, comment="SSH連接埠")
    username = Column(String(50), nullable=False, comment="SSH登入用戶名")
    
    # 加密認證資訊
    password_encrypted = Column(Text, nullable=True, comment="AES-256-GCM加密密碼")
    private_key_encrypted = Column(Text, nullable=True, comment="AES-256-GCM加密私鑰")
    public_key = Column(Text, nullable=True, comment="SSH公鑰")
    
    # 狀態管理
    status = Column(
        Enum('online', 'offline', 'warning', 'error', 'unknown', name='server_status'),
        default='unknown',
        nullable=False,
        comment="伺服器連接狀態"
    )
    
    # 連接設定
    connection_timeout = Column(Integer, default=10, comment="連接超時時間（秒）")
    command_timeout = Column(Integer, default=30, comment="指令執行超時時間（秒）")
    max_connections = Column(Integer, default=3, comment="最大並發連接數")
    
    # 監控設定
    monitoring_enabled = Column(Boolean, default=True, comment="是否啟用監控")
    monitoring_interval = Column(Integer, default=30, comment="監控間隔（秒）")
    
    # 最後連接資訊
    last_connected_at = Column(DateTime, nullable=True, comment="最後成功連接時間")
    last_error = Column(Text, nullable=True, comment="最後連接錯誤訊息")
    connection_attempts = Column(Integer, default=0, comment="連續連接失敗次數")
    
    # 標籤系統
    tags = Column(Text, nullable=True, comment="JSON格式的標籤列表")
    
    # 時間戳記
    created_at = Column(DateTime, default=func.now(), nullable=False, comment="建立時間")
    updated_at = Column(
        DateTime, 
        default=func.now(), 
        onupdate=func.now(), 
        nullable=False, 
        comment="更新時間"
    )
    
    # 關聯關係
    system_metrics = relationship(
        "SystemMetrics", 
        back_populates="server", 
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    
    system_info = relationship(
        "SystemInfo", 
        back_populates="server", 
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False  # 一對一關係
    )
    
    # 表約束
    __table_args__ = (
        # 唯一約束
        UniqueConstraint('name', name='uq_servers_name'),
        UniqueConstraint('ip_address', 'ssh_port', name='uq_servers_ip_port'),
        
        # 檢查約束
        CheckConstraint('ssh_port > 0 AND ssh_port <= 65535', name='ck_servers_ssh_port'),
        CheckConstraint('connection_timeout > 0', name='ck_servers_connection_timeout'),
        CheckConstraint('command_timeout > 0', name='ck_servers_command_timeout'),
        CheckConstraint('max_connections > 0', name='ck_servers_max_connections'),
        CheckConstraint('monitoring_interval >= 10', name='ck_servers_monitoring_interval'),
        CheckConstraint(
            'password_encrypted IS NOT NULL OR private_key_encrypted IS NOT NULL',
            name='ck_servers_auth_required'
        ),
        
        # 索引
        Index('idx_servers_status', 'status'),
        Index('idx_servers_monitoring', 'monitoring_enabled'),
        Index('idx_servers_created', 'created_at'),
        Index('idx_servers_ip', 'ip_address'),
        
        # 表註釋
        {'comment': '伺服器配置表 - 儲存監控目標伺服器的連接資訊和配置'}
    )
    
    def __repr__(self) -> str:
        return f"<Server(id={self.id}, name='{self.name}', ip='{self.ip_address}', status='{self.status}')>"
    
    def __str__(self) -> str:
        return f"{self.name} ({self.ip_address})"
    
    @property
    def is_online(self) -> bool:
        """檢查伺服器是否在線"""
        return self.status == 'online'
    
    @property
    def has_connection_issues(self) -> bool:
        """檢查是否有連接問題"""
        return self.connection_attempts > 3
    
    @property
    def connection_info(self) -> dict:
        """取得連接資訊字典"""
        return {
            'host': self.ip_address,
            'port': self.ssh_port,
            'username': self.username,
            'timeout': self.connection_timeout
        }