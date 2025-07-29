#!/usr/bin/env python3
"""
創建 CWatcher 示例數據腳本

創建一些示例伺服器和監控數據用於測試和演示
"""

import asyncio
from datetime import datetime, timedelta
import random
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import AsyncSessionLocal
from app.models.server import Server
from app.models.system_metrics import SystemMetrics
from app.models.system_info import SystemInfo
from app.core.config import settings


async def create_sample_servers(session: AsyncSession) -> list:
    """創建示例伺服器"""
    servers_data = [
        {
            "name": "Web Server 1",
            "ip_address": "192.168.1.10",
            "description": "主要Web伺服器 - Nginx + PHP",
            "ssh_port": 22,
            "username": "ubuntu",
            "password_encrypted": "encrypted_password_1",
            "status": "online",
            "monitoring_enabled": True,
            "monitoring_interval": 30,
        },
        {
            "name": "Database Server",
            "ip_address": "192.168.1.20", 
            "description": "MySQL 主資料庫伺服器",
            "ssh_port": 22,
            "username": "admin",
            "password_encrypted": "encrypted_password_2",
            "status": "online",
            "monitoring_enabled": True,
            "monitoring_interval": 15,
        },
        {
            "name": "API Server",
            "ip_address": "192.168.1.30",
            "description": "RESTful API 後端服務",
            "ssh_port": 2222,
            "username": "apiuser",
            "private_key_encrypted": "encrypted_private_key_1",
            "status": "warning",
            "monitoring_enabled": True,
            "monitoring_interval": 30,
        },
        {
            "name": "Cache Server",
            "ip_address": "192.168.1.40",
            "description": "Redis 快取伺服器",
            "ssh_port": 22,
            "username": "redis",
            "password_encrypted": "encrypted_password_3",
            "status": "offline",
            "monitoring_enabled": False,
            "monitoring_interval": 60,
            "last_error": "Connection timeout after 10 seconds",
        },
    ]
    
    servers = []
    for server_data in servers_data:
        server = Server(**server_data)
        session.add(server)
        servers.append(server)
    
    await session.commit()
    
    # 刷新以取得 ID
    for server in servers:
        await session.refresh(server)
    
    print(f"✅ 創建了 {len(servers)} 個示例伺服器")
    return servers


async def create_sample_system_info(session: AsyncSession, servers: list):
    """創建示例系統資訊"""
    system_info_data = [
        {
            "server_id": servers[0].id,
            "hostname": "web-server-01",
            "fqdn": "web-server-01.example.com",
            "os_name": "Ubuntu",
            "os_version": "20.04.3 LTS",
            "os_release": "Focal Fossa",
            "os_architecture": "x86_64",
            "kernel_version": "5.4.0-96-generic",
            "cpu_model": "Intel(R) Xeon(R) CPU E5-2686 v4 @ 2.30GHz",
            "cpu_vendor": "Intel",
            "cpu_cores_physical": 4,
            "cpu_cores_logical": 8,
            "cpu_frequency_base_mhz": 2300.0,
            "memory_total_mb": 8192,
            "memory_type": "DDR4",
            "disk_total_gb": 100.0,
            "disk_type": "SSD",
            "primary_interface": "eth0",
            "primary_ip_address": "192.168.1.10",
            "is_virtual": True,
            "virtualization_type": "AWS EC2",
        },
        {
            "server_id": servers[1].id,
            "hostname": "db-server-01",
            "fqdn": "db-server-01.example.com",
            "os_name": "CentOS",
            "os_version": "8.4.2105",
            "os_release": "Core",
            "os_architecture": "x86_64", 
            "kernel_version": "4.18.0-305.3.1.el8.x86_64",
            "cpu_model": "AMD EPYC 7571 32-Core Processor",
            "cpu_vendor": "AMD",
            "cpu_cores_physical": 16,
            "cpu_cores_logical": 32,
            "cpu_frequency_base_mhz": 2550.0,
            "memory_total_mb": 16384,
            "memory_type": "DDR4",
            "disk_total_gb": 500.0,
            "disk_type": "NVMe SSD",
            "primary_interface": "ens3",
            "primary_ip_address": "192.168.1.20",
            "is_virtual": False,
        },
    ]
    
    for info_data in system_info_data:
        system_info = SystemInfo(**info_data)
        session.add(system_info)
    
    await session.commit()
    print(f"✅ 創建了 {len(system_info_data)} 個系統資訊記錄")


