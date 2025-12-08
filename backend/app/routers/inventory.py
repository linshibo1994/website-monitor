"""
库存监控相关 API 路由
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from ..services.inventory_monitor import inventory_monitor_service
from ..services.url_parser import parse_product_input, get_supported_sites, build_product_url
from ..services.inventory_scraper import inventory_scraper
from ..services.scheels_scraper import scheels_scraper

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
    """添加监控商品请求（支持智能解析）"""
    # 智能模式：只需要提供 input，系统自动解析
    input: Optional[str] = None
    # 显式模式：提供站点、Key和分类
    site_id: Optional[str] = None
    key: Optional[str] = None
    category: Optional[str] = None
    # 传统模式：直接提供URL
    url: Optional[str] = None
    # 通用字段
    name: str = ""
    target_sizes: List[str] = []
    target_colors: List[str] = []


class ParseRequest(BaseModel):
    """解析请求"""
    input: str


class ParseResponse(BaseModel):
    """解析响应"""
    success: bool
    site_id: Optional[str] = None
    site_name: Optional[str] = None
    key: Optional[str] = None
    category: Optional[str] = None
    url: Optional[str] = None
    input_type: Optional[str] = None
    error: Optional[str] = None
    categories: Optional[List[Dict[str, str]]] = None


class SiteInfo(BaseModel):
    """站点信息"""
    site_id: str
    name: str
    domain: str
    url_templates: Dict[str, str]
    default_category: str
    categories: List[Dict[str, str]]
    key_pattern: str
    key_example: str


class SitesResponse(BaseModel):
    """站点列表响应"""
    sites: List[SiteInfo]


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


class ColorOption(BaseModel):
    """颜色选项"""
    value: str  # 颜色ID或值
    label: str  # 颜色名称


class ColorsResponse(BaseModel):
    """颜色列表响应"""
    success: bool
    colors: List[ColorOption]
    message: str = ""


# ==================== 新增站点和解析 API ====================

@router.get("/sites", response_model=SitesResponse)
async def get_sites():
    """获取支持的站点列表"""
    try:
        sites = get_supported_sites()
        return SitesResponse(sites=[SiteInfo(**s) for s in sites])
    except Exception as e:
        logger.error(f"获取站点列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/parse", response_model=ParseResponse)
async def parse_input(request: ParseRequest):
    """智能解析用户输入"""
    try:
        result = parse_product_input(request.input)
        return ParseResponse(**result.to_dict())
    except Exception as e:
        logger.error(f"解析输入失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/colors", response_model=ColorsResponse)
async def get_colors(url: str):
    """获取商品可用颜色列表"""
    if not url:
        raise HTTPException(status_code=400, detail="请提供商品URL")

    try:
        normalized_url = url.lower()

        if 'scheels.com' in normalized_url:
            colors = await scheels_scraper.get_available_colors(url)
        elif 'arcteryx.com' in normalized_url:
            colors = await inventory_scraper.get_available_colors(url)
        else:
            raise HTTPException(status_code=400, detail="不支持的URL，当前仅支持 Arc'teryx 与 Scheels")

        color_options = [
            ColorOption(value=str(c.get('value', '') or '').strip(), label=(c.get('label', '') or '').strip())
            for c in colors if isinstance(c, dict) and (c.get('value') or c.get('label'))
        ]

        if not color_options:
            return ColorsResponse(success=False, colors=[], message="未获取到颜色信息")

        return ColorsResponse(success=True, colors=color_options, message="")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取颜色列表失败: {e}")
        raise HTTPException(status_code=500, detail="获取颜色失败，请稍后重试")


# ==================== 原有 API ====================


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
    """
    添加监控商品（支持三种模式）

    1. 智能模式：提供 input，系统自动解析
    2. 显式模式：提供 site_id + key + category
    3. 传统模式：直接提供 url
    """
    try:
        url = None
        name = request.name

        # 模式1: 智能解析模式
        if request.input:
            result = parse_product_input(request.input)
            if not result.success:
                raise HTTPException(status_code=400, detail=result.error)

            # 如果用户指定了分类，使用用户指定的
            if request.category:
                url = build_product_url(result.site_id, result.key, request.category)
            else:
                url = result.url

        # 模式2: 显式模式
        elif request.site_id and request.key:
            url = build_product_url(request.site_id, request.key, request.category)
            if not url:
                raise HTTPException(status_code=400, detail=f"无法构建URL: site={request.site_id}, key={request.key}")

        # 模式3: 传统模式
        elif request.url:
            url = request.url

        else:
            raise HTTPException(status_code=400, detail="请提供 input、url 或 site_id+key")

        # 添加商品
        inventory_monitor_service.add_product(
            url=url,
            name=name,
            target_sizes=request.target_sizes,
            target_colors=request.target_colors
        )

        # 立即抓取一次库存信息，确保前端能显示名称与尺码
        initial_inventory = await inventory_monitor_service.refresh_product_inventory(url)
        message_suffix = ""
        if not initial_inventory:
            message_suffix = "（首次抓取失败，请稍后手动执行一次库存检查）"

        return MessageResponse(
            success=True,
            message=f"已添加监控商品: {url}{message_suffix}"
        )
    except HTTPException:
        raise
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
