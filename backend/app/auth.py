"""
认证与授权工具
"""
from __future__ import annotations

import secrets
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_config
from .database import get_db
from .models.models import ApiToken

# 统一的 Bearer 认证方案
bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthenticatedUser:
    """JWT 解码后的用户信息"""
    subject: str
    type: str
    token_id: Optional[int] = None

    @property
    def is_admin(self) -> bool:
        return self.type == "admin"


def verify_password(plain_password: str, expected_password: str) -> bool:
    """使用恒定时间比较验证密码"""
    return secrets.compare_digest(plain_password or "", expected_password or "")


def hash_token(token: str) -> str:
    """对API Token进行SHA256哈希"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(payload: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT 访问令牌"""
    config = get_config()
    auth_config = getattr(config, "auth", None)
    if not auth_config:
        raise RuntimeError("未配置认证参数")

    to_encode = payload.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=auth_config.jwt_expire_hours))
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, auth_config.jwt_secret, algorithm="HS256")
    return token


async def _validate_api_token(token_id: int, db: AsyncSession) -> ApiToken:
    """校验数据库中的 API Token 状态"""
    result = await db.execute(select(ApiToken).where(ApiToken.id == token_id))
    token_obj = result.scalar_one_or_none()

    if not token_obj:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token不存在或已删除")
    if token_obj.is_revoked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token已被撤销")
    if token_obj.is_expired():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token已过期")

    token_obj.last_used_at = datetime.utcnow()
    db.add(token_obj)
    return token_obj


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db)
) -> AuthenticatedUser:
    """FastAPI 依赖：验证并返回当前用户"""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少认证信息")

    token = credentials.credentials
    config = get_config()
    auth_config = getattr(config, "auth", None)
    if not auth_config:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="未配置认证信息")

    try:
        payload = jwt.decode(token, auth_config.jwt_secret, algorithms=["HS256"])
        subject: str = payload.get("sub")
        token_type: str = payload.get("type")
        token_id: Optional[int] = payload.get("token_id")
    except JWTError as e:
        logger.warning(f"JWT解析失败: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证信息")

    if not subject or not token_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证信息")

    user = AuthenticatedUser(subject=subject, type=token_type, token_id=token_id)

    if token_type == "token":
        if token_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少Token ID")
        await _validate_api_token(token_id, db)

    return user


async def require_admin(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """FastAPI 依赖：要求管理员权限"""
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user