async def create_sample_metrics(session: AsyncSession, servers: list):
    """創建示例監控指標"""
    print("🔄 創建示例監控指標...")
    
    # 為每個在線伺服器創建過去24小時的監控數據
    now = datetime.utcnow()
    
    for server in servers[:2]:  # 只為前兩個伺服器創建數據
        print(f"   為伺服器 {server.name} 創建監控數據...")
        
        # 創建過去24小時的數據，每5分鐘一個數據點
        for i in range(288):  # 24 * 60 / 5 = 288 個數據點
            timestamp = now - timedelta(minutes=i * 5)
            
            # 生成模擬的監控數據
            base_cpu = 20 + random.random() * 60  # 20-80% CPU
            base_memory = 30 + random.random() * 50  # 30-80% Memory
            base_disk = 40 + random.random() * 40   # 40-80% Disk
            
            # 添加一些波動
            cpu_usage = max(0, min(100, base_cpu + random.gauss(0, 10)))
            memory_usage = max(0, min(100, base_memory + random.gauss(0, 5)))
            disk_usage = max(0, min(100, base_disk + random.gauss(0, 2)))
            
            metrics = SystemMetrics(
                server_id=server.id,
                timestamp=timestamp,
                
                # CPU 指標
                cpu_usage_percent=round(cpu_usage, 1),
                cpu_user_percent=round(cpu_usage * 0.7, 1),
                cpu_system_percent=round(cpu_usage * 0.2, 1),
                cpu_idle_percent=round(100 - cpu_usage, 1),
                cpu_count=4,
                cpu_frequency_mhz=2300.0 + random.random() * 400,
                load_average_1m=round(cpu_usage / 25, 2),
                load_average_5m=round(cpu_usage / 30, 2),
                load_average_15m=round(cpu_usage / 35, 2),
                
                # 記憶體指標
                memory_total_mb=8192,
                memory_used_mb=int(8192 * memory_usage / 100),
                memory_available_mb=int(8192 * (100 - memory_usage) / 100),
                memory_usage_percent=round(memory_usage, 1),
                memory_cached_mb=int(8192 * 0.15),
                
                # 磁碟指標
                disk_total_gb=100.0,
                disk_used_gb=round(100.0 * disk_usage / 100, 2),
                disk_free_gb=round(100.0 * (100 - disk_usage) / 100, 2),
                disk_usage_percent=round(disk_usage, 1),
                disk_read_bytes_per_sec=random.randint(1024*1024, 10*1024*1024),
                disk_write_bytes_per_sec=random.randint(512*1024, 5*1024*1024),
                
                # 網路指標
                network_interface="eth0",
                network_bytes_sent_per_sec=random.randint(1024*100, 1024*1024*10),
                network_bytes_recv_per_sec=random.randint(1024*100, 1024*1024*10),
                
                # 系統指標
                uptime_seconds=random.randint(86400, 86400*30),  # 1-30天
                processes_total=random.randint(150, 300),
                processes_running=random.randint(1, 5),
                processes_sleeping=random.randint(140, 290),
                
                # 收集資訊
                collection_duration_ms=random.randint(100, 1000),
                collection_success=True,
            )
            
            session.add(metrics)
            
            # 每50個記錄提交一次
            if i % 50 == 0:
                await session.commit()
    
    await session.commit()
    print("✅ 創建了示例監控指標數據")


async def main():
    """主函數"""
    print("🚀 開始創建 CWatcher 示例數據...")
    
    async with AsyncSessionLocal() as session:
        try:
            # 創建示例伺服器
            servers = await create_sample_servers(session)
            
            # 創建系統資訊
            await create_sample_system_info(session, servers)
            
            # 創建監控指標
            await create_sample_metrics(session, servers)
            
            print("\n🎉 示例數據創建完成！")
            print(f"   - {len(servers)} 個伺服器")
            print("   - 2 個系統資訊記錄")
            print("   - 約 576 個監控指標記錄（2個伺服器 × 288個數據點）")
            
        except Exception as e:
            print(f"❌ 創建示例數據失敗: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(main())