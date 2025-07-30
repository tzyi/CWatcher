"""
CWatcher 數據清理與歸檔服務

專門負責舊數據清理、數據歸檔和儲存空間監控
支援自動化清理策略和數據生命週期管理
"""

import asyncio
import logging
import os
import shutil
import time
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import text, func, desc, and_, or_, delete
from contextlib import asynccontextmanager

from core.deps import get_db
from db.base import get_sync_db
from models.system_metrics import SystemMetrics
from models.server import Server
from core.config import settings

# 設定日誌
logger = logging.getLogger(__name__)


class CleanupLevel(Enum):
    """清理等級"""
    BASIC = "basic"       # 基本清理（30天以上）
    AGGRESSIVE = "aggressive"  # 積極清理（7天以上）
    EMERGENCY = "emergency"    # 緊急清理（1天以上）


class DataType(Enum):
    """數據類型"""
    METRICS = "metrics"   # 監控數據
    LOGS = "logs"        # 日誌數據
    ARCHIVES = "archives" # 歸檔數據


@dataclass
class CleanupStats:
    """清理統計"""
    cleaned_records: int = 0
    cleaned_size_bytes: int = 0
    archived_records: int = 0
    archived_size_bytes: int = 0
    cleanup_time: float = 0.0
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cleaned_records": self.cleaned_records,
            "cleaned_size_mb": round(self.cleaned_size_bytes / (1024 * 1024), 2),
            "archived_records": self.archived_records,
            "archived_size_mb": round(self.archived_size_bytes / (1024 * 1024), 2),
            "cleanup_time": self.cleanup_time,
            "errors": self.errors
        }


@dataclass
class StorageInfo:
    """儲存空間資訊"""
    total_space_bytes: int
    used_space_bytes: int
    free_space_bytes: int
    usage_percentage: float
    database_size_bytes: int = 0
    archive_size_bytes: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_space_gb": round(self.total_space_bytes / (1024**3), 2),
            "used_space_gb": round(self.used_space_bytes / (1024**3), 2),
            "free_space_gb": round(self.free_space_bytes / (1024**3), 2),
            "usage_percentage": self.usage_percentage,
            "database_size_mb": round(self.database_size_bytes / (1024**2), 2),
            "archive_size_mb": round(self.archive_size_bytes / (1024**2), 2)
        }


@dataclass
class CleanupPolicy:
    """清理策略"""
    name: str
    retention_days: int
    enabled: bool = True
    archive_before_delete: bool = True
    batch_size: int = 1000
    
    # 條件篩選
    server_ids: Optional[List[int]] = None
    collection_success_only: bool = False
    error_records_only: bool = False


class DataCleaner:
    """數據清理器"""
    
    # 預設清理策略
    DEFAULT_POLICIES = {
        CleanupLevel.BASIC: CleanupPolicy(
            name="基本清理（30天）",
            retention_days=30,
            archive_before_delete=True,
            batch_size=1000
        ),
        CleanupLevel.AGGRESSIVE: CleanupPolicy(
            name="積極清理（7天）",
            retention_days=7,
            archive_before_delete=False,
            batch_size=2000
        ),
        CleanupLevel.EMERGENCY: CleanupPolicy(
            name="緊急清理（1天）",
            retention_days=1,
            archive_before_delete=False,
            batch_size=5000,
            error_records_only=True
        )
    }
    
    def __init__(self, archive_path: str = "backend/app/archives"):
        self.archive_path = Path(archive_path)
        self.archive_path.mkdir(parents=True, exist_ok=True)
        self.db_session_factory = get_sync_db
    
    async def cleanup_old_data(
        self,
        cleanup_level: CleanupLevel = CleanupLevel.BASIC,
        custom_policy: Optional[CleanupPolicy] = None
    ) -> CleanupStats:
        """
        清理舊數據主要入口
        
        Args:
            cleanup_level: 清理等級
            custom_policy: 自定義清理策略
        """
        start_time = time.time()
        stats = CleanupStats()
        
        try:
            # 使用自定義策略或預設策略
            policy = custom_policy or self.DEFAULT_POLICIES[cleanup_level]
            
            logger.info(f"開始執行數據清理: {policy.name}")
            
            # 計算清理時間點
            cutoff_date = datetime.now() - timedelta(days=policy.retention_days)
            
            # 執行歸檔
            if policy.archive_before_delete:
                archive_stats = await self._archive_old_data(cutoff_date, policy)
                stats.archived_records = archive_stats.archived_records
                stats.archived_size_bytes = archive_stats.archived_size_bytes
                stats.errors.extend(archive_stats.errors)
            
            # 執行清理
            cleanup_stats = await self._delete_old_data(cutoff_date, policy)
            stats.cleaned_records = cleanup_stats.cleaned_records
            stats.cleaned_size_bytes = cleanup_stats.cleaned_size_bytes
            stats.errors.extend(cleanup_stats.errors)
            
            stats.cleanup_time = time.time() - start_time
            
            logger.info(f"數據清理完成: 清理 {stats.cleaned_records} 筆記錄, "
                       f"歸檔 {stats.archived_records} 筆記錄, 耗時 {stats.cleanup_time:.2f}s")
            
            return stats
            
        except Exception as e:
            logger.error(f"數據清理失敗: {e}")
            stats.errors.append(str(e))
            stats.cleanup_time = time.time() - start_time
            return stats
    
    async def _archive_old_data(self, cutoff_date: datetime, policy: CleanupPolicy) -> CleanupStats:
        """歸檔舊數據"""
        stats = CleanupStats()
        
        try:
            db = self.db_session_factory()
            try:
                # 構建查詢條件
                query = db.query(SystemMetrics).filter(
                    SystemMetrics.timestamp < cutoff_date
                )
                
                # 應用額外過濾條件
                if policy.server_ids:
                    query = query.filter(SystemMetrics.server_id.in_(policy.server_ids))
                
                if policy.collection_success_only:
                    query = query.filter(SystemMetrics.collection_success == True)
                elif policy.error_records_only:
                    query = query.filter(SystemMetrics.collection_success == False)
                
                # 分批處理歸檔
                total_records = query.count()
                if total_records == 0:
                    return stats
                
                logger.info(f"開始歸檔 {total_records} 筆舊數據到 {cutoff_date}")
                
                # 創建歸檔目錄
                archive_date = cutoff_date.strftime("%Y%m%d")
                archive_dir = self.archive_path / f"metrics_{archive_date}"
                archive_dir.mkdir(exist_ok=True)
                
                batch_count = 0
                offset = 0
                
                while offset < total_records:
                    # 批量查詢
                    batch_records = query.offset(offset).limit(policy.batch_size).all()
                    if not batch_records:
                        break
                    
                    # 轉換為 JSON 格式
                    archive_data = []
                    for record in batch_records:
                        archive_data.append({
                            "id": record.id,
                            "server_id": record.server_id,
                            "timestamp": record.timestamp.isoformat(),
                            "cpu_usage_percent": record.cpu_usage_percent,
                            "memory_usage_percent": record.memory_usage_percent,
                            "disk_usage_percent": record.disk_usage_percent,
                            "load_average_1m": record.load_average_1m,
                            "memory_total_mb": record.memory_total_mb,
                            "disk_total_gb": record.disk_total_gb,
                            "network_bytes_sent_per_sec": record.network_bytes_sent_per_sec,
                            "network_bytes_recv_per_sec": record.network_bytes_recv_per_sec,
                            "collection_success": record.collection_success,
                            "error_message": record.error_message
                        })
                    
                    # 寫入歸檔檔案
                    archive_file = archive_dir / f"batch_{batch_count:04d}.json"
                    with open(archive_file, 'w', encoding='utf-8') as f:
                        json.dump(archive_data, f, ensure_ascii=False, indent=2)
                    
                    # 計算檔案大小
                    file_size = archive_file.stat().st_size
                    stats.archived_size_bytes += file_size
                    stats.archived_records += len(batch_records)
                    
                    batch_count += 1
                    offset += policy.batch_size
                    
                    # 進度日誌
                    if batch_count % 10 == 0:
                        progress = (offset / total_records) * 100
                        logger.info(f"歸檔進度: {progress:.1f}% ({offset}/{total_records})")
                
                # 創建歸檔摘要檔案
                summary_file = archive_dir / "archive_summary.json"
                with open(summary_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "archive_date": cutoff_date.isoformat(),
                        "total_records": stats.archived_records,
                        "total_size_bytes": stats.archived_size_bytes,
                        "batch_files": batch_count,
                        "policy": {
                            "name": policy.name,
                            "retention_days": policy.retention_days,
                            "batch_size": policy.batch_size
                        },
                        "created_at": datetime.now().isoformat()
                    }, f, ensure_ascii=False, indent=2)
                
                logger.info(f"歸檔完成: {stats.archived_records} 筆記錄, "
                           f"大小 {stats.archived_size_bytes / (1024**2):.2f}MB")
                
                return stats
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"歸檔失敗: {e}")
            stats.errors.append(str(e))
            return stats
    
    async def _delete_old_data(self, cutoff_date: datetime, policy: CleanupPolicy) -> CleanupStats:
        """刪除舊數據"""
        stats = CleanupStats()
        
        try:
            db = self.db_session_factory()
            try:
                # 構建刪除查詢
                delete_query = delete(SystemMetrics).where(
                    SystemMetrics.timestamp < cutoff_date
                )
                
                # 應用額外過濾條件
                if policy.server_ids:
                    delete_query = delete_query.where(
                        SystemMetrics.server_id.in_(policy.server_ids)
                    )
                
                if policy.collection_success_only:
                    delete_query = delete_query.where(
                        SystemMetrics.collection_success == True
                    )
                elif policy.error_records_only:
                    delete_query = delete_query.where(
                        SystemMetrics.collection_success == False
                    )
                
                # 先計算要刪除的記錄數
                count_query = db.query(SystemMetrics).filter(
                    SystemMetrics.timestamp < cutoff_date
                )
                if policy.server_ids:
                    count_query = count_query.filter(
                        SystemMetrics.server_id.in_(policy.server_ids)
                    )
                if policy.collection_success_only:
                    count_query = count_query.filter(
                        SystemMetrics.collection_success == True
                    )
                elif policy.error_records_only:
                    count_query = count_query.filter(
                        SystemMetrics.collection_success == False
                    )
                
                total_to_delete = count_query.count()
                
                if total_to_delete == 0:
                    logger.info("沒有需要清理的舊數據")
                    return stats
                
                logger.info(f"開始刪除 {total_to_delete} 筆舊數據 (早於 {cutoff_date})")
                
                # 執行刪除
                result = db.execute(delete_query)
                stats.cleaned_records = result.rowcount
                
                # 估算清理的空間大小 (假設每筆記錄約 1KB)
                stats.cleaned_size_bytes = stats.cleaned_records * 1024
                
                # 提交事務
                db.commit()
                
                logger.info(f"清理完成: 刪除 {stats.cleaned_records} 筆記錄")
                
                return stats
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"刪除舊數據失敗: {e}")
            stats.errors.append(str(e))
            return stats
    
    async def get_storage_info(self) -> StorageInfo:
        """取得儲存空間資訊"""
        try:
            # 取得系統磁碟使用情況
            disk_usage = shutil.disk_usage("/")
            
            storage_info = StorageInfo(
                total_space_bytes=disk_usage.total,
                used_space_bytes=disk_usage.used,
                free_space_bytes=disk_usage.free,
                usage_percentage=round((disk_usage.used / disk_usage.total) * 100, 2)
            )
            
            # 計算資料庫大小
            try:
                db = self.db_session_factory()
                try:
                    # PostgreSQL 查詢資料庫大小
                    result = db.execute(text(
                        "SELECT pg_database_size(current_database()) as db_size"
                    )).fetchone()
                    if result:
                        storage_info.database_size_bytes = result.db_size
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"取得資料庫大小失敗: {e}")
            
            # 計算歸檔目錄大小
            try:
                archive_size = sum(
                    f.stat().st_size 
                    for f in self.archive_path.rglob('*') 
                    if f.is_file()
                )
                storage_info.archive_size_bytes = archive_size
            except Exception as e:
                logger.warning(f"取得歸檔大小失敗: {e}")
            
            return storage_info
            
        except Exception as e:
            logger.error(f"取得儲存空間資訊失敗: {e}")
            return StorageInfo(
                total_space_bytes=0,
                used_space_bytes=0,
                free_space_bytes=0,
                usage_percentage=0.0
            )
    
    async def cleanup_archive_files(self, days_to_keep: int = 90) -> CleanupStats:
        """清理舊的歸檔檔案"""
        stats = CleanupStats()
        start_time = time.time()
        
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            # 掃描歸檔目錄
            for archive_dir in self.archive_path.iterdir():
                if not archive_dir.is_dir():
                    continue
                
                try:
                    # 解析目錄名稱中的日期
                    if archive_dir.name.startswith("metrics_"):
                        date_str = archive_dir.name.replace("metrics_", "")
                        archive_date = datetime.strptime(date_str, "%Y%m%d")
                        
                        if archive_date < cutoff_date:
                            # 計算目錄大小
                            dir_size = sum(
                                f.stat().st_size 
                                for f in archive_dir.rglob('*') 
                                if f.is_file()
                            )
                            
                            # 刪除目錄
                            shutil.rmtree(archive_dir)
                            
                            stats.cleaned_records += 1
                            stats.cleaned_size_bytes += dir_size
                            
                            logger.info(f"清理歸檔目錄: {archive_dir.name}")
                            
                except Exception as e:
                    logger.warning(f"清理歸檔目錄 {archive_dir.name} 失敗: {e}")
                    stats.errors.append(f"清理 {archive_dir.name} 失敗: {e}")
            
            stats.cleanup_time = time.time() - start_time
            
            logger.info(f"歸檔檔案清理完成: 清理 {stats.cleaned_records} 個目錄, "
                       f"釋放 {stats.cleaned_size_bytes / (1024**2):.2f}MB")
            
            return stats
            
        except Exception as e:
            logger.error(f"清理歸檔檔案失敗: {e}")
            stats.errors.append(str(e))
            stats.cleanup_time = time.time() - start_time
            return stats
    
    async def get_cleanup_recommendations(self) -> Dict[str, Any]:
        """取得清理建議"""
        try:
            storage_info = await self.get_storage_info()
            
            recommendations = []
            
            # 儲存空間檢查
            if storage_info.usage_percentage > 90:
                recommendations.append({
                    "level": "critical",
                    "type": "storage_space",
                    "message": "磁碟使用率超過 90%，建議立即執行緊急清理",
                    "action": "emergency_cleanup",
                    "priority": 1
                })
            elif storage_info.usage_percentage > 80:
                recommendations.append({
                    "level": "warning",
                    "type": "storage_space",
                    "message": "磁碟使用率超過 80%，建議執行積極清理",
                    "action": "aggressive_cleanup",
                    "priority": 2
                })
            
            # 資料庫大小檢查
            db_size_gb = storage_info.database_size_bytes / (1024**3)
            if db_size_gb > 10:
                recommendations.append({
                    "level": "info",
                    "type": "database_size",
                    "message": f"資料庫大小 {db_size_gb:.1f}GB，建議定期清理舊數據",
                    "action": "basic_cleanup",
                    "priority": 3
                })
            
            # 歸檔大小檢查
            archive_size_gb = storage_info.archive_size_bytes / (1024**3)
            if archive_size_gb > 5:
                recommendations.append({
                    "level": "info",
                    "type": "archive_size",
                    "message": f"歸檔大小 {archive_size_gb:.1f}GB，建議清理舊歸檔檔案",
                    "action": "cleanup_archives",
                    "priority": 4
                })
            
            # 檢查舊數據數量
            try:
                db = self.db_session_factory()
                try:
                    # 檢查30天以上的數據
                    old_data_count = db.query(SystemMetrics).filter(
                        SystemMetrics.timestamp < datetime.now() - timedelta(days=30)
                    ).count()
                    
                    if old_data_count > 100000:  # 超過10萬筆
                        recommendations.append({
                            "level": "warning",
                            "type": "old_data",
                            "message": f"發現 {old_data_count} 筆30天以上的舊數據，建議執行清理",
                            "action": "basic_cleanup",
                            "priority": 2
                        })
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"檢查舊數據數量失敗: {e}")
            
            # 排序建議（按優先級）
            recommendations.sort(key=lambda x: x["priority"])
            
            return {
                "storage_info": storage_info.to_dict(),
                "recommendations": recommendations,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"取得清理建議失敗: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


class ScheduledCleaner:
    """定時清理器"""
    
    def __init__(self, cleaner: DataCleaner):
        self.cleaner = cleaner
        self.is_running = False
    
    async def start_scheduled_cleanup(
        self,
        cleanup_interval_hours: int = 24,
        cleanup_level: CleanupLevel = CleanupLevel.BASIC
    ):
        """開始定時清理"""
        if self.is_running:
            logger.warning("定時清理已在運行中")
            return
        
        self.is_running = True
        logger.info(f"開始定時清理，間隔 {cleanup_interval_hours} 小時")
        
        try:
            while self.is_running:
                # 執行清理
                stats = await self.cleaner.cleanup_old_data(cleanup_level)
                
                if stats.errors:
                    logger.error(f"定時清理出現錯誤: {stats.errors}")
                else:
                    logger.info(f"定時清理完成: {stats.to_dict()}")
                
                # 等待下次清理
                await asyncio.sleep(cleanup_interval_hours * 3600)
                
        except asyncio.CancelledError:
            logger.info("定時清理被取消")
        except Exception as e:
            logger.error(f"定時清理發生異常: {e}")
        finally:
            self.is_running = False
    
    def stop_scheduled_cleanup(self):
        """停止定時清理"""
        self.is_running = False
        logger.info("停止定時清理")


# 全域實例
data_cleaner = DataCleaner()
scheduled_cleaner = ScheduledCleaner(data_cleaner)


# 便利函數
async def cleanup_old_monitoring_data(
    days_to_keep: int = 30,
    archive_before_delete: bool = True
) -> CleanupStats:
    """清理舊監控數據的便利函數"""
    policy = CleanupPolicy(
        name=f"自定義清理（{days_to_keep}天）",
        retention_days=days_to_keep,
        archive_before_delete=archive_before_delete
    )
    return await data_cleaner.cleanup_old_data(custom_policy=policy)


async def get_storage_status() -> StorageInfo:
    """取得儲存狀態的便利函數"""
    return await data_cleaner.get_storage_info()


async def get_cleanup_suggestions() -> Dict[str, Any]:
    """取得清理建議的便利函數"""
    return await data_cleaner.get_cleanup_recommendations()


if __name__ == "__main__":
    # 測試數據清理器
    
    async def test_storage_info():
        """測試儲存空間資訊"""
        print("💾 測試儲存空間資訊...")
        
        try:
            storage_info = await data_cleaner.get_storage_info()
            
            print(f"✅ 儲存空間資訊:")
            print(f"  - 總空間: {storage_info.total_space_bytes / (1024**3):.2f}GB")
            print(f"  - 已用空間: {storage_info.used_space_bytes / (1024**3):.2f}GB")
            print(f"  - 可用空間: {storage_info.free_space_bytes / (1024**3):.2f}GB")
            print(f"  - 使用率: {storage_info.usage_percentage}%")
            print(f"  - 資料庫大小: {storage_info.database_size_bytes / (1024**2):.2f}MB")
            
        except Exception as e:
            print(f"❌ 儲存空間資訊測試失敗: {e}")
    
    async def test_cleanup_recommendations():
        """測試清理建議"""
        print("\n📋 測試清理建議...")
        
        try:
            recommendations = await data_cleaner.get_cleanup_recommendations()
            
            print(f"✅ 清理建議:")
            
            if "recommendations" in recommendations:
                for i, rec in enumerate(recommendations["recommendations"], 1):
                    print(f"  {i}. [{rec['level'].upper()}] {rec['message']}")
                    print(f"     建議動作: {rec['action']}")
            else:
                print("  目前無清理建議")
                
        except Exception as e:
            print(f"❌ 清理建議測試失敗: {e}")
    
    async def test_data_cleanup():
        """測試數據清理"""
        print("\n🧹 測試數據清理...")
        
        try:
            # 創建測試清理策略
            test_policy = CleanupPolicy(
                name="測試清理",
                retention_days=365,  # 保留1年以上的數據進行測試
                archive_before_delete=True,
                batch_size=100
            )
            
            stats = await data_cleaner.cleanup_old_data(custom_policy=test_policy)
            
            print(f"✅ 數據清理完成:")
            print(f"  - 清理記錄: {stats.cleaned_records} 筆")
            print(f"  - 歸檔記錄: {stats.archived_records} 筆")
            print(f"  - 處理時間: {stats.cleanup_time:.2f}s")
            
            if stats.errors:
                print(f"  - 錯誤: {stats.errors}")
                
        except Exception as e:
            print(f"❌ 數據清理測試失敗: {e}")
    
    async def test_complete():
        """完整測試"""
        print("=" * 50)
        print("🧪 CWatcher 數據清理與歸檔服務測試")
        print("=" * 50)
        
        await test_storage_info()
        await test_cleanup_recommendations()
        await test_data_cleanup()
        
        print("\n✅ 數據清理與歸檔服務測試完成")
    
    # 執行測試
    import asyncio
    asyncio.run(test_complete())