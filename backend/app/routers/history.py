"""
历史记录相关 API 路由
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from ..services.storage import storage_service
from ..schemas.schemas import (
    MonitorLogResponse,
    MonitorLogListResponse,
    MonitorLogDetailResponse,
    ChangeDetailResponse,
    StatisticsResponse,
    TrendDataPoint
)

router = APIRouter()


@router.get("", response_model=MonitorLogListResponse)
async def get_history(
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    """获取监控历史记录"""
    offset = (page - 1) * page_size
    logs, total = storage_service.get_monitor_logs(
        start_date=start_date,
        end_date=end_date,
        offset=offset,
        limit=page_size
    )

    return MonitorLogListResponse(
        items=[MonitorLogResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/statistics", response_model=StatisticsResponse)
async def get_statistics(
    days: int = Query(30, ge=1, le=365, description="统计天数")
):
    """获取统计数据（趋势图）"""
    stats = storage_service.get_statistics(days=days)

    return StatisticsResponse(
        current_active=stats["current_active"],
        total_tracked=stats["total_tracked"],
        trend_data=[TrendDataPoint(**d) for d in stats["trend_data"]],
        days=stats["days"]
    )


@router.get("/recent")
async def get_recent_changes(
    limit: int = Query(10, ge=1, le=50, description="返回数量")
):
    """获取最近的变化记录"""
    logs, _ = storage_service.get_monitor_logs(limit=limit)

    recent_changes = []
    for log in logs:
        if log.added_count > 0 or log.removed_count > 0:
            detail = storage_service.get_monitor_log_detail(log.id)
            if detail:
                recent_changes.append({
                    "id": log.id,
                    "check_time": log.check_time.isoformat(),
                    "added_count": log.added_count,
                    "removed_count": log.removed_count,
                    "total_count": log.total_count
                })

    return {"changes": recent_changes}


@router.get("/{log_id}", response_model=MonitorLogDetailResponse)
async def get_history_detail(log_id: int):
    """获取监控记录详情（含变化详情）"""
    detail = storage_service.get_monitor_log_detail(log_id)

    if not detail:
        raise HTTPException(status_code=404, detail="记录不存在")

    log = detail["log"]
    added = detail["added"]
    removed = detail["removed"]

    return MonitorLogDetailResponse(
        id=log.id,
        check_time=log.check_time,
        total_count=log.total_count,
        previous_count=log.previous_count,
        added_count=log.added_count,
        removed_count=log.removed_count,
        detection_method=log.detection_method,
        status=log.status,
        error_message=log.error_message,
        duration_seconds=log.duration_seconds,
        created_at=log.created_at,
        added_products=[ChangeDetailResponse.model_validate(c) for c in added],
        removed_products=[ChangeDetailResponse.model_validate(c) for c in removed]
    )
