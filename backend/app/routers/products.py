"""
商品相关 API 路由
"""
from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from ..services.storage import storage_service
from ..schemas.schemas import ProductResponse, ProductListResponse

router = APIRouter()


@router.get("", response_model=ProductListResponse)
async def get_products(
    status: Optional[str] = Query(None, description="状态筛选: active/removed"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    """获取商品列表"""
    offset = (page - 1) * page_size
    products, total = storage_service.get_products(
        status=status,
        search=search,
        offset=offset,
        limit=page_size
    )

    return ProductListResponse(
        items=[ProductResponse.model_validate(p) for p in products],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str):
    """获取单个商品详情"""
    products, _ = storage_service.get_products(search=product_id, limit=1)

    for p in products:
        if p.product_id == product_id:
            return ProductResponse.model_validate(p)

    raise HTTPException(status_code=404, detail="商品不存在")


@router.get("/stats/summary")
async def get_products_summary():
    """获取商品统计摘要"""
    active_products, active_total = storage_service.get_products(status="active", limit=1)
    removed_products, removed_total = storage_service.get_products(status="removed", limit=1)
    _, total = storage_service.get_products(limit=1)

    return {
        "total": total,
        "active": active_total,
        "removed": removed_total
    }
