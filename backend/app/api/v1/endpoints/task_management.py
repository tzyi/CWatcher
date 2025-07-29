"""
CWatcher 任務管理 API 端點

提供任務調度器的管理和監控功能
包括任務狀態查詢、控制和配置管理
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from app.services.task_scheduler import (
    task_scheduler, TaskExecutionResult, get_scheduler_status
)
from app.services.task_coordinator import task_coordinator, get_coordination_status
from app.core.deps import get_current_active_user

router = APIRouter()


class TaskControlRequest(BaseModel):
    """任務控制請求"""
    action: str = Field(..., description="操作類型: enable, disable, run_now, reset_failures")


class TaskRetryConfigRequest(BaseModel):
    """任務重試配置請求"""
    max_retries: Optional[int] = Field(None, ge=0, le=10, description="最大重試次數")
    retry_delay: Optional[float] = Field(None, ge=1, le=3600, description="重試延遲（秒）")
    auto_disable_threshold: Optional[int] = Field(None, ge=1, le=20, description="自動停用閾值")


@router.get("/status", summary="取得調度器狀態")
async def get_task_scheduler_status():
    """取得任務調度器運行狀態"""
    try:
        status = get_scheduler_status()
        health_summary = task_scheduler.get_task_health_summary()
        
        return {
            "scheduler_status": status,
            "health_summary": health_summary,
            "timestamp": task_scheduler.execution_history[-1].start_time.isoformat() if task_scheduler.execution_history else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取調度器狀態失敗: {str(e)}")


@router.get("/tasks", summary="取得任務清單")
async def get_task_list(
    include_disabled: bool = Query(False, description="是否包含已停用的任務"),
    task_type: Optional[str] = Query(None, description="按任務類型過濾")
):
    """取得所有註冊的任務清單"""
    try:
        tasks = task_scheduler.get_task_list()
        
        # 過濾停用的任務
        if not include_disabled:
            tasks = [task for task in tasks if task["enabled"]]
        
        # 按任務類型過濾
        if task_type:
            tasks = [task for task in tasks if task["task_type"] == task_type]
        
        return {
            "tasks": tasks,
            "total_count": len(tasks),
            "enabled_count": sum(1 for task in tasks if task["enabled"])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取任務清單失敗: {str(e)}")


@router.get("/tasks/{task_id}", summary="取得特定任務詳情")
async def get_task_details(task_id: str):
    """取得特定任務的詳細資訊"""
    try:
        if task_id not in task_scheduler.tasks:
            raise HTTPException(status_code=404, detail=f"任務 {task_id} 不存在")
        
        task = task_scheduler.tasks[task_id]
        task_dict = task.to_dict()
        
        # 獲取該任務的執行歷史
        execution_history = task_scheduler.get_execution_history(task_id, limit=10)
        
        return {
            "task": task_dict,
            "execution_history": execution_history,
            "history_count": len(execution_history)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取任務詳情失敗: {str(e)}")


@router.post("/tasks/{task_id}/control", summary="控制任務執行")
async def control_task(
    task_id: str, 
    request: TaskControlRequest,
    current_user = Depends(get_current_active_user)
):
    """控制任務的執行狀態"""
    try:
        if task_id not in task_scheduler.tasks:
            raise HTTPException(status_code=404, detail=f"任務 {task_id} 不存在")
        
        task = task_scheduler.tasks[task_id]
        
        if request.action == "enable":
            await task_scheduler.enable_task(task_id)
            return {"message": f"任務 '{task.name}' 已啟用", "status": "enabled"}
            
        elif request.action == "disable":
            await task_scheduler.disable_task(task_id)
            return {"message": f"任務 '{task.name}' 已停用", "status": "disabled"}
            
        elif request.action == "run_now":
            result = await task_scheduler.run_task_now(task_id)
            return {
                "message": f"任務 '{task.name}' 已執行",
                "execution_result": result.to_dict()
            }
            
        elif request.action == "reset_failures":
            await task_scheduler.reset_task_failures(task_id)
            return {"message": f"任務 '{task.name}' 失敗計數已重置"}
            
        else:
            raise HTTPException(status_code=400, detail=f"不支援的操作: {request.action}")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"控制任務失敗: {str(e)}")


@router.put("/tasks/{task_id}/retry-config", summary="更新任務重試配置")
async def update_task_retry_config(
    task_id: str,
    config: TaskRetryConfigRequest,
    current_user = Depends(get_current_active_user)
):
    """更新任務的重試配置"""
    try:
        if task_id not in task_scheduler.tasks:
            raise HTTPException(status_code=404, detail=f"任務 {task_id} 不存在")
        
        await task_scheduler.update_task_retry_config(
            task_id=task_id,
            max_retries=config.max_retries,
            retry_delay=config.retry_delay,
            auto_disable_threshold=config.auto_disable_threshold
        )
        
        updated_task = task_scheduler.tasks[task_id]
        
        return {
            "message": f"任務 '{updated_task.name}' 重試配置已更新",
            "updated_config": {
                "max_retries": updated_task.max_retries,
                "retry_delay": updated_task.retry_delay,
                "auto_disable_threshold": updated_task.auto_disable_threshold
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新重試配置失敗: {str(e)}")


@router.get("/execution-history", summary="取得執行歷史")
async def get_execution_history(
    task_id: Optional[str] = Query(None, description="特定任務ID"),
    limit: int = Query(50, ge=1, le=1000, description="返回記錄數量限制"),
    status_filter: Optional[str] = Query(None, description="按狀態過濾: completed, failed, running")
):
    """取得任務執行歷史記錄"""
    try:
        history = task_scheduler.get_execution_history(task_id, limit)
        
        # 按狀態過濾
        if status_filter:
            history = [h for h in history if h["status"] == status_filter]
        
        return {
            "execution_history": history,
            "total_count": len(history),
            "filters_applied": {
                "task_id": task_id,
                "status_filter": status_filter,
                "limit": limit
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取執行歷史失敗: {str(e)}")


@router.get("/failed-tasks", summary="取得失敗任務清單")
async def get_failed_tasks():
    """取得有失敗記錄的任務清單"""
    try:
        failed_tasks = task_scheduler.get_failed_tasks()
        
        return {
            "failed_tasks": failed_tasks,
            "total_failed": len(failed_tasks),
            "critical_tasks": [
                task for task in failed_tasks 
                if task["consecutive_failures"] >= task["auto_disable_threshold"]
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取失敗任務失敗: {str(e)}")


@router.get("/health", summary="任務健康檢查")
async def get_task_health():
    """取得任務調度器健康狀況"""
    try:
        health_summary = task_scheduler.get_task_health_summary()
        failed_tasks = task_scheduler.get_failed_tasks()
        
        # 健康狀況評估
        health_status = "healthy"
        if health_summary["critical_tasks"] > 0:
            health_status = "critical"
        elif health_summary["failed_tasks"] > 0:
            health_status = "warning"
        elif not health_summary["scheduler_running"]:
            health_status = "stopped"
        
        return {
            "health_status": health_status,
            "summary": health_summary,
            "failed_tasks": failed_tasks,
            "recommendations": _generate_health_recommendations(health_summary, failed_tasks)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"健康檢查失敗: {str(e)}")


def _generate_health_recommendations(
    health_summary: Dict[str, Any], 
    failed_tasks: List[Dict[str, Any]]
) -> List[str]:
    """生成健康狀況建議"""
    recommendations = []
    
    if not health_summary["scheduler_running"]:
        recommendations.append("任務調度器未運行，請檢查系統狀態")
    
    if health_summary["success_rate"] < 90:
        recommendations.append(f"任務成功率偏低 ({health_summary['success_rate']}%)，建議檢查失敗原因")
    
    if health_summary["critical_tasks"] > 0:
        recommendations.append(f"有 {health_summary['critical_tasks']} 個任務處於危險狀態，建議立即檢查")
    
    if health_summary["disabled_tasks"] > 0:
        recommendations.append(f"有 {health_summary['disabled_tasks']} 個任務已停用，檢查是否需要重新啟用")
    
    # 檢查連續失敗的任務
    high_failure_tasks = [t for t in failed_tasks if t["consecutive_failures"] >= 3]
    if high_failure_tasks:
        task_names = [t["name"] for t in high_failure_tasks]
        recommendations.append(f"以下任務連續失敗超過3次: {', '.join(task_names)}")
    
    if not recommendations:
        recommendations.append("所有任務運行正常")
    
    return recommendations


@router.get("/coordinator/status", summary="取得任務協調器狀態")
async def get_coordinator_status():
    """取得任務協調器運行狀態"""
    try:
        coordination_status = get_coordination_status()
        resource_usage = task_coordinator.get_resource_usage()
        
        return {
            "coordinator_status": coordination_status,
            "resource_usage": resource_usage,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取協調器狀態失敗: {str(e)}")


@router.get("/coordinator/dependencies", summary="取得任務依賴關係")
async def get_task_dependencies():
    """取得任務間的依賴關係"""
    try:
        dependencies = {}
        for task_id, dependency in task_coordinator.task_dependencies.items():
            dependencies[task_id] = {
                "depends_on": list(dependency.depends_on),
                "conflicts_with": list(dependency.conflicts_with),
                "required_resources": [res.value for res in dependency.required_resources],
                "priority": dependency.priority
            }
        
        return {
            "task_dependencies": dependencies,
            "total_dependencies": len(dependencies)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取任務依賴關係失敗: {str(e)}")


@router.get("/system-overview", summary="系統總覽")
async def get_system_overview():
    """取得整個任務系統的總覽"""
    try:
        # 任務調度器狀態
        scheduler_status = get_scheduler_status()
        health_summary = task_scheduler.get_task_health_summary()
        
        # 任務協調器狀態
        coordination_status = get_coordination_status()
        
        # 失敗任務
        failed_tasks = task_scheduler.get_failed_tasks()
        
        # 系統整體健康評估
        overall_health = "healthy"
        if coordination_status["mode"] == "emergency":
            overall_health = "critical"
        elif coordination_status["mode"] == "high_load" or health_summary["failed_tasks"] > 0:
            overall_health = "warning"
        elif not health_summary["scheduler_running"] or not coordination_status["is_running"]:
            overall_health = "degraded"
        
        return {
            "overall_health": overall_health,
            "scheduler": {
                "status": scheduler_status,
                "health_summary": health_summary
            },
            "coordinator": coordination_status,
            "failed_tasks": failed_tasks,
            "recommendations": _generate_enhanced_health_recommendations(health_summary, failed_tasks, coordination_status),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取系統總覽失敗: {str(e)}")


def _generate_enhanced_health_recommendations(
    health_summary: Dict[str, Any], 
    failed_tasks: List[Dict[str, Any]],
    coordination_status: Dict[str, Any]
) -> List[str]:
    """生成增強的健康狀況建議"""
    recommendations = []
    
    if not health_summary["scheduler_running"]:
        recommendations.append("任務調度器未運行，請檢查系統狀態")
    
    if not coordination_status["is_running"]:
        recommendations.append("任務協調器未運行，系統可能無法有效協調任務執行")
    
    if coordination_status["mode"] == "emergency":
        recommendations.append("系統處於緊急模式，僅執行核心監控任務，請檢查系統負載和失敗任務")
    elif coordination_status["mode"] == "high_load":
        recommendations.append("系統處於高負載模式，任務執行頻率已降低以減輕負載")
    
    if health_summary["success_rate"] < 90:
        recommendations.append(f"任務成功率偏低 ({health_summary['success_rate']}%)，建議檢查失敗原因")
    
    if health_summary["critical_tasks"] > 0:
        recommendations.append(f"有 {health_summary['critical_tasks']} 個任務處於危險狀態，建議立即檢查")
    
    if health_summary["disabled_tasks"] > 0:
        recommendations.append(f"有 {health_summary['disabled_tasks']} 個任務已停用，檢查是否需要重新啟用")
    
    # 檢查連續失敗的任務
    high_failure_tasks = [t for t in failed_tasks if t["consecutive_failures"] >= 3]
    if high_failure_tasks:
        task_names = [t["name"] for t in high_failure_tasks]
        recommendations.append(f"以下任務連續失敗超過3次: {', '.join(task_names)}")
    
    # 協調器特定建議
    conflicts_resolved = coordination_status["stats"]["resource_conflicts_resolved"]
    if conflicts_resolved > 10:
        recommendations.append(f"協調器已解決 {conflicts_resolved} 個資源衝突，系統運行效率良好")
    
    if not recommendations:
        recommendations.append("所有任務運行正常，系統健康狀況良好")
    
    return recommendations