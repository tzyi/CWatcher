#!/usr/bin/env python3
"""
CWatcher 定時任務系統測試腳本

驗證任務調度器、協調器和所有核心定時任務的功能
"""

import asyncio
import logging
import sys
import time
from datetime import datetime

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_task_scheduler():
    """測試任務調度器"""
    print("🕐 測試任務調度器...")
    
    try:
        from app.services.task_scheduler import task_scheduler
        
        # 啟動調度器
        await task_scheduler.start()
        print(f"✅ 調度器啟動成功")
        
        # 檢查註冊的任務
        tasks = task_scheduler.get_task_list()
        print(f"📋 註冊任務數: {len(tasks)}")
        
        for task in tasks:
            status = "啟用" if task["enabled"] else "停用"
            print(f"  - {task['name']} ({task['task_type']}): {status}")
            if task.get('next_run'):
                print(f"    下次執行: {task['next_run']}")
        
        # 測試手動執行任務
        print("\n🚀 測試手動執行健康檢查任務...")
        result = await task_scheduler.run_task_now("system_health_check")
        print(f"  執行狀態: {result.status.value}")
        print(f"  執行時間: {result.duration:.2f}s")
        if result.result_data:
            print(f"  結果數據: {len(result.result_data)} 項")
        
        # 獲取健康摘要
        health_summary = task_scheduler.get_task_health_summary()
        print(f"\n📊 調度器健康摘要:")
        print(f"  總任務數: {health_summary['total_tasks']}")
        print(f"  啟用任務: {health_summary['enabled_tasks']}")
        print(f"  成功率: {health_summary['success_rate']}%")
        print(f"  總執行次數: {health_summary['total_runs']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 調度器測試失敗: {e}")
        return False


async def test_task_coordinator():
    """測試任務協調器"""
    print("\n🎯 測試任務協調器...")
    
    try:
        from app.services.task_coordinator import task_coordinator
        
        # 啟動協調器
        await task_coordinator.start()
        print(f"✅ 協調器啟動成功")
        
        # 檢查協調器狀態
        status = task_coordinator.get_coordination_status()
        print(f"📊 協調器狀態:")
        print(f"  模式: {status['mode']}")
        print(f"  運行中: {status['is_running']}")
        print(f"  任務依賴數: {status['task_dependencies']}")
        print(f"  活躍資源鎖: {status['active_resource_locks']}")
        
        # 檢查系統負載
        print(f"📈 系統負載:")
        load = status['system_load']
        for key, value in load.items():
            print(f"  {key}: {value}")
        
        # 檢查統計數據
        print(f"📊 協調統計:")
        stats = status['stats']
        print(f"  解決衝突數: {stats['resource_conflicts_resolved']}")
        print(f"  依賴延遲數: {stats['dependency_delays']}")
        print(f"  優化節省時間: {stats['optimization_savings_seconds']:.2f}s")
        
        # 檢查任務依賴關係
        dependencies = task_coordinator.task_dependencies
        print(f"\n🔗 任務依賴關係:")
        for task_id, dep in dependencies.items():
            print(f"  {task_id}:")
            print(f"    優先級: {dep.priority}")
            if dep.depends_on:
                print(f"    依賴: {list(dep.depends_on)}")
            if dep.conflicts_with:
                print(f"    衝突: {list(dep.conflicts_with)}")
            print(f"    需要資源: {[r.value for r in dep.required_resources]}")
        
        return True
        
    except Exception as e:
        print(f"❌ 協調器測試失敗: {e}")
        return False


async def test_integration():
    """測試系統整合"""
    print("\n🔧 測試系統整合...")
    
    try:
        from app.services.task_scheduler import task_scheduler
        from app.services.task_coordinator import task_coordinator
        
        # 運行短時間觀察任務執行
        print("⏱️ 運行30秒觀察任務執行...")
        start_time = time.time()
        
        while time.time() - start_time < 30:
            await asyncio.sleep(5)
            
            # 檢查執行歷史
            history = task_scheduler.get_execution_history(limit=5)
            if history:
                latest = history[0]
                print(f"  最新執行: {latest['task_id']} - {latest['status']}")
        
        # 檢查失敗任務
        failed_tasks = task_scheduler.get_failed_tasks()
        if failed_tasks:
            print(f"⚠️ 發現失敗任務: {len(failed_tasks)} 個")
            for task in failed_tasks:
                print(f"  - {task['name']}: 連續失敗 {task['consecutive_failures']} 次")
        else:
            print("✅ 沒有失敗任務")
        
        # 最終狀態檢查
        scheduler_health = task_scheduler.get_task_health_summary()
        coordinator_status = task_coordinator.get_coordination_status()
        
        print(f"\n📋 最終狀態報告:")
        print(f"  調度器運行: {scheduler_health['scheduler_running']}")
        print(f"  協調器運行: {coordinator_status['is_running']}")
        print(f"  協調器模式: {coordinator_status['mode']}")
        print(f"  任務成功率: {scheduler_health['success_rate']}%")
        
        return True
        
    except Exception as e:
        print(f"❌ 整合測試失敗: {e}")
        return False


async def cleanup():
    """清理資源"""
    print("\n🧹 清理資源...")
    
    try:
        from app.services.task_coordinator import task_coordinator
        from app.services.task_scheduler import task_scheduler
        
        # 停止協調器
        await task_coordinator.stop()
        print("✅ 協調器已停止")
        
        # 停止調度器
        await task_scheduler.stop()
        print("✅ 調度器已停止")
        
    except Exception as e:
        print(f"⚠️ 清理時發生錯誤: {e}")


async def main():
    """主測試函數"""
    print("🚀 CWatcher 定時任務系統測試")
    print("=" * 50)
    
    success_count = 0
    total_tests = 3
    
    try:
        # 測試調度器
        if await test_task_scheduler():
            success_count += 1
        
        # 測試協調器
        if await test_task_coordinator():
            success_count += 1
        
        # 測試整合
        if await test_integration():
            success_count += 1
        
    except KeyboardInterrupt:
        print("\n⏹️ 測試被用戶中斷")
    except Exception as e:
        print(f"\n❌ 測試過程中發生未預期錯誤: {e}")
    finally:
        # 清理資源
        await cleanup()
    
    # 測試結果總結
    print("\n" + "=" * 50)
    print(f"📊 測試結果總結:")
    print(f"  成功: {success_count}/{total_tests}")
    print(f"  成功率: {success_count/total_tests*100:.1f}%")
    
    if success_count == total_tests:
        print("🎉 所有測試通過！定時任務系統運行正常")
        return 0
    else:
        print("⚠️ 部分測試失敗，請檢查系統狀態")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)