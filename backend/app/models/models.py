"""
数据库模型定义
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship, declarative_base
import enum

Base = declarative_base()


class ProductStatus(str, enum.Enum):
    """商品状态枚举"""
    ACTIVE = "active"      # 在售
    REMOVED = "removed"    # 已下架


class ReleaseMonitorStatus(str, enum.Enum):
    """上线监控状态枚举"""
    COMING_SOON = "coming_soon"    # 即将上线
    AVAILABLE = "available"        # 已上线可购买
    UNAVAILABLE = "unavailable"    # 不可用/下架
    ERROR = "error"                # 检测错误


class WebsiteType(str, enum.Enum):
    """支持的网站类型枚举"""
    DAYTONA_PARK = "daytona_park"  # Daytona Park
    RAKUTEN = "rakuten"            # 乐天


class ChangeType(str, enum.Enum):
    """变化类型枚举"""
    ADDED = "added"        # 新增
    REMOVED = "removed"    # 下架


class MonitorStatus(str, enum.Enum):
    """监控状态枚举"""
    SUCCESS = "success"    # 成功
    FAILED = "failed"      # 失败


class Product(Base):
    """商品表"""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 商品ID（从URL提取的唯一标识）
    product_id = Column(String(50), unique=True, nullable=False, index=True)
    # 商品名称
    name = Column(String(255), nullable=False)
    # 当前价格
    price = Column(Float, nullable=True)
    # 原价（如有折扣）
    original_price = Column(Float, nullable=True)
    # 是否促销
    is_on_sale = Column(Boolean, default=False)
    # 商品链接
    url = Column(String(500), nullable=True)
    # 商品状态
    status = Column(String(20), default=ProductStatus.ACTIVE.value)
    # 首次发现时间
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    # 最后发现时间
    last_seen_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # 下架时间
    removed_at = Column(DateTime, nullable=True)
    # 创建时间
    created_at = Column(DateTime, default=datetime.utcnow)
    # 更新时间
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Product(id={self.id}, product_id={self.product_id}, name={self.name})>"


class MonitorLog(Base):
    """监控记录表"""
    __tablename__ = "monitor_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 检测时间
    check_time = Column(DateTime, default=datetime.utcnow, index=True)
    # 商品总数
    total_count = Column(Integer, nullable=False)
    # 上次数量
    previous_count = Column(Integer, nullable=True)
    # 新增数量
    added_count = Column(Integer, default=0)
    # 下架数量
    removed_count = Column(Integer, default=0)
    # 检测方法（primary/fallback/card_count）
    detection_method = Column(String(50), nullable=True)
    # 状态
    status = Column(String(20), default=MonitorStatus.SUCCESS.value)
    # 错误信息
    error_message = Column(Text, nullable=True)
    # 检测耗时（秒）
    duration_seconds = Column(Float, nullable=True)
    # 创建时间
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关联变化详情
    changes = relationship("ChangeDetail", back_populates="monitor_log", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<MonitorLog(id={self.id}, check_time={self.check_time}, total_count={self.total_count})>"


class ChangeDetail(Base):
    """变化详情表"""
    __tablename__ = "change_details"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 关联监控记录ID
    monitor_log_id = Column(Integer, ForeignKey("monitor_logs.id"), nullable=False, index=True)
    # 商品ID
    product_id = Column(String(50), nullable=False)
    # 变化类型
    change_type = Column(String(20), nullable=False)
    # 商品名称（快照）
    product_name = Column(String(255), nullable=True)
    # 商品价格（快照）
    product_price = Column(Float, nullable=True)
    # 商品链接（快照）
    product_url = Column(String(500), nullable=True)
    # 创建时间
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关联监控记录
    monitor_log = relationship("MonitorLog", back_populates="changes")

    def __repr__(self):
        return f"<ChangeDetail(id={self.id}, product_id={self.product_id}, change_type={self.change_type})>"


class SystemConfig(Base):
    """系统配置表（存储运行时配置）"""
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 配置键
    key = Column(String(100), unique=True, nullable=False)
    # 配置值
    value = Column(Text, nullable=True)
    # 描述
    description = Column(String(255), nullable=True)
    # 更新时间
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SystemConfig(key={self.key}, value={self.value})>"


class ApiToken(Base):
    """API Token 表"""
    __tablename__ = "api_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    is_revoked = Column(Boolean, default=False)

    def is_expired(self) -> bool:
        """判断是否过期"""
        return self.expires_at is not None and self.expires_at < datetime.utcnow()

    def __repr__(self):
        return f"<ApiToken(id={self.id}, name={self.name}, revoked={self.is_revoked})>"


class ReleaseMonitorProduct(Base):
    """上线监控商品表 - 用于监控即将上线的商品"""
    __tablename__ = "release_monitor_products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 商品URL（唯一标识）
    url = Column(String(500), unique=True, nullable=False, index=True)
    # 商品名称（自动提取或手动填写）
    name = Column(String(255), nullable=True)
    # 网站类型
    website_type = Column(String(20), nullable=False, index=True)
    # 商品ID（从URL提取）
    product_id = Column(String(50), nullable=True)
    # 当前状态
    status = Column(String(20), default=ReleaseMonitorStatus.COMING_SOON.value)
    # 预计上线时间（如果能从页面获取）
    scheduled_release_time = Column(String(100), nullable=True)
    # 最后检测时间
    last_check_time = Column(DateTime, nullable=True)
    # 最后检测结果详情（JSON格式存储库存等信息）
    last_check_result = Column(Text, nullable=True)
    # 是否已发送上线通知
    notification_sent = Column(Boolean, default=False)
    # 通知发送时间
    notification_sent_at = Column(DateTime, nullable=True)
    # 是否启用监控
    is_active = Column(Boolean, default=True)
    # 检测失败次数（连续失败计数）
    consecutive_failures = Column(Integer, default=0)
    # 最后错误信息
    last_error = Column(Text, nullable=True)
    # 创建时间
    created_at = Column(DateTime, default=datetime.utcnow)
    # 更新时间
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ReleaseMonitorProduct(id={self.id}, url={self.url}, status={self.status})>"
