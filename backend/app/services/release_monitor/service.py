"""
上线监控核心服务
管理商品上线监控的添加、检测、通知等功能
"""
from __future__ import annotations

import html
import json
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

from sqlalchemy.orm import Session
from loguru import logger

from ...models.models import ReleaseMonitorProduct, ReleaseMonitorStatus, WebsiteType
from ...database import get_sync_db
from ...config import get_config
from .detectors import (
    DetectionResult,
    DaytonaParkDetector,
    RakutenDetector,
    detect_website_type,
    get_detector,
)
from .url_parser import parse_release_url, ReleaseParseResult
from ..notifier import EmailNotifier


# 有效状态值集合（用于验证）
VALID_STATUSES = {s.value for s in ReleaseMonitorStatus}
VALID_WEBSITE_TYPES = {t.value for t in WebsiteType}


class ReleaseMonitorService:
    """上线监控服务"""

    def __init__(self):
        self.config = get_config()
        self.notifier = EmailNotifier()

    def parse_url(self, url: str) -> ReleaseParseResult:
        """解析商品URL"""
        return parse_release_url(url)

    def add_product(
        self,
        db: Session,
        url: str,
        name: Optional[str] = None,
    ) -> ReleaseMonitorProduct:
        """
        添加监控商品

        Args:
            db: 数据库会话
            url: 商品URL
            name: 商品名称（可选，不填则自动获取）

        Returns:
            ReleaseMonitorProduct: 创建的监控商品记录

        Raises:
            ValueError: URL无效或已存在
        """
        # 解析URL
        parse_result = parse_release_url(url)
        if not parse_result.success:
            raise ValueError(parse_result.error or "URL解析失败")

        # 验证网站类型
        if parse_result.website_type not in VALID_WEBSITE_TYPES:
            raise ValueError(f"不支持的网站类型: {parse_result.website_type}")

        # 检查是否已存在
        existing = db.query(ReleaseMonitorProduct).filter(
            ReleaseMonitorProduct.url == url
        ).first()

        if existing:
            raise ValueError("该商品已在监控列表中")

        # 立即检测一次获取初始状态
        detector = get_detector(parse_result.website_type)
        initial_result = None
        initial_error = None

        if detector:
            try:
                initial_result = detector.check(url)
                # 如果没有提供名称，使用检测到的名称
                if not name and initial_result.product_name:
                    name = initial_result.product_name
            except Exception as e:
                logger.warning(f"初始检测失败: {e}")
                initial_error = str(e)

        # 确定初始状态
        initial_status = ReleaseMonitorStatus.COMING_SOON.value
        if initial_result:
            # 验证状态值
            if initial_result.status in VALID_STATUSES:
                initial_status = initial_result.status
            else:
                logger.warning(f"无效的状态值: {initial_result.status}，使用默认值")

        # 创建监控记录
        product = ReleaseMonitorProduct(
            url=url,
            name=name or "未知商品",
            website_type=parse_result.website_type,
            product_id=parse_result.product_id,
            status=initial_status,
            scheduled_release_time=initial_result.scheduled_release if initial_result else None,
            last_check_time=datetime.utcnow() if initial_result else None,
            last_check_result=initial_result.to_json() if initial_result else None,
            last_error=initial_error,
            consecutive_failures=1 if initial_error else 0,
        )

        db.add(product)
        db.commit()
        db.refresh(product)

        logger.info(f"添加上线监控商品: {url}, 状态: {product.status}")

        return product

    def remove_product(self, db: Session, product_id: int) -> bool:
        """
        移除监控商品

        Args:
            db: 数据库会话
            product_id: 商品ID

        Returns:
            bool: 是否成功删除
        """
        product = db.query(ReleaseMonitorProduct).filter(
            ReleaseMonitorProduct.id == product_id
        ).first()

        if not product:
            return False

        db.delete(product)
        db.commit()

        logger.info(f"移除上线监控商品: {product.url}")
        return True

    def remove_product_by_url(self, db: Session, url: str) -> bool:
        """
        通过URL移除监控商品

        Args:
            db: 数据库会话
            url: 商品URL

        Returns:
            bool: 是否成功删除
        """
        product = db.query(ReleaseMonitorProduct).filter(
            ReleaseMonitorProduct.url == url
        ).first()

        if not product:
            return False

        db.delete(product)
        db.commit()

        logger.info(f"移除上线监控商品: {url}")
        return True

    def get_all_products(self, db: Session, active_only: bool = True) -> List[ReleaseMonitorProduct]:
        """
        获取所有监控商品

        Args:
            db: 数据库会话
            active_only: 是否只返回激活的商品

        Returns:
            List[ReleaseMonitorProduct]: 商品列表
        """
        query = db.query(ReleaseMonitorProduct)

        if active_only:
            query = query.filter(ReleaseMonitorProduct.is_active == True)

        return query.order_by(ReleaseMonitorProduct.created_at.desc()).all()

    def get_product(self, db: Session, product_id: int) -> Optional[ReleaseMonitorProduct]:
        """获取单个商品"""
        return db.query(ReleaseMonitorProduct).filter(
            ReleaseMonitorProduct.id == product_id
        ).first()

    def check_product(self, db: Session, product: ReleaseMonitorProduct) -> Tuple[DetectionResult, bool]:
        """
        检测单个商品状态

        Args:
            db: 数据库会话
            product: 商品记录

        Returns:
            Tuple[DetectionResult, bool]: 检测结果和是否发送了通知
        """
        detector = get_detector(product.website_type)
        notification_sent = False

        if not detector:
            logger.error(f"不支持的网站类型: {product.website_type}")
            return DetectionResult(status='error', error='不支持的网站类型'), False

        try:
            result = detector.check(product.url)

            # 验证状态值
            if result.status not in VALID_STATUSES:
                logger.warning(f"无效的状态值: {result.status}，标记为error")
                result = DetectionResult(status='error', error=f'无效的状态值: {result.status}')

            # 更新商品状态
            previous_status = product.status
            product.status = result.status
            product.last_check_time = datetime.utcnow()
            product.last_check_result = result.to_json()

            if result.product_name and product.name == "未知商品":
                product.name = result.product_name

            if result.scheduled_release:
                product.scheduled_release_time = result.scheduled_release

            if result.status == 'error':
                product.consecutive_failures += 1
                product.last_error = result.error
            else:
                product.consecutive_failures = 0
                product.last_error = None

            # 检查是否需要发送通知
            if self._should_notify(previous_status, result.status):
                notification_sent = self._send_notification(product, result)
                if notification_sent:
                    product.notification_sent = True
                    product.notification_sent_at = datetime.utcnow()
                    logger.info(f"上线通知已发送: {product.url}")
                else:
                    logger.warning(f"上线通知发送失败: {product.url}")

            # 当状态从 available 变为其他状态时，重置通知状态
            if previous_status == ReleaseMonitorStatus.AVAILABLE.value and result.status != ReleaseMonitorStatus.AVAILABLE.value:
                product.notification_sent = False
                product.notification_sent_at = None
                logger.info(f"商品状态降级，重置通知状态: {product.url}")

            db.commit()

            return result, notification_sent

        except Exception as e:
            logger.exception(f"检测商品失败: {product.url}")
            product.consecutive_failures += 1
            product.last_error = str(e)
            db.commit()
            return DetectionResult(status='error', error=str(e)), False

    def check_all_products(self, db: Session) -> Dict[str, Any]:
        """
        检测所有激活的商品

        Returns:
            Dict: 检测结果摘要
        """
        products = self.get_all_products(db, active_only=True)

        results = {
            'total': len(products),
            'checked': 0,
            'available': 0,
            'coming_soon': 0,
            'unavailable': 0,
            'errors': 0,
            'notifications_sent': 0,
        }

        for product in products:
            result, notification_sent = self.check_product(db, product)
            results['checked'] += 1

            if result.status == 'available':
                results['available'] += 1
            elif result.status == 'coming_soon':
                results['coming_soon'] += 1
            elif result.status == 'unavailable':
                results['unavailable'] += 1
            elif result.status == 'error':
                results['errors'] += 1

            if notification_sent:
                results['notifications_sent'] += 1

        logger.info(f"上线监控检测完成: {results}")
        return results

    def _should_notify(self, previous_status: str, current_status: str) -> bool:
        """判断是否需要发送通知"""
        # 只有从非可用状态变为可用状态时才通知
        non_available_statuses = [
            ReleaseMonitorStatus.COMING_SOON.value,
            ReleaseMonitorStatus.UNAVAILABLE.value,
            ReleaseMonitorStatus.ERROR.value,
        ]

        return (
            previous_status in non_available_statuses and
            current_status == ReleaseMonitorStatus.AVAILABLE.value
        )

    def _send_notification(self, product: ReleaseMonitorProduct, result: DetectionResult) -> bool:
        """发送上线通知，返回是否成功"""
        try:
            subject = f"【上线通知】{product.name} 已开始发售!"

            # 构建库存信息
            stock_info = ""
            if result.variants:
                stock_details = []
                if result.total_in_stock > 0:
                    stock_details.append(f"充足库存: {result.total_in_stock}个")
                if result.total_low_stock > 0:
                    stock_details.append(f"库存紧张: {result.total_low_stock}个")
                if result.total_out_of_stock > 0:
                    stock_details.append(f"已售罄: {result.total_out_of_stock}个")
                stock_info = " | ".join(stock_details) if stock_details else "库存信息未获取到"
            else:
                stock_info = "库存信息未获取到"

            html_content = self._build_notification_html(product, result, stock_info)

            return self.notifier.send_email(subject, html_content)

        except Exception as e:
            logger.error(f"发送上线通知失败: {e}")
            return False

    def _build_notification_html(
        self,
        product: ReleaseMonitorProduct,
        result: DetectionResult,
        stock_info: str
    ) -> str:
        """构建通知邮件HTML"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # HTML 转义外部内容，防止注入
        safe_product_name = html.escape(result.product_name or product.name or '未知商品')
        safe_price = html.escape(result.price or '价格未知')
        safe_stock_info = html.escape(stock_info)
        safe_url = html.escape(product.url)

        # 构建变体列表
        variants_html = ""
        if result.variants:
            variant_rows = []
            for v in result.variants:
                status_color = {
                    'in_stock': '#27ae60',
                    'low_stock': '#f39c12',
                    'out_of_stock': '#e74c3c',
                }.get(v.stock_status, '#999')

                status_text = {
                    'in_stock': '在库あり',
                    'low_stock': '残りわずか',
                    'out_of_stock': '在库なし',
                }.get(v.stock_status, '未知')

                # 转义尺码和颜色
                safe_size = html.escape(v.size or '-')
                safe_color = html.escape(v.color or '-')

                variant_rows.append(f"""
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{safe_size}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{safe_color}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee; color: {status_color}; font-weight: bold;">{status_text}</td>
                </tr>
                """)

            variants_html = f"""
            <div style="margin: 20px 0;">
                <h3 style="color: #333; margin-bottom: 10px;">库存详情</h3>
                <table style="width: 100%; border-collapse: collapse; background: #f8f9fa;">
                    <tr style="background: #667eea; color: white;">
                        <th style="padding: 10px; text-align: left;">尺码</th>
                        <th style="padding: 10px; text-align: left;">颜色</th>
                        <th style="padding: 10px; text-align: left;">状态</th>
                    </tr>
                    {''.join(variant_rows)}
                </table>
            </div>
            """

        # 获取网站名称
        website_name = {
            'daytona_park': 'Daytona Park',
            'rakuten': 'Rakuten',
        }.get(product.website_type, html.escape(product.website_type))

        email_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
                <h1 style="color: white; margin: 0; font-size: 24px;">商品已上线!</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">快去抢购吧!</p>
            </div>

            <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                <h2 style="color: #333; margin-top: 0;">{safe_product_name}</h2>

                <table style="width: 100%;">
                    <tr>
                        <td style="padding: 8px 0; color: #666;">网站</td>
                        <td style="padding: 8px 0; font-weight: bold;">{website_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #666;">价格</td>
                        <td style="padding: 8px 0; font-weight: bold; color: #e74c3c;">{safe_price}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #666;">库存概况</td>
                        <td style="padding: 8px 0; font-weight: bold;">{safe_stock_info}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #666;">检测时间</td>
                        <td style="padding: 8px 0;">{now}</td>
                    </tr>
                </table>
            </div>

            {variants_html}

            <div style="text-align: center; margin-top: 30px;">
                <a href="{safe_url}" style="display: inline-block; background: #e74c3c; color: white; padding: 15px 40px; border-radius: 5px; text-decoration: none; font-weight: bold; font-size: 18px;">
                    立即购买
                </a>
            </div>

            <p style="color: #999; text-align: center; margin-top: 30px; font-size: 12px;">
                此邮件由商品上线监控系统自动发送
            </p>
        </body>
        </html>
        """

        return email_html

    def toggle_product_active(self, db: Session, product_id: int, is_active: bool) -> bool:
        """切换商品监控状态"""
        product = db.query(ReleaseMonitorProduct).filter(
            ReleaseMonitorProduct.id == product_id
        ).first()

        if not product:
            return False

        product.is_active = is_active

        # 重新启用监控时重置通知状态
        if is_active:
            product.notification_sent = False
            product.notification_sent_at = None

        db.commit()

        logger.info(f"切换商品监控状态: {product.url}, is_active={is_active}")
        return True

    def get_status_summary(self, db: Session) -> Dict[str, Any]:
        """获取监控状态摘要"""
        products = self.get_all_products(db, active_only=False)

        summary = {
            'total': len(products),
            'active': sum(1 for p in products if p.is_active),
            'coming_soon': sum(1 for p in products if p.status == ReleaseMonitorStatus.COMING_SOON.value),
            'available': sum(1 for p in products if p.status == ReleaseMonitorStatus.AVAILABLE.value),
            'unavailable': sum(1 for p in products if p.status == ReleaseMonitorStatus.UNAVAILABLE.value),
            'error': sum(1 for p in products if p.status == ReleaseMonitorStatus.ERROR.value),
            # notified 统计已上线且已通知的商品数量
            'notified': sum(1 for p in products if p.notification_sent and p.status == ReleaseMonitorStatus.AVAILABLE.value),
        }

        return summary


# 创建全局服务实例
release_monitor_service = ReleaseMonitorService()
