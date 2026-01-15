"""
通知模块
支持邮件、微信（ServerChan）与 QQ（Qmsg 酱）多通道通知
"""
from abc import ABC, abstractmethod
import html
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime
from typing import List, Optional, Dict
from loguru import logger
import requests

from ..config import get_config
from .scraper import ProductInfo
from .inventory_scraper import InventoryChange


def _normalize_inventory_status(status: str) -> str:
    """库存状态标准化（用于展示与判定）"""
    return (status or "").strip()


def _inventory_status_display(status: str) -> str:
    """库存状态展示文案"""
    key = _normalize_inventory_status(status).lower()
    if key in {"instock", "in_stock"}:
        return "有货"
    if key in {"outofstock", "out_of_stock", "oos"}:
        return "无货"
    if key in {"lowstock", "low_stock"}:
        return "库存紧张"
    if key in {"unknown", ""}:
        return "未知"
    # 兜底：直接展示原始状态，便于排查站点差异
    return _normalize_inventory_status(status)


def _inventory_status_is_available(status: str) -> Optional[bool]:
    """判断状态是否可购买（未知返回 None）"""
    key = _normalize_inventory_status(status).lower()
    if key in {"instock", "in_stock", "lowstock", "low_stock"}:
        return True
    if key in {"outofstock", "out_of_stock", "oos"}:
        return False
    if key in {"unknown", ""}:
        return None
    return None


def _inventory_change_type(change: InventoryChange) -> str:
    """计算变化类型标识（补货/售罄/状态变化）"""
    try:
        if getattr(change, "became_available", False) is True:
            return "补货"
    except Exception:
        # became_available 字段异常时继续走兼容逻辑
        pass

    old_available = _inventory_status_is_available(getattr(change, "old_status", ""))
    new_available = _inventory_status_is_available(getattr(change, "new_status", ""))
    if old_available is False and new_available is True:
        return "补货"
    if old_available is True and new_available is False:
        return "售罄"
    return "状态变化"


def _inventory_notification_title(changes: List[InventoryChange]) -> str:
    """根据变化列表生成通知类型标题（补货通知/售罄通知/库存变化通知）"""
    types = {_inventory_change_type(c) for c in (changes or [])}
    if types == {"补货"}:
        return "补货通知"
    if types == {"售罄"}:
        return "售罄通知"
    return "库存变化通知"


def _format_inventory_quantity(change: InventoryChange) -> str:
    """
    格式化库存数量展示（若无数量信息则返回空串）

    说明：InventoryChange 在不同站点/抓取器中可能会被动态附加数量字段，
    这里做最大兼容：优先读取 new_quantity/quantity。
    """
    quantity = getattr(change, "new_quantity", None)
    if quantity is None:
        quantity = getattr(change, "quantity", None)

    if quantity is None:
        return ""

    try:
        if isinstance(quantity, bool):
            return ""
        if isinstance(quantity, int):
            return f" (库存: {quantity}件)"
        if isinstance(quantity, float):
            return f" (库存: {int(quantity)}件)"
        if isinstance(quantity, str):
            text = quantity.strip()
            if not text:
                return ""
            if "件" in text:
                return f" (库存: {text})"
            return f" (库存: {text}件)"
    except Exception:
        return ""

    return ""


class BaseNotifier(ABC):
    """通知通道抽象基类"""

    @abstractmethod
    def send(self, title: str, content: str) -> bool:
        """发送通知（不同通道可自行解释 content 格式）"""
        raise NotImplementedError

    @abstractmethod
    def send_test(self) -> bool:
        """发送测试通知"""
        raise NotImplementedError


