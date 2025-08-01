"""Initial migration: create servers, system_metrics, system_info tables

Revision ID: 30ac87cf17dc
Revises: 
Create Date: 2025-07-28 18:14:29.701363

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '30ac87cf17dc'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('servers',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='伺服器唯一識別碼'),
    sa.Column('name', sa.String(length=100), nullable=False, comment='伺服器顯示名稱'),
    sa.Column('ip_address', sa.String(length=45), nullable=False, comment='IP位址（支援IPv4/IPv6）'),
    sa.Column('description', sa.Text(), nullable=True, comment='伺服器描述'),
    sa.Column('ssh_port', sa.Integer(), nullable=False, comment='SSH連接埠'),
    sa.Column('username', sa.String(length=50), nullable=False, comment='SSH登入用戶名'),
    sa.Column('password_encrypted', sa.Text(), nullable=True, comment='AES-256-GCM加密密碼'),
    sa.Column('private_key_encrypted', sa.Text(), nullable=True, comment='AES-256-GCM加密私鑰'),
    sa.Column('public_key', sa.Text(), nullable=True, comment='SSH公鑰'),
    sa.Column('status', sa.Enum('online', 'offline', 'warning', 'error', 'unknown', name='server_status'), nullable=False, comment='伺服器連接狀態'),
    sa.Column('connection_timeout', sa.Integer(), nullable=True, comment='連接超時時間（秒）'),
    sa.Column('command_timeout', sa.Integer(), nullable=True, comment='指令執行超時時間（秒）'),
    sa.Column('max_connections', sa.Integer(), nullable=True, comment='最大並發連接數'),
    sa.Column('monitoring_enabled', sa.Boolean(), nullable=True, comment='是否啟用監控'),
    sa.Column('monitoring_interval', sa.Integer(), nullable=True, comment='監控間隔（秒）'),
    sa.Column('last_connected_at', sa.DateTime(), nullable=True, comment='最後成功連接時間'),
    sa.Column('last_error', sa.Text(), nullable=True, comment='最後連接錯誤訊息'),
    sa.Column('connection_attempts', sa.Integer(), nullable=True, comment='連續連接失敗次數'),
    sa.Column('tags', sa.Text(), nullable=True, comment='JSON格式的標籤列表'),
    sa.Column('created_at', sa.DateTime(), nullable=False, comment='建立時間'),
    sa.Column('updated_at', sa.DateTime(), nullable=False, comment='更新時間'),
    sa.CheckConstraint('command_timeout > 0', name=op.f('ck_servers_ck_servers_command_timeout')),
    sa.CheckConstraint('connection_timeout > 0', name=op.f('ck_servers_ck_servers_connection_timeout')),
    sa.CheckConstraint('max_connections > 0', name=op.f('ck_servers_ck_servers_max_connections')),
    sa.CheckConstraint('monitoring_interval >= 10', name=op.f('ck_servers_ck_servers_monitoring_interval')),
    sa.CheckConstraint('password_encrypted IS NOT NULL OR private_key_encrypted IS NOT NULL', name=op.f('ck_servers_ck_servers_auth_required')),
    sa.CheckConstraint('ssh_port > 0 AND ssh_port <= 65535', name=op.f('ck_servers_ck_servers_ssh_port')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_servers')),
    sa.UniqueConstraint('ip_address', 'ssh_port', name='uq_servers_ip_port'),
    sa.UniqueConstraint('name', name='uq_servers_name'),
    comment='伺服器配置表 - 儲存監控目標伺服器的連接資訊和配置'
    )
    op.create_index('idx_servers_created', 'servers', ['created_at'], unique=False)
    op.create_index('idx_servers_ip', 'servers', ['ip_address'], unique=False)
    op.create_index('idx_servers_monitoring', 'servers', ['monitoring_enabled'], unique=False)
    op.create_index('idx_servers_status', 'servers', ['status'], unique=False)
    op.create_table('system_info',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='系統資訊唯一識別碼'),
    sa.Column('server_id', sa.Integer(), nullable=False, comment='關聯的伺服器ID'),
    sa.Column('hostname', sa.String(length=255), nullable=True, comment='主機名稱'),
    sa.Column('fqdn', sa.String(length=255), nullable=True, comment='完全限定域名'),
    sa.Column('os_name', sa.String(length=100), nullable=True, comment='作業系統名稱'),
    sa.Column('os_version', sa.String(length=100), nullable=True, comment='作業系統版本'),
    sa.Column('os_release', sa.String(length=100), nullable=True, comment='作業系統發行版'),
    sa.Column('os_architecture', sa.String(length=20), nullable=True, comment='系統架構'),
    sa.Column('kernel_version', sa.String(length=100), nullable=True, comment='核心版本'),
    sa.Column('cpu_model', sa.String(length=255), nullable=True, comment='CPU型號'),
    sa.Column('cpu_vendor', sa.String(length=100), nullable=True, comment='CPU廠商'),
    sa.Column('cpu_architecture', sa.String(length=20), nullable=True, comment='CPU架構'),
    sa.Column('cpu_cores_physical', sa.Integer(), nullable=True, comment='實體核心數'),
    sa.Column('cpu_cores_logical', sa.Integer(), nullable=True, comment='邏輯核心數'),
    sa.Column('cpu_threads_per_core', sa.Integer(), nullable=True, comment='每核心執行緒數'),
    sa.Column('cpu_frequency_base_mhz', sa.Float(), nullable=True, comment='基礎時脈頻率(MHz)'),
    sa.Column('cpu_frequency_max_mhz', sa.Float(), nullable=True, comment='最大時脈頻率(MHz)'),
    sa.Column('cpu_cache_l1_kb', sa.Integer(), nullable=True, comment='L1快取大小(KB)'),
    sa.Column('cpu_cache_l2_kb', sa.Integer(), nullable=True, comment='L2快取大小(KB)'),
    sa.Column('cpu_cache_l3_kb', sa.Integer(), nullable=True, comment='L3快取大小(KB)'),
    sa.Column('memory_total_mb', sa.Integer(), nullable=True, comment='總實體記憶體(MB)'),
    sa.Column('memory_slots_total', sa.Integer(), nullable=True, comment='記憶體插槽總數'),
    sa.Column('memory_slots_used', sa.Integer(), nullable=True, comment='已使用記憶體插槽數'),
    sa.Column('memory_type', sa.String(length=20), nullable=True, comment='記憶體類型(DDR3/DDR4等)'),
    sa.Column('memory_speed_mhz', sa.Integer(), nullable=True, comment='記憶體速度(MHz)'),
    sa.Column('disk_total_gb', sa.Float(), nullable=True, comment='總磁碟容量(GB)'),
    sa.Column('disk_count', sa.Integer(), nullable=True, comment='磁碟數量'),
    sa.Column('disk_type', sa.String(length=20), nullable=True, comment='主要磁碟類型(HDD/SSD)'),
    sa.Column('filesystems', sa.Text(), nullable=True, comment='檔案系統資訊(JSON)'),
    sa.Column('mount_points', sa.Text(), nullable=True, comment='掛載點資訊(JSON)'),
    sa.Column('network_interfaces', sa.Text(), nullable=True, comment='網路介面資訊(JSON)'),
    sa.Column('network_interfaces_count', sa.Integer(), nullable=True, comment='網路介面數量'),
    sa.Column('primary_interface', sa.String(length=50), nullable=True, comment='主要網路介面名稱'),
    sa.Column('primary_ip_address', sa.String(length=45), nullable=True, comment='主要IP位址'),
    sa.Column('python_version', sa.String(length=20), nullable=True, comment='Python版本'),
    sa.Column('docker_installed', sa.Boolean(), nullable=True, comment='是否安裝Docker'),
    sa.Column('docker_version', sa.String(length=50), nullable=True, comment='Docker版本'),
    sa.Column('virtualization_type', sa.String(length=50), nullable=True, comment='虛擬化類型'),
    sa.Column('hypervisor', sa.String(length=100), nullable=True, comment='虛擬化平台'),
    sa.Column('is_virtual', sa.Boolean(), nullable=True, comment='是否為虛擬機'),
    sa.Column('boot_time', sa.DateTime(timezone=True), nullable=True, comment='系統啟動時間'),
    sa.Column('uptime_seconds', sa.BigInteger(), nullable=True, comment='系統運行時間(秒)'),
    sa.Column('timezone', sa.String(length=50), nullable=True, comment='系統時區'),
    sa.Column('system_serial', sa.String(length=100), nullable=True, comment='系統序號'),
    sa.Column('motherboard_serial', sa.String(length=100), nullable=True, comment='主機板序號'),
    sa.Column('bios_version', sa.String(length=100), nullable=True, comment='BIOS版本'),
    sa.Column('bios_date', sa.String(length=20), nullable=True, comment='BIOS日期'),
    sa.Column('last_updated', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='最後更新時間'),
    sa.Column('collection_version', sa.String(length=20), nullable=True, comment='收集程式版本'),
    sa.Column('collection_method', sa.String(length=50), nullable=True, comment='收集方法'),
    sa.Column('raw_data', sa.Text(), nullable=True, comment='原始收集數據(JSON)'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='建立時間'),
    sa.ForeignKeyConstraint(['server_id'], ['servers.id'], name=op.f('fk_system_info_server_id_servers'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_system_info')),
    sa.UniqueConstraint('server_id', name=op.f('uq_system_info_server_id')),
    comment='系統資訊表 - 儲存伺服器的詳細硬體和軟體資訊'
    )
    op.create_index('idx_system_info_hostname', 'system_info', ['hostname'], unique=False)
    op.create_index('idx_system_info_os', 'system_info', ['os_name', 'os_version'], unique=False)
    op.create_index('idx_system_info_server', 'system_info', ['server_id'], unique=False)
    op.create_index('idx_system_info_updated', 'system_info', ['last_updated'], unique=False)
    op.create_table('system_metrics',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='指標記錄唯一識別碼'),
    sa.Column('server_id', sa.Integer(), nullable=False, comment='關聯的伺服器ID'),
    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='數據收集時間'),
    sa.Column('cpu_usage_percent', sa.Float(), nullable=True, comment='CPU使用率百分比'),
    sa.Column('cpu_user_percent', sa.Float(), nullable=True, comment='用戶態CPU使用率'),
    sa.Column('cpu_system_percent', sa.Float(), nullable=True, comment='系統態CPU使用率'),
    sa.Column('cpu_idle_percent', sa.Float(), nullable=True, comment='CPU空閒率'),
    sa.Column('cpu_iowait_percent', sa.Float(), nullable=True, comment='IO等待時間百分比'),
    sa.Column('cpu_count', sa.Integer(), nullable=True, comment='CPU核心數'),
    sa.Column('cpu_frequency_mhz', sa.Float(), nullable=True, comment='CPU頻率(MHz)'),
    sa.Column('load_average_1m', sa.Float(), nullable=True, comment='1分鐘平均負載'),
    sa.Column('load_average_5m', sa.Float(), nullable=True, comment='5分鐘平均負載'),
    sa.Column('load_average_15m', sa.Float(), nullable=True, comment='15分鐘平均負載'),
    sa.Column('memory_total_mb', sa.Integer(), nullable=True, comment='總記憶體(MB)'),
    sa.Column('memory_used_mb', sa.Integer(), nullable=True, comment='已用記憶體(MB)'),
    sa.Column('memory_available_mb', sa.Integer(), nullable=True, comment='可用記憶體(MB)'),
    sa.Column('memory_free_mb', sa.Integer(), nullable=True, comment='空閒記憶體(MB)'),
    sa.Column('memory_cached_mb', sa.Integer(), nullable=True, comment='快取記憶體(MB)'),
    sa.Column('memory_buffers_mb', sa.Integer(), nullable=True, comment='緩衝區記憶體(MB)'),
    sa.Column('memory_usage_percent', sa.Float(), nullable=True, comment='記憶體使用率百分比'),
    sa.Column('swap_total_mb', sa.Integer(), nullable=True, comment='總Swap空間(MB)'),
    sa.Column('swap_used_mb', sa.Integer(), nullable=True, comment='已用Swap空間(MB)'),
    sa.Column('swap_free_mb', sa.Integer(), nullable=True, comment='空閒Swap空間(MB)'),
    sa.Column('swap_usage_percent', sa.Float(), nullable=True, comment='Swap使用率百分比'),
    sa.Column('disk_total_gb', sa.Float(), nullable=True, comment='磁碟總容量(GB)'),
    sa.Column('disk_used_gb', sa.Float(), nullable=True, comment='磁碟已用空間(GB)'),
    sa.Column('disk_free_gb', sa.Float(), nullable=True, comment='磁碟可用空間(GB)'),
    sa.Column('disk_usage_percent', sa.Float(), nullable=True, comment='磁碟使用率百分比'),
    sa.Column('disk_read_bytes_per_sec', sa.BigInteger(), nullable=True, comment='磁碟讀取速度(bytes/s)'),
    sa.Column('disk_write_bytes_per_sec', sa.BigInteger(), nullable=True, comment='磁碟寫入速度(bytes/s)'),
    sa.Column('disk_read_iops', sa.Integer(), nullable=True, comment='磁碟讀取IOPS'),
    sa.Column('disk_write_iops', sa.Integer(), nullable=True, comment='磁碟寫入IOPS'),
    sa.Column('network_interface', sa.String(length=50), nullable=True, comment='網路介面名稱'),
    sa.Column('network_bytes_sent_per_sec', sa.BigInteger(), nullable=True, comment='網路發送速度(bytes/s)'),
    sa.Column('network_bytes_recv_per_sec', sa.BigInteger(), nullable=True, comment='網路接收速度(bytes/s)'),
    sa.Column('network_packets_sent_per_sec', sa.Integer(), nullable=True, comment='網路發送封包數/秒'),
    sa.Column('network_packets_recv_per_sec', sa.Integer(), nullable=True, comment='網路接收封包數/秒'),
    sa.Column('network_errors_in', sa.Integer(), nullable=True, comment='網路接收錯誤數'),
    sa.Column('network_errors_out', sa.Integer(), nullable=True, comment='網路發送錯誤數'),
    sa.Column('uptime_seconds', sa.BigInteger(), nullable=True, comment='系統運行時間(秒)'),
    sa.Column('processes_total', sa.Integer(), nullable=True, comment='總程序數'),
    sa.Column('processes_running', sa.Integer(), nullable=True, comment='運行中程序數'),
    sa.Column('processes_sleeping', sa.Integer(), nullable=True, comment='睡眠程序數'),
    sa.Column('processes_zombie', sa.Integer(), nullable=True, comment='僵屍程序數'),
    sa.Column('collection_duration_ms', sa.Integer(), nullable=True, comment='數據收集耗時(毫秒)'),
    sa.Column('collection_success', sa.Boolean(), nullable=False, comment='數據收集是否成功'),
    sa.Column('error_message', sa.Text(), nullable=True, comment='收集錯誤訊息'),
    sa.ForeignKeyConstraint(['server_id'], ['servers.id'], name=op.f('fk_system_metrics_server_id_servers'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_system_metrics')),
    comment='系統指標表 - 儲存時間序列的監控數據'
    )
    op.create_index('idx_metrics_server_success', 'system_metrics', ['server_id', 'collection_success'], unique=False)
    op.create_index('idx_metrics_server_time_range', 'system_metrics', ['server_id', 'timestamp', 'collection_success'], unique=False)
    op.create_index('idx_metrics_server_timestamp', 'system_metrics', ['server_id', 'timestamp'], unique=False)
    op.create_index('idx_metrics_timestamp', 'system_metrics', ['timestamp'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('idx_metrics_timestamp', table_name='system_metrics')
    op.drop_index('idx_metrics_server_timestamp', table_name='system_metrics')
    op.drop_index('idx_metrics_server_time_range', table_name='system_metrics')
    op.drop_index('idx_metrics_server_success', table_name='system_metrics')
    op.drop_table('system_metrics')
    op.drop_index('idx_system_info_updated', table_name='system_info')
    op.drop_index('idx_system_info_server', table_name='system_info')
    op.drop_index('idx_system_info_os', table_name='system_info')
    op.drop_index('idx_system_info_hostname', table_name='system_info')
    op.drop_table('system_info')
    op.drop_index('idx_servers_status', table_name='servers')
    op.drop_index('idx_servers_monitoring', table_name='servers')
    op.drop_index('idx_servers_ip', table_name='servers')
    op.drop_index('idx_servers_created', table_name='servers')
    op.drop_table('servers')
    # ### end Alembic commands ###
