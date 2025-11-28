"""
监控控制相关 API 路由
"""
import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks

from ..services.monitor import monitor_service
from ..schemas.schemas import MonitorStatusResponse, TriggerResponse, MessageResponse

router = APIRouter()

# 用于追踪正在运行的检测任务
_running_check = False


@router.get("/status", response_model=MonitorStatusResponse)
async def get_monitor_status():
    """获取监控状态"""
    status = monitor_service.get_status()
    return MonitorStatusResponse(**status)


@router.post("/trigger", response_model=TriggerResponse)
async def trigger_check():
    """手动触发一次检测"""
    global _running_check

    if _running_check:
        raise HTTPException(status_code=409, detail="已有检测任务正在运行")

    try:
        _running_check = True
        result = await monitor_service.run_check()
        return TriggerResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检测失败: {str(e)}")
    finally:
        _running_check = False


@router.post("/start", response_model=MessageResponse)
async def start_scheduler():
    """启动定时调度器"""
    try:
        if monitor_service.is_running:
            return MessageResponse(success=False, message="调度器已在运行")

        monitor_service.start_scheduler()
        return MessageResponse(success=True, message="调度器已启动")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动失败: {str(e)}")


@router.post("/stop", response_model=MessageResponse)
async def stop_scheduler():
    """停止定时调度器"""
    try:
        if not monitor_service.is_running:
            return MessageResponse(success=False, message="调度器未在运行")

        monitor_service.stop_scheduler()
        return MessageResponse(success=True, message="调度器已停止")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止失败: {str(e)}")