class EmailNotifier(BaseNotifier):
    """邮件通知服务"""

    def __init__(self):
        self.config = get_config()

    def _create_connection(self):
        """创建 SMTP 连接"""
        email_config = self.config.email

        context = ssl.create_default_context()
        server = smtplib.SMTP_SSL(
            email_config.smtp_server,
            email_config.smtp_port,
            context=context
        )
        server.login(email_config.sender, email_config.password)
        return server

    def send_email(self, subject: str, html_content: str) -> bool:
        """发送邮件"""
        if not self.config.email.enabled:
            logger.info("邮件通知已禁用")
            return False

        email_config = self.config.email
        server = None

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = Header(subject, 'utf-8')
            msg['From'] = email_config.sender
            msg['To'] = email_config.receiver

            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)

            # 创建连接并发送（不使用 with 语句，避免兼容性问题）
            server = self._create_connection()
            server.sendmail(
                email_config.sender,
                email_config.receiver,
                msg.as_string()
            )
            server.quit()

            logger.info(f"邮件发送成功: {subject}")
            return True

        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return False
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass

    def send(self, title: str, content: str) -> bool:
        """BaseNotifier.send 的邮件实现，等价于 send_email"""
        return self.send_email(title, content)

    def send_test(self) -> bool:
        """BaseNotifier.send_test 的邮件实现"""
        return self.send_test_email()

    def send_change_notification(
        self,
        previous_count: int,
        current_count: int,
        added_products: List[ProductInfo],
        removed_products: List[ProductInfo]
    ) -> bool:
        """发送商品变化通知"""
        notification_config = self.config.notification

        # 检查是否需要发送通知
        if len(added_products) > 0 and not notification_config.notify_on_added:
            logger.info("新增通知已禁用，跳过")
            return False
        if len(removed_products) > 0 and not notification_config.notify_on_removed:
            logger.info("下架通知已禁用，跳过")
            return False
        if len(added_products) == 0 and len(removed_products) == 0:
            logger.info("无变化，不发送通知")
            return False

        # 构建邮件主题
        change_text = []
        if len(added_products) > 0:
            change_text.append(f"+{len(added_products)}件新品")
        if len(removed_products) > 0:
            change_text.append(f"-{len(removed_products)}件下架")

        subject = f"【Arc'teryx 商品变化】{', '.join(change_text)} | 当前共{current_count}件"

        # 构建邮件内容
        html_content = self._build_change_email(
            previous_count,
            current_count,
            added_products,
            removed_products
        )

        return self.send_email(subject, html_content)

    def send_inventory_change_notification(
        self,
        product_name: str,
        product_url: str,
        changes: List[InventoryChange],
        site_name: str = "Arc'teryx"  # 支持 SCHEELS, Rakuten 等
    ) -> bool:
        """
        发送库存变化通知（补货/售罄）

        Args:
            product_name: 商品名称
            product_url: 商品链接
            changes: 库存变化列表
            site_name: 站点来源名称（如 Arc'teryx / SCHEELS / Rakuten）

        Returns:
            是否发送成功（仅表示邮件通道结果）
        """
        if not changes:
            logger.info("无库存变化，不发送通知")
            return False

        try:
            notice_title = _inventory_notification_title(changes)
            subject = f"【{notice_title}】{site_name} {product_name}".strip()

            html_content = self._build_inventory_change_email(
                product_name=product_name,
                product_url=product_url,
                changes=changes,
                site_name=site_name,
            )

            return self.send_email(subject, html_content)
        except Exception as e:
            logger.error(f"构建/发送库存变化通知失败: {type(e).__name__}: {e}")
            return False

    def _build_inventory_change_email(
        self,
        product_name: str,
        product_url: str,
        changes: List[InventoryChange],
        site_name: str,
    ) -> str:
        """构建库存变化通知邮件内容（HTML）"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notice_title = _inventory_notification_title(changes)

        # 对动态内容进行 HTML 转义，防止 XSS
        safe_product_name = html.escape(product_name or "")
        safe_site_name = html.escape(site_name or "")
        safe_product_url = html.escape(product_url or "")

        # 根据通知类型选择配色
        if notice_title == "补货通知":
            gradient = "linear-gradient(135deg, #27ae60 0%, #2ecc71 100%)"
            header_icon = "[补货]"
        elif notice_title == "售罄通知":
            gradient = "linear-gradient(135deg, #e74c3c 0%, #c0392b 100%)"
            header_icon = "[售罄]"
        else:
            gradient = "linear-gradient(135deg, #3498db 0%, #2980b9 100%)"
            header_icon = "[变化]"

        # 按颜色分组（保持插入顺序）
        grouped: Dict[str, List[InventoryChange]] = {}
        for c in changes:
            color = (getattr(c, "color_name", "") or "").strip()
            grouped.setdefault(color, []).append(c)

        sections: List[str] = []
        has_color = any(grouped.keys())

        # 统一渲染表格（每个颜色一张表）
        for color_name, items in grouped.items():
            title_text = ""
            if has_color:
                display_color = html.escape(color_name or "未指定")
                title_text = f"""
                <h3 style="background: #2c3e50; color: white; padding: 10px 15px; margin: 0; border-radius: 5px 5px 0 0;">
                    颜色: {display_color}
                </h3>
                """

            rows: List[str] = []
            for change in items:
                size = html.escape((getattr(change, "size", "") or "").strip() or "-")
                old_text = html.escape(_inventory_status_display(getattr(change, "old_status", "")))
                new_text = html.escape(_inventory_status_display(getattr(change, "new_status", "")))
                change_text = f"{old_text} -> {new_text}"

                quantity_text = _format_inventory_quantity(change)
                quantity_cell = html.escape(quantity_text.replace(" (库存: ", "").replace(")", "") if quantity_text else "-")

                change_type = html.escape(_inventory_change_type(change))

                rows.append(f"""
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: center;">
                        <strong>{size}</strong>
                    </td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: center;">
                        {change_text}
                    </td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: center; color: #555;">
                        {quantity_cell}
                    </td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: center;">
                        {change_type}
                    </td>
                </tr>
                """)

            sections.append(f"""
            <div style="margin: 20px 0;">
                {title_text}
                <table style="width: 100%; border-collapse: collapse; background: #f8f9fa; border-radius: {('0 0 5px 5px' if has_color else '5px')}; overflow: hidden;">
                    <tr style="background: #ecf0f1;">
                        <th style="padding: 10px; text-align: center;">尺寸</th>
                        <th style="padding: 10px; text-align: center;">状态变化</th>
                        <th style="padding: 10px; text-align: center;">库存数量</th>
                        <th style="padding: 10px; text-align: center;">变化类型</th>
                    </tr>
                    {''.join(rows)}
                </table>
            </div>
            """)

        url_html = ""
        if safe_product_url:
            url_html = f'<a href="{safe_product_url}" style="color: #3498db; text-decoration: none;">{safe_product_url}</a>'

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: {gradient}; padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
                <h1 style="color: white; margin: 0; font-size: 24px;">{header_icon} {notice_title}</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">站点：{safe_site_name}</p>
            </div>

            <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                <h2 style="margin: 0 0 12px 0; color: #333;">{safe_product_name}</h2>
                <table style="width: 100%;">
                    <tr>
                        <td style="padding: 6px 0;">
                            <span style="color: #666;">商品链接</span><br>
                            <strong>{url_html or '（无）'}</strong>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0;">
                            <span style="color: #666;">通知时间</span><br>
                            <strong>{now}</strong>
                        </td>
                    </tr>
                </table>
            </div>

            {''.join(sections)}

            <div style="text-align: center; margin-top: 20px;">
                <p style="color: #999; font-size: 12px;">
                    此邮件由库存监控系统自动发送
                </p>
            </div>
        </body>
        </html>
        """

        return html_content

    def _build_change_email(
        self,
        previous_count: int,
        current_count: int,
        added_products: List[ProductInfo],
        removed_products: List[ProductInfo]
    ) -> str:
        """构建变化通知邮件内容"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        change_diff = current_count - previous_count
        change_sign = "+" if change_diff >= 0 else ""

        # 新增商品列表 HTML
        added_html = ""
        if added_products:
            items = []
            for i, p in enumerate(added_products, 1):
                price_text = f"${p.price:.2f}" if p.price else "价格未知"
                if p.original_price and p.original_price > (p.price or 0):
                    price_text += f' <span style="text-decoration: line-through; color: #999;">${p.original_price:.2f}</span>'
                    price_text += ' <span style="color: #e74c3c;">🔥促销</span>'

                items.append(f"""
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #eee;">
                        <strong>{i}. {p.name}</strong><br>
                        <span style="color: #27ae60;">💰 {price_text}</span><br>
                        <a href="{p.url}" style="color: #3498db; text-decoration: none;">🔗 查看详情</a>
                    </td>
                </tr>
                """)

            added_html = f"""
            <div style="margin: 20px 0;">
                <h3 style="background: #27ae60; color: white; padding: 10px 15px; margin: 0; border-radius: 5px 5px 0 0;">
                    🆕 新增商品（{len(added_products)}件）
                </h3>
                <table style="width: 100%; border-collapse: collapse; background: #f8f9fa; border-radius: 0 0 5px 5px;">
                    {''.join(items)}
                </table>
            </div>
            """

        # 下架商品列表 HTML
        removed_html = ""
        if removed_products:
            items = []
            for i, p in enumerate(removed_products, 1):
                price_text = f"${p.price:.2f}" if p.price else "价格未知"
                items.append(f"""
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #eee;">
                        <strong>{i}. {p.name}</strong><br>
                        <span style="color: #95a5a6;">💰 {price_text}</span>
                    </td>
                </tr>
                """)

            removed_html = f"""
            <div style="margin: 20px 0;">
                <h3 style="background: #e74c3c; color: white; padding: 10px 15px; margin: 0; border-radius: 5px 5px 0 0;">
                    ❌ 下架商品（{len(removed_products)}件）
                </h3>
                <table style="width: 100%; border-collapse: collapse; background: #f8f9fa; border-radius: 0 0 5px 5px;">
                    {''.join(items)}
                </table>
            </div>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
                <h1 style="color: white; margin: 0; font-size: 24px;">Arc'teryx 商品监控</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">SCHEELS 网站商品变化通知</p>
            </div>

            <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                <table style="width: 100%;">
                    <tr>
                        <td style="padding: 10px 0;">
                            <span style="color: #666;">⏰ 检测时间</span><br>
                            <strong>{now}</strong>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0;">
                            <span style="color: #666;">📊 数量变化</span><br>
                            <strong style="font-size: 20px;">{previous_count} → {current_count}</strong>
                            <span style="color: {'#27ae60' if change_diff >= 0 else '#e74c3c'}; font-weight: bold;">
                                ({change_sign}{change_diff})
                            </span>
                        </td>
                    </tr>
                </table>
            </div>

            {added_html}
            {removed_html}

            <div style="text-align: center; margin-top: 30px; padding: 20px; background: #f8f9fa; border-radius: 10px;">
                <a href="{self.config.monitor.url}" style="display: inline-block; background: #3498db; color: white; padding: 12px 30px; border-radius: 5px; text-decoration: none; font-weight: bold;">
                    🌐 查看全部商品
                </a>
                <p style="color: #999; margin-top: 15px; font-size: 12px;">
                    此邮件由 Arc'teryx 商品监控系统自动发送
                </p>
            </div>
        </body>
        </html>
        """

        return html

    def send_error_notification(self, error_message: str) -> bool:
        """发送错误告警通知"""
        if not self.config.notification.notify_on_error:
            logger.info("错误通知已禁用，跳过")
            return False

        subject = "【Arc'teryx 监控告警】系统运行异常"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: #e74c3c; padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
                <h1 style="color: white; margin: 0;">⚠️ 系统告警</h1>
            </div>

            <div style="background: #f8f9fa; padding: 20px; border-radius: 10px;">
                <p><strong>⏰ 时间：</strong>{now}</p>
                <p><strong>❌ 错误信息：</strong></p>
                <pre style="background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 5px; overflow-x: auto;">{error_message}</pre>
            </div>

            <p style="color: #999; text-align: center; margin-top: 20px; font-size: 12px;">
                请检查监控系统运行状态
            </p>
        </body>
        </html>
        """

        return self.send_email(subject, html)

    def send_test_email(self) -> bool:
        """发送测试邮件"""
        subject = "【Arc'teryx 监控】测试邮件"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
                <h1 style="color: white; margin: 0;">✅ 测试邮件</h1>
            </div>

            <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; text-align: center;">
                <p style="font-size: 18px;">邮件配置正确！</p>
                <p style="color: #666;">发送时间：{now}</p>
                <p style="color: #27ae60;">您的 Arc'teryx 商品监控系统已准备就绪。</p>
            </div>
        </body>
        </html>
        """

        return self.send_email(subject, html)


class ServerChanNotifier(BaseNotifier):
    """微信 ServerChan 通知通道"""

    def __init__(self):
        self.config = get_config()

    def send(self, title: str, content: str) -> bool:
        """发送 ServerChan 消息（content 为 Markdown）"""
        wechat_config = self.config.wechat
        if not wechat_config.enabled:
            logger.info("微信通知已禁用")
            return False
        if not wechat_config.sendkey:
            logger.warning("微信 sendkey 为空，无法发送")
            return False

        url = f"https://sctapi.ftqq.com/{wechat_config.sendkey}.send"
        try:
            resp = requests.post(
                url,
                data={"title": title, "desp": content},
                timeout=10,
            )
            # ServerChan API 成功响应: {"code": 0, "message": "", "data": {...}}
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if data.get("code") == 0:
                        logger.info(f"微信通知发送成功: {title}")
                        return True
                    logger.error(f"微信通知发送失败: code={data.get('code')}, message={data.get('message')}")
                except ValueError:
                    logger.error(f"微信通知响应解析失败: {resp.text}")
            else:
                logger.error(f"微信通知发送失败: status={resp.status_code}, body={resp.text}")
            return False
        except requests.Timeout:
            logger.error("微信通知发送超时")
            return False
        except requests.RequestException as e:
            logger.error(f"微信通知发送异常: {e}")
            return False

    def send_test(self) -> bool:
        """发送测试微信通知"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = "【Arc'teryx 监控】微信测试通知"
        desp = f"检测时间：{now}\n\n如果你看到这条消息，说明微信 ServerChan 配置正确。"
        return self.send(title, desp)


