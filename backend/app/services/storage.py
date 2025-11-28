"""
数据存储模块
负责商品数据的存储、查询和变化检测
"""
from datetime import datetime
from typing import List, Optional, Tuple, Set, Dict
from sqlalchemy import select, update, and_, desc, func
from sqlalchemy.orm import Session
from loguru import logger

from ..database import get_db_session, init_db
from ..models.models import Product, MonitorLog, ChangeDetail, ProductStatus, ChangeType, MonitorStatus
from .scraper import ProductInfo, ScrapeResult


class StorageService:
    """数据存储服务"""

    def __init__(self):
        # 确保数据库初始化
        init_db()

    def get_last_monitor_log(self) -> Optional[MonitorLog]:
        """获取最近一次监控记录"""
        with get_db_session() as session:
            result = session.execute(
                select(MonitorLog)
                .where(MonitorLog.status == MonitorStatus.SUCCESS.value)
                .order_by(desc(MonitorLog.check_time))
                .limit(1)
            )
            log = result.scalar_one_or_none()
            if log:
                # 分离对象以便在会话外使用
                session.expunge(log)
            return log

    def get_previous_count(self) -> int:
        """获取上次的商品总数"""
        log = self.get_last_monitor_log()
        return log.total_count if log else 0

    def get_active_product_ids(self) -> Set[str]:
        """获取当前活跃商品的ID集合"""
        with get_db_session() as session:
            result = session.execute(
                select(Product.product_id)
                .where(Product.status == ProductStatus.ACTIVE.value)
            )
            return {row[0] for row in result.fetchall()}

    def process_scrape_result(self, result: ScrapeResult) -> Tuple[List[ProductInfo], List[ProductInfo]]:
        """
        处理抓取结果，检测变化
        返回: (新增商品列表, 下架商品列表)
        """
        if not result.success:
            logger.warning("抓取结果失败，跳过处理")
            return [], []

        # 获取当前数据库中活跃的商品ID
        old_product_ids = self.get_active_product_ids()

        # 当前抓取到的商品ID
        new_product_ids = {p.product_id for p in result.products}

        # 计算新增和下架
        added_ids = new_product_ids - old_product_ids
        removed_ids = old_product_ids - new_product_ids

        added_products = [p for p in result.products if p.product_id in added_ids]
        removed_products = []

        # 获取下架商品的信息
        if removed_ids:
            with get_db_session() as session:
                result_query = session.execute(
                    select(Product).where(Product.product_id.in_(removed_ids))
                )
                for product in result_query.scalars():
                    removed_products.append(ProductInfo(
                        product_id=product.product_id,
                        name=product.name,
                        price=product.price,
                        original_price=product.original_price,
                        is_on_sale=product.is_on_sale,
                        url=product.url or ""
                    ))

        logger.info(f"变化检测: 新增={len(added_products)}, 下架={len(removed_products)}")

        return added_products, removed_products

    def save_scrape_result(
        self,
        result: ScrapeResult,
        added_products: List[ProductInfo],
        removed_products: List[ProductInfo]
    ) -> MonitorLog:
        """保存抓取结果到数据库"""
        with get_db_session() as session:
            # 获取上次的数量
            previous_count = self.get_previous_count()

            # 创建监控记录
            monitor_log = MonitorLog(
                check_time=datetime.utcnow(),
                total_count=result.total_count,
                previous_count=previous_count,
                added_count=len(added_products),
                removed_count=len(removed_products),
                detection_method=result.detection_method,
                status=MonitorStatus.SUCCESS.value if result.success else MonitorStatus.FAILED.value,
                error_message=result.error_message,
                duration_seconds=result.duration_seconds
            )
            session.add(monitor_log)
            session.flush()  # 获取ID

            # 保存变化详情
            for product in added_products:
                change = ChangeDetail(
                    monitor_log_id=monitor_log.id,
                    product_id=product.product_id,
                    change_type=ChangeType.ADDED.value,
                    product_name=product.name,
                    product_price=product.price,
                    product_url=product.url
                )
                session.add(change)

            for product in removed_products:
                change = ChangeDetail(
                    monitor_log_id=monitor_log.id,
                    product_id=product.product_id,
                    change_type=ChangeType.REMOVED.value,
                    product_name=product.name,
                    product_price=product.price,
                    product_url=product.url
                )
                session.add(change)

            # 更新商品表
            now = datetime.utcnow()

            # 更新现有商品
            for product_info in result.products:
                existing = session.execute(
                    select(Product).where(Product.product_id == product_info.product_id)
                ).scalar_one_or_none()

                if existing:
                    # 更新现有商品
                    existing.name = product_info.name
                    existing.price = product_info.price
                    existing.original_price = product_info.original_price
                    existing.is_on_sale = product_info.is_on_sale
                    existing.url = product_info.url
                    existing.status = ProductStatus.ACTIVE.value
                    existing.last_seen_at = now
                    existing.removed_at = None
                else:
                    # 新增商品
                    new_product = Product(
                        product_id=product_info.product_id,
                        name=product_info.name,
                        price=product_info.price,
                        original_price=product_info.original_price,
                        is_on_sale=product_info.is_on_sale,
                        url=product_info.url,
                        status=ProductStatus.ACTIVE.value,
                        first_seen_at=now,
                        last_seen_at=now
                    )
                    session.add(new_product)

            # 标记下架商品
            for product_info in removed_products:
                session.execute(
                    update(Product)
                    .where(Product.product_id == product_info.product_id)
                    .values(
                        status=ProductStatus.REMOVED.value,
                        removed_at=now
                    )
                )

            session.commit()
            session.refresh(monitor_log)

            logger.info(f"保存监控记录: ID={monitor_log.id}, 总数={result.total_count}")

            return monitor_log

    def save_failed_result(self, error_message: str, duration: float) -> MonitorLog:
        """保存失败的监控记录"""
        with get_db_session() as session:
            previous_count = self.get_previous_count()

            monitor_log = MonitorLog(
                check_time=datetime.utcnow(),
                total_count=previous_count,  # 使用上次的数量
                previous_count=previous_count,
                added_count=0,
                removed_count=0,
                detection_method="failed",
                status=MonitorStatus.FAILED.value,
                error_message=error_message,
                duration_seconds=duration
            )
            session.add(monitor_log)
            session.commit()
            session.refresh(monitor_log)

            return monitor_log

    def get_products(
        self,
        status: Optional[str] = None,
        search: Optional[str] = None,
        offset: int = 0,
        limit: int = 20
    ) -> Tuple[List[Product], int]:
        """获取商品列表（支持分页和筛选）"""
        with get_db_session() as session:
            query = select(Product)

            if status:
                query = query.where(Product.status == status)

            if search:
                query = query.where(Product.name.ilike(f"%{search}%"))

            # 获取总数
            count_query = select(func.count()).select_from(query.subquery())
            total = session.execute(count_query).scalar()

            # 获取分页数据
            query = query.order_by(desc(Product.last_seen_at))
            query = query.offset(offset).limit(limit)

            result = session.execute(query)
            products = list(result.scalars())

            # 分离对象
            for p in products:
                session.expunge(p)

            return products, total

    def get_monitor_logs(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        offset: int = 0,
        limit: int = 20
    ) -> Tuple[List[MonitorLog], int]:
        """获取监控记录列表"""
        with get_db_session() as session:
            query = select(MonitorLog)

            if start_date:
                query = query.where(MonitorLog.check_time >= start_date)
            if end_date:
                query = query.where(MonitorLog.check_time <= end_date)

            # 获取总数
            count_query = select(func.count()).select_from(query.subquery())
            total = session.execute(count_query).scalar()

            # 获取分页数据
            query = query.order_by(desc(MonitorLog.check_time))
            query = query.offset(offset).limit(limit)

            result = session.execute(query)
            logs = list(result.scalars())

            for log in logs:
                session.expunge(log)

            return logs, total

    def get_monitor_log_detail(self, log_id: int) -> Optional[Dict]:
        """获取监控记录详情（包含变化详情）"""
        with get_db_session() as session:
            log = session.get(MonitorLog, log_id)
            if not log:
                return None

            # 获取变化详情
            changes = session.execute(
                select(ChangeDetail)
                .where(ChangeDetail.monitor_log_id == log_id)
                .order_by(ChangeDetail.change_type)
            ).scalars().all()

            added = [c for c in changes if c.change_type == ChangeType.ADDED.value]
            removed = [c for c in changes if c.change_type == ChangeType.REMOVED.value]

            return {
                "log": log,
                "added": added,
                "removed": removed
            }

    def get_statistics(self, days: int = 30) -> Dict:
        """获取统计数据（用于趋势图）"""
        with get_db_session() as session:
            from datetime import timedelta
            start_date = datetime.utcnow() - timedelta(days=days)

            # 获取时间范围内的监控记录
            result = session.execute(
                select(MonitorLog)
                .where(
                    and_(
                        MonitorLog.check_time >= start_date,
                        MonitorLog.status == MonitorStatus.SUCCESS.value
                    )
                )
                .order_by(MonitorLog.check_time)
            )
            logs = list(result.scalars())

            # 构建趋势数据
            trend_data = []
            for log in logs:
                trend_data.append({
                    "time": log.check_time.isoformat(),
                    "count": log.total_count,
                    "added": log.added_count,
                    "removed": log.removed_count
                })

            # 获取当前统计
            active_count = session.execute(
                select(func.count())
                .where(Product.status == ProductStatus.ACTIVE.value)
            ).scalar()

            total_count = session.execute(
                select(func.count()).select_from(Product)
            ).scalar()

            return {
                "current_active": active_count,
                "total_tracked": total_count,
                "trend_data": trend_data,
                "days": days
            }


# 创建存储服务单例
storage_service = StorageService()
