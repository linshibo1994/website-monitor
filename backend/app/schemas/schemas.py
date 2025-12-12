"""
Pydantic 数据模型（请求/响应模式）
"""
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


# ==================== 商品相关 ====================

class ProductBase(BaseModel):
    """商品基础模型"""
    product_id: str
    name: str
    price: Optional[float] = None
    original_price: Optional[float] = None
    is_on_sale: bool = False
    url: Optional[str] = None


class ProductResponse(ProductBase):
    """商品响应模型"""
    id: int
    status: str
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    removed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    """商品列表响应"""
    items: List[ProductResponse]
    total: int
    page: int
    page_size: int


# ==================== 监控记录相关 ====================

class ChangeDetailResponse(BaseModel):
    """变化详情响应"""
    id: int
    product_id: str
    change_type: str
    product_name: Optional[str] = None
    product_price: Optional[float] = None
    product_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MonitorLogBase(BaseModel):
    """监控记录基础模型"""
    check_time: datetime
    total_count: int
    previous_count: Optional[int] = None
    added_count: int = 0
    removed_count: int = 0
    detection_method: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None


class MonitorLogResponse(MonitorLogBase):
    """监控记录响应"""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class MonitorLogDetailResponse(MonitorLogResponse):
    """监控记录详情响应（含变化详情）"""
    added_products: List[ChangeDetailResponse] = []
    removed_products: List[ChangeDetailResponse] = []


class MonitorLogListResponse(BaseModel):
    """监控记录列表响应"""
    items: List[MonitorLogResponse]
    total: int
    page: int
    page_size: int


# ==================== 统计相关 ====================

class TrendDataPoint(BaseModel):
    """趋势数据点"""
    time: str
    count: int
    added: int
    removed: int


class StatisticsResponse(BaseModel):
    """统计数据响应"""
    current_active: int
    total_tracked: int
    trend_data: List[TrendDataPoint]
    days: int


# ==================== 状态相关 ====================

class MonitorStatusResponse(BaseModel):
    """监控状态响应"""
    is_running: bool
    last_check_time: Optional[str] = None
    interval_minutes: int
    last_total_count: int
    last_status: Optional[str] = None


class TriggerResponse(BaseModel):
    """触发检测响应"""
    success: bool
    total_count: Optional[int] = None
    previous_count: Optional[int] = None
    added_count: Optional[int] = None
    removed_count: Optional[int] = None
    duration: Optional[float] = None
    method: Optional[str] = None
    error: Optional[str] = None


# ==================== 配置相关 ====================

class MonitorConfigSchema(BaseModel):
    """监控配置模式"""
    url: str = Field(description="监控URL")
    interval_minutes: int = Field(ge=1, le=1440, description="检测间隔(分钟)")
    timeout_seconds: int = Field(ge=10, le=300, description="超时时间(秒)")
    retry_times: int = Field(ge=0, le=10, description="重试次数")
    headless: bool = Field(description="是否无头模式")


class EmailConfigSchema(BaseModel):
    """邮件配置模式"""
    enabled: bool = Field(description="是否启用")
    smtp_server: str = Field(description="SMTP服务器")
    smtp_port: int = Field(ge=1, le=65535, description="SMTP端口")
    sender: str = Field(description="发件人")
    password: str = Field(description="授权码")
    receiver: str = Field(description="收件人")


class WeChatConfigSchema(BaseModel):
    """微信 ServerChan 配置模式"""
    enabled: bool = Field(default=False, description="是否启用")
    sendkey: str = Field(default="", description="ServerChan SendKey")


class QQConfigSchema(BaseModel):
    """QQ Qmsg 酱配置模式"""
    enabled: bool = Field(default=False, description="是否启用")
    key: str = Field(default="", description="Qmsg Key")
    qq: str = Field(default="", description="接收 QQ 号码")


class NotificationConfigSchema(BaseModel):
    """通知配置模式"""
    notify_on_added: bool = Field(description="新增时通知")
    notify_on_removed: bool = Field(description="下架时通知")
    notify_on_error: bool = Field(description="异常时通知")


class SettingsResponse(BaseModel):
    """设置响应"""
    monitor: MonitorConfigSchema
    email: EmailConfigSchema
    wechat: WeChatConfigSchema
    qq: QQConfigSchema
    notification: NotificationConfigSchema


class SettingsUpdateRequest(BaseModel):
    """设置更新请求"""
    monitor: Optional[MonitorConfigSchema] = None
    email: Optional[EmailConfigSchema] = None
    wechat: Optional[WeChatConfigSchema] = None
    qq: Optional[QQConfigSchema] = None
    notification: Optional[NotificationConfigSchema] = None


# ==================== 通用响应 ====================

class MessageResponse(BaseModel):
    """通用消息响应"""
    success: bool
    message: str


class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = False
    error: str
    detail: Optional[str] = None


# ==================== 认证相关 ====================


class LoginRequest(BaseModel):
    """管理员登录请求"""
    username: str = Field(description="用户名")
    password: str = Field(description="密码")


class TokenLoginRequest(BaseModel):
    """Token 登录请求"""
    token: str = Field(description="API Token")


class TokenResponse(BaseModel):
    """统一的JWT响应"""
    access_token: str = Field(description="JWT令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    user_type: str = Field(description="用户类型")
    expires_in: int = Field(description="有效期(秒)")


class UserInfoResponse(BaseModel):
    """当前用户信息"""
    subject: str
    type: str
    token_id: Optional[int] = None
    token_name: Optional[str] = None
    is_admin: bool = False


class TokenCreateRequest(BaseModel):
    """创建Token请求"""
    name: str = Field(..., max_length=100, description="备注名称")
    expires_in: Literal["1d", "7d", "30d", "90d", "forever"] = Field(default="30d", description="有效期")


class TokenUpdateRequest(BaseModel):
    """更新Token请求"""
    name: str = Field(..., max_length=100, description="备注名称")


class ApiTokenSchema(BaseModel):
    """Token 信息"""
    id: int
    name: str
    expires_at: Optional[datetime] = None
    created_at: datetime
    last_used_at: Optional[datetime] = None
    is_revoked: bool

    class Config:
        from_attributes = True


class TokenCreateResponse(BaseModel):
    """创建Token响应"""
    token: str
    token_info: ApiTokenSchema