class QmsgNotifier(BaseNotifier):
    """QQ Qmsg 酱通知通道"""

    def __init__(self):
        self.config = get_config()

    def send(self, title: str, content: str) -> bool:
        """发送 Qmsg 消息（content 为纯文本/Markdown 均可）"""
        qq_config = self.config.qq
        if not qq_config.enabled:
            logger.info("QQ 通知已禁用")
            return False
        if not qq_config.key:
            logger.warning("QQ key 为空，无法发送")
            return False
        if not qq_config.qq:
            logger.warning("QQ 号码为空，无法发送")
            return False

        url = f"https://qmsg.zendee.cn/send/{qq_config.key}"
        msg = f"{title}\n\n{content}"
        try:
            resp = requests.post(
                url,
                data={"msg": msg, "qq": qq_config.qq},
                timeout=10,
            )
            # Qmsg API 成功响应: {"success": true, "reason": "..."}
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if data.get("success") is True:
                        logger.info(f"QQ 通知发送成功: {title}")
                        return True
                    logger.error(f"QQ 通知发送失败: reason={data.get('reason')}")
                except ValueError:
                    logger.error(f"QQ 通知响应解析失败: {resp.text}")
            else:
                logger.error(f"QQ 通知发送失败: status={resp.status_code}, body={resp.text}")
            return False
        except requests.Timeout:
            logger.error("QQ 通知发送超时")
            return False
        except requests.RequestException as e:
            logger.error(f"QQ 通知发送异常: {e}")
            return False

    def send_test(self) -> bool:
        """发送测试 QQ 通知"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = "【Arc'teryx 监控】QQ 测试通知"
        content = f"检测时间：{now}\n如果你看到这条消息，说明 QQ Qmsg 酱配置正确。"
        return self.send(title, content)


class MultiChannelNotifier:
    """多通道通知聚合器，对外保持旧接口不变"""

    def __init__(self):
        self.config = get_config()
        self.email_notifier = EmailNotifier()
        self.wechat_notifier = ServerChanNotifier()
        self.qq_notifier = QmsgNotifier()

    def _build_change_markdown(
        self,
        previous_count: int,
        current_count: int,
        added_products: List[ProductInfo],
        removed_products: List[ProductInfo],
    ) -> str:
        """构建变化通知的 Markdown/文本内容"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        change_diff = current_count - previous_count
        change_sign = "+" if change_diff >= 0 else ""

        parts: List[str] = [
            f"检测时间：{now}",
            f"数量变化：{previous_count} → {current_count}（{change_sign}{change_diff}）",
        ]

        if added_products:
            parts.append(f"\n新增商品（{len(added_products)}件）：")
            for i, p in enumerate(added_products, 1):
                price_text = f"${p.price:.2f}" if p.price else "价格未知"
                if p.original_price and p.original_price > (p.price or 0):
                    price_text += f"（原价 ${p.original_price:.2f}，促销）"
                parts.append(f"{i}. {p.name} - {price_text}")
                if p.url:
                    parts.append(f"   链接：{p.url}")

        if removed_products:
            parts.append(f"\n下架商品（{len(removed_products)}件）：")
            for i, p in enumerate(removed_products, 1):
                price_text = f"${p.price:.2f}" if p.price else "价格未知"
                parts.append(f"{i}. {p.name} - {price_text}")

        parts.append(f"\n监控地址：{self.config.monitor.url}")
        return "\n".join(parts)

    def _build_error_markdown(self, error_message: str) -> str:
        """构建错误通知内容"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"时间：{now}\n\n错误信息：\n{error_message}"

    def _build_inventory_change_markdown(
        self,
        product_name: str,
        product_url: str,
        changes: List[InventoryChange],
        site_name: str,
    ) -> str:
        """构建库存变化通知的 Markdown/文本内容（用于微信/QQ）"""
        parts: List[str] = []
        if product_name:
            parts.append(f"商品：{product_name}")
        if site_name:
            parts.append(f"站点：{site_name}")
        if product_url:
            parts.append(f"链接：{product_url}")
        parts.append("")  # 与明细分隔，提升可读性

        # 按颜色分组（保持插入顺序）
        grouped: dict = {}
        for c in changes or []:
            color = (getattr(c, "color_name", "") or "").strip()
            grouped.setdefault(color, []).append(c)

        has_color = any(k for k in grouped.keys())

        first_group = True
        for color_name, items in grouped.items():
            if has_color:
                if not first_group:
                    parts.append("")  # 分隔不同颜色分组
                parts.append(f"颜色: {color_name or '未指定'}")

            for change in items:
                size = (getattr(change, "size", "") or "").strip() or "-"
                old_text = _inventory_status_display(getattr(change, "old_status", ""))
                new_text = _inventory_status_display(getattr(change, "new_status", ""))
                change_type = _inventory_change_type(change)

                quantity_text = _format_inventory_quantity(change).strip()
                extras = [x for x in [quantity_text, f"【{change_type}】"] if x]
                extra_text = f" {' '.join(extras)}" if extras else ""

                parts.append(f"尺码 {size}: {old_text} -> {new_text}{extra_text}")

            first_group = False

        return "\n".join(parts).strip()

    def send_email(self, subject: str, html_content: str) -> bool:
        """兼容旧代码的邮件发送接口（仅邮件通道）"""
        return self.email_notifier.send_email(subject, html_content)

    def send_change_notification(
        self,
        previous_count: int,
        current_count: int,
        added_products: List[ProductInfo],
        removed_products: List[ProductInfo],
    ) -> bool:
        """向所有启用通道发送商品变化通知"""
        # 先走邮件原有逻辑，保证行为一致
        email_sent = self.email_notifier.send_change_notification(
            previous_count,
            current_count,
            added_products,
            removed_products,
        )

        notification_config = self.config.notification
        if (added_products and not notification_config.notify_on_added) or \
           (removed_products and not notification_config.notify_on_removed) or \
           (not added_products and not removed_products):
            return email_sent

        # 其他通道使用文本/Markdown
        change_text = []
        if added_products:
            change_text.append(f"+{len(added_products)}件新品")
        if removed_products:
            change_text.append(f"-{len(removed_products)}件下架")
        title = f"Arc'teryx 商品变化：{', '.join(change_text)} | 当前共{current_count}件"
        content = self._build_change_markdown(
            previous_count,
            current_count,
            added_products,
            removed_products,
        )

        wechat_sent = self.wechat_notifier.send(title, content)
        qq_sent = self.qq_notifier.send(title, content)

        return any([email_sent, wechat_sent, qq_sent])

    def send_inventory_change_notification(
        self,
        product_name: str,
        product_url: str,
        changes: List[InventoryChange],
        site_name: str = "Arc'teryx"  # 支持 SCHEELS, Rakuten 等
    ) -> bool:
        """向所有启用通道发送库存变化通知（补货/售罄）"""
        # 邮件通道：走 EmailNotifier 的统一实现
        email_sent = self.email_notifier.send_inventory_change_notification(
            product_name=product_name,
            product_url=product_url,
            changes=changes,
            site_name=site_name,
        )

        if not changes:
            return email_sent

        try:
            notice_title = _inventory_notification_title(changes)
            title = f"【{notice_title}】{site_name} {product_name}".strip()
            content = self._build_inventory_change_markdown(
                product_name=product_name,
                product_url=product_url,
                changes=changes,
                site_name=site_name,
            )
        except Exception as e:
            logger.error(f"构建库存变化多通道通知失败: {type(e).__name__}: {e}")
            return email_sent

        wechat_sent = self.wechat_notifier.send(title, content)
        qq_sent = self.qq_notifier.send(title, content)

        return any([email_sent, wechat_sent, qq_sent])

    def send_error_notification(self, error_message: str) -> bool:
        """向所有启用通道发送错误告警通知"""
        email_sent = self.email_notifier.send_error_notification(error_message)

        if not self.config.notification.notify_on_error:
            return email_sent

        title = "Arc'teryx 监控告警：系统运行异常"
        content = self._build_error_markdown(error_message)

        wechat_sent = self.wechat_notifier.send(title, content)
        qq_sent = self.qq_notifier.send(title, content)

        return any([email_sent, wechat_sent, qq_sent])

    def send_test_email(self) -> bool:
        """发送测试邮件（旧接口）"""
        return self.email_notifier.send_test_email()

    def send_test_wechat(self) -> bool:
        """发送测试微信通知"""
        return self.wechat_notifier.send_test()

    def send_test_qq(self) -> bool:
        """发送测试 QQ 通知"""
        return self.qq_notifier.send_test()


# 创建多通道通知服务单例，并兼容旧导入名称
multi_channel_notifier = MultiChannelNotifier()
email_notifier = multi_channel_notifier
