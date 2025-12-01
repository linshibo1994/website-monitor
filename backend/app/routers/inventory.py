"""
库存监控相关 API 路由
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from ..services.inventory_monitor import inventory_monitor_service

router = APIRouter()

# 用于追踪正在运行的检测任务
_running_check = False


class VariantInfo(BaseModel):
    """变体库存信息"""
    size: str
    stock_status: str
    is_available: bool
    color_name: str = ""


class ProductInventoryInfo(BaseModel):
    """商品库存信息"""
    url: str
    name: str
    target_sizes: List[str]
    target_colors: List[str] = []
    variants: List[VariantInfo]
    last_check_time: Optional[str] = None
    status: str = "available"  # available / coming_soon / unavailable


class InventoryStatusResponse(BaseModel):
    """库存监控状态响应"""
    is_running: bool
    last_check_time: Optional[str]
    monitored_products: int
    products: List[ProductInventoryInfo]


class AddProductRequest(BaseModel):
    """添加监控商品请求"""
    url: str
    name: str = ""
    target_sizes: List[str] = []
    target_colors: List[str] = []


class MessageResponse(BaseModel):
    """通用消息响应"""
    success: bool
    message: str


class CheckResultResponse(BaseModel):
    """检查结果响应"""
    success: bool
    products_checked: int
    changes_detected: int
    notifications_sent: int
    errors: List[str]


@router.get("/status", response_model=InventoryStatusResponse)
async def get_inventory_status():
    """获取库存监控状态"""
    try:
        status = inventory_monitor_service.get_status()

        # 转换产品列表格式
        products = []
        for p in status.get('products', []):
            # 获取该商品的库存详情
            url = p.get('url', '')
            inventory = inventory_monitor_service.last_inventory.get(url)

            variants = []
            if inventory:
                for v in inventory.variants:
                    variants.append(VariantInfo(
                        size=v.size,
                        stock_status=v.stock_status,
                        is_available=v.is_available(),
                        color_name=v.color_name
                    ))

            products.append(ProductInventoryInfo(
                url=url,
                name=p.get('name', '') or (inventory.name if inventory else '未知商品'),
                target_sizes=p.get('target_sizes', []),
                target_colors=p.get('target_colors', []),
                variants=variants,
                last_check_time=inventory.check_time.isoformat() if inventory else None,
                status=inventory.status if inventory else 'available'
            ))

        return InventoryStatusResponse(
            is_running=status.get('is_running', False),
            last_check_time=status.get('last_check_time'),
            monitored_products=status.get('monitored_products', 0),
            products=products
        )
    except Exception as e:
        logger.error(f"获取库存监控状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check", response_model=CheckResultResponse)
async def trigger_inventory_check():
    """手动触发一次库存检查"""
    global _running_check

    if _running_check:
        raise HTTPException(status_code=409, detail="已有检测任务正在运行")

    try:
        _running_check = True
        result = await inventory_monitor_service.check_all_products()
        return CheckResultResponse(
            success=result.get('success', True),
            products_checked=result.get('products_checked', 0),
            changes_detected=result.get('changes_detected', 0),
            notifications_sent=result.get('notifications_sent', 0),
            errors=result.get('errors', [])
        )
    except Exception as e:
        logger.error(f"库存检查失败: {e}")
        raise HTTPException(status_code=500, detail=f"检测失败: {str(e)}")
    finally:
        _running_check = False


@router.post("/products", response_model=MessageResponse)
async def add_product(request: AddProductRequest):
    """添加监控商品"""
    try:
        inventory_monitor_service.add_product(
            url=request.url,
            name=request.name,
            target_sizes=request.target_sizes,
            target_colors=request.target_colors
        )
        return MessageResponse(
            success=True,
            message=f"已添加监控商品: {request.url}"
        )
    except Exception as e:
        logger.error(f"添加商品失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/products", response_model=MessageResponse)
async def remove_product(url: str):
    """移除监控商品"""
    try:
        inventory_monitor_service.remove_product(url)
        return MessageResponse(
            success=True,
            message=f"已移除监控商品: {url}"
        )
    except Exception as e:
        logger.error(f"移除商品失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start", response_model=MessageResponse)
async def start_inventory_scheduler(interval_minutes: int = 5):
    """启动库存监控调度器"""
    try:
        if inventory_monitor_service.is_running:
            return MessageResponse(success=False, message="调度器已在运行")

        inventory_monitor_service.start_scheduler(interval_minutes)
        return MessageResponse(success=True, message=f"库存监控调度器已启动，间隔: {interval_minutes} 分钟")
    except Exception as e:
        logger.error(f"启动调度器失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop", response_model=MessageResponse)
async def stop_inventory_scheduler():
    """停止库存监控调度器"""
    try:
        if not inventory_monitor_service.is_running:
            return MessageResponse(success=False, message="调度器未在运行")

        inventory_monitor_service.stop_scheduler()
        return MessageResponse(success=True, message="库存监控调度器已停止")
    except Exception as e:
        logger.error(f"停止调度器失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
