"""
API Token 管理路由
"""
import secrets
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import AuthenticatedUser, hash_token, require_admin
from ..database import get_db
from ..models.models import ApiToken
from ..schemas.schemas import ApiTokenSchema, TokenCreateRequest, TokenCreateResponse, TokenUpdateRequest

router = APIRouter()

EXPIRE_MAP = {
    "1d": timedelta(days=1),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "90d": timedelta(days=90),
    "forever": None,
}


def _calc_expire_at(option: str) -> Optional[datetime]:
    """根据选项计算过期时间"""
    delta = EXPIRE_MAP.get(option)
    if delta is None:
        return None
    return datetime.utcnow() + delta


async def _get_token_or_404(token_id: int, db: AsyncSession) -> ApiToken:
    """获取 Token，如果不存在抛出404"""
    token = await db.get(ApiToken, token_id)
    if not token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token不存在")
    return token


@router.get("", response_model=List[ApiTokenSchema])
async def list_tokens(
    _: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Token 列表"""
    result = await db.execute(select(ApiToken).order_by(ApiToken.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=TokenCreateResponse)
async def create_token(
    request: TokenCreateRequest,
    _: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """创建新的 API Token"""
    expires_at = _calc_expire_at(request.expires_in)
    plain_token = secrets.token_urlsafe(32)

    token_obj = ApiToken(
        name=request.name,
        token_hash=hash_token(plain_token),
        expires_at=expires_at,
    )
    db.add(token_obj)
    await db.flush()

    return TokenCreateResponse(token=plain_token, token_info=token_obj)


@router.put("/{token_id}", response_model=ApiTokenSchema)
async def update_token(
    token_id: int,
    request: TokenUpdateRequest,
    _: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """更新 Token 备注"""
    token = await _get_token_or_404(token_id, db)
    token.name = request.name
    db.add(token)
    return token


@router.delete("/{token_id}", response_model=ApiTokenSchema)
async def revoke_token(
    token_id: int,
    _: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """撤销 Token"""
    token = await _get_token_or_404(token_id, db)
    if not token.is_revoked:
        token.is_revoked = True
        db.add(token)
    return token
