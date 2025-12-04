"""
认证与授权相关路由
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import (
    AuthenticatedUser,
    create_access_token,
    get_current_user,
    hash_token,
    verify_password,
)
from ..config import get_config
from ..database import get_db
from ..models.models import ApiToken
from ..schemas.schemas import (
    LoginRequest,
    TokenLoginRequest,
    TokenResponse,
    UserInfoResponse,
)

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """管理员账号密码登录"""
    config = get_config()
    auth_config = config.auth

    if request.username != auth_config.admin_username or not verify_password(request.password, auth_config.admin_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    token = create_access_token({"sub": auth_config.admin_username, "type": "admin"})
    expires_in = auth_config.jwt_expire_hours * 3600
    return TokenResponse(access_token=token, user_type="admin", expires_in=expires_in)


@router.post("/login/token", response_model=TokenResponse)
async def login_with_token(request: TokenLoginRequest, db: AsyncSession = Depends(get_db)):
    """API Token 登录"""
    token_hash = hash_token(request.token)
    result = await db.execute(select(ApiToken).where(ApiToken.token_hash == token_hash))
    token_obj = result.scalar_one_or_none()

    if not token_obj or token_obj.is_revoked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效或已撤销")
    if token_obj.is_expired():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 已过期")

    token_obj.last_used_at = datetime.utcnow()
    db.add(token_obj)

    jwt_token = create_access_token({
        "sub": f"token:{token_obj.id}",
        "type": "token",
        "token_id": token_obj.id
    })
    expires_in = get_config().auth.jwt_expire_hours * 3600
    return TokenResponse(access_token=jwt_token, user_type="token", expires_in=expires_in)


@router.get("/me", response_model=UserInfoResponse)
async def get_me(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户信息"""
    token_name = None
    if user.type == "token" and user.token_id is not None:
        result = await db.execute(select(ApiToken).where(ApiToken.id == user.token_id))
        token_obj = result.scalar_one_or_none()
        token_name = token_obj.name if token_obj else None

    return UserInfoResponse(
        subject=user.subject,
        type=user.type,
        token_id=user.token_id,
        token_name=token_name,
        is_admin=user.is_admin
    )
