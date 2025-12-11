"""
上线监控 API 路由
监控即将上线的商品（Daytona Park / Rakuten 等日本网站）
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from loguru import logger
from datetime import datetime

from ..database import get_sync_db
from ..auth import get_current_user, AuthenticatedUser
from ..services.release_monitor import (
    release_monitor_service,
    parse_release_url,
)
from ..models.models import ReleaseMonitorProduct

router = APIRouter()


# ==================== 请求/响应模型 ====================

class ParseReleaseRequest(BaseModel):
    """解析请求"""
    url: str


class ParseReleaseResponse(BaseModel):
    """解析响应"""
    success: bool
    website_type: Optional[str] = None
    website_name: Optional[str] = None
    product_id: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None


class AddReleaseProductRequest(BaseModel):
    """添加上线监控商品请求"""
    url: str
    name: Optional[str] = None


class ReleaseProductResponse(BaseModel):
    """商品响应"""
    id: int
    url: str
    name: Optional[str]
    website_type: str
    product_id: Optional[str]
    status: str
    scheduled_release_time: Optional[str]
    last_check_time: Optional[str]
    notification_sent: bool
    is_active: bool
    created_at: str

    class Config:
        from_attributes = True


class ReleaseStatusResponse(BaseModel):
    """监控状态响应"""
    total: int
    active: int
    coming_soon: int
    available: int
    unavailable: int
    error: int
    notified: int
    products: List[ReleaseProductResponse]


class MessageResponse(BaseModel):
    """通用消息响应"""
    success: bool
    message: str


class CheckResultResponse(BaseModel):
    """检查结果响应"""
    total: int
    checked: int
    available: int
    coming_soon: int
    unavailable: int
    errors: int
    notifications_sent: int


class SupportedWebsite(BaseModel):
    """支持的网站"""
    type: str
    name: str
    domains: List[str]


# ==================== API 路由 ====================

@router.get("/websites", response_model=List[SupportedWebsite])
def get_supported_websites(
    _: AuthenticatedUser = Depends(get_current_user)
):
    """获取支持的网站列表"""
    from ..services.release_monitor.url_parser import get_supported_release_websites

    websites = get_supported_release_websites()
    return [SupportedWebsite(**w) for w in websites]


@router.post("/parse", response_model=ParseReleaseResponse)
def parse_url(
    request: ParseReleaseRequest,
    _: AuthenticatedUser = Depends(get_current_user)
):
    """解析商品URL"""
    try:
        result = parse_release_url(request.url)
        return ParseReleaseResponse(**result.to_dict())
    except Exception as e:
        logger.error(f"解析URL失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=ReleaseStatusResponse)
def get_release_status(
    db: Session = Depends(get_sync_db),
    _: AuthenticatedUser = Depends(get_current_user)
):
    """获取上线监控状态"""
    try:
        summary = release_monitor_service.get_status_summary(db)
        products = release_monitor_service.get_all_products(db, active_only=False)

        product_responses = []
        for p in products:
            product_responses.append(ReleaseProductResponse(
                id=p.id,
                url=p.url,
                name=p.name,
                website_type=p.website_type,
                product_id=p.product_id,
                status=p.status,
                scheduled_release_time=p.scheduled_release_time,
                last_check_time=p.last_check_time.isoformat() if p.last_check_time else None,
                notification_sent=p.notification_sent,
                is_active=p.is_active,
                created_at=p.created_at.isoformat() if p.created_at else None,
            ))

        return ReleaseStatusResponse(
            total=summary['total'],
            active=summary['active'],
            coming_soon=summary['coming_soon'],
            available=summary['available'],
            unavailable=summary['unavailable'],
            error=summary['error'],
            notified=summary['notified'],
            products=product_responses,
        )
    except Exception as e:
        logger.error(f"获取上线监控状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/products", response_model=ReleaseProductResponse)
def add_release_product(
    request: AddReleaseProductRequest,
    db: Session = Depends(get_sync_db),
    _: AuthenticatedUser = Depends(get_current_user)
):
    """添加上线监控商品"""
    try:
        product = release_monitor_service.add_product(
            db=db,
            url=request.url,
            name=request.name,
        )

        return ReleaseProductResponse(
            id=product.id,
            url=product.url,
            name=product.name,
            website_type=product.website_type,
            product_id=product.product_id,
            status=product.status,
            scheduled_release_time=product.scheduled_release_time,
            last_check_time=product.last_check_time.isoformat() if product.last_check_time else None,
            notification_sent=product.notification_sent,
            is_active=product.is_active,
            created_at=product.created_at.isoformat() if product.created_at else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"添加上线监控商品失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/products/{product_id}", response_model=MessageResponse)
def remove_release_product(
    product_id: int,
    db: Session = Depends(get_sync_db),
    _: AuthenticatedUser = Depends(get_current_user)
):
    """移除上线监控商品"""
    try:
        success = release_monitor_service.remove_product(db, product_id)
        if not success:
            raise HTTPException(status_code=404, detail="商品不存在")

        return MessageResponse(success=True, message="已移除监控商品")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"移除上线监控商品失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/products", response_model=MessageResponse)
def remove_release_product_by_url(
    url: str,
    db: Session = Depends(get_sync_db),
    _: AuthenticatedUser = Depends(get_current_user)
):
    """通过URL移除上线监控商品"""
    try:
        success = release_monitor_service.remove_product_by_url(db, url)
        if not success:
            raise HTTPException(status_code=404, detail="商品不存在")

        return MessageResponse(success=True, message="已移除监控商品")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"移除上线监控商品失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check", response_model=CheckResultResponse)
def trigger_release_check(
    db: Session = Depends(get_sync_db),
    _: AuthenticatedUser = Depends(get_current_user)
):
    """手动触发一次上线检测"""
    try:
        result = release_monitor_service.check_all_products(db)
        return CheckResultResponse(**result)
    except Exception as e:
        logger.error(f"上线检测失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/products/{product_id}/check", response_model=Dict[str, Any])
def check_single_product(
    product_id: int,
    db: Session = Depends(get_sync_db),
    _: AuthenticatedUser = Depends(get_current_user)
):
    """检测单个商品状态"""
    try:
        product = release_monitor_service.get_product(db, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="商品不存在")

        # check_product 返回 (DetectionResult, notification_sent)
        result, notification_sent = release_monitor_service.check_product(db, product)
        response = result.to_dict()
        response['notification_sent'] = notification_sent
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"检测商品失败: {e}")
        raise HTTPException(status_code=500, detail="检测失败，请稍后重试")


@router.patch("/products/{product_id}/toggle", response_model=MessageResponse)
def toggle_product_active(
    product_id: int,
    is_active: bool,
    db: Session = Depends(get_sync_db),
    _: AuthenticatedUser = Depends(get_current_user)
):
    """切换商品监控状态"""
    try:
        success = release_monitor_service.toggle_product_active(db, product_id, is_active)
        if not success:
            raise HTTPException(status_code=404, detail="商品不存在")

        status_text = "启用" if is_active else "停用"
        return MessageResponse(success=True, message=f"已{status_text}监控")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"切换商品监控状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
