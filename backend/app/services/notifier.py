"""
邮件通知模块
使用 QQ 邮箱 SMTP 发送通知邮件
"""
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime
from typing import List, Optional
from loguru import logger

from ..config import get_config
from .scraper import ProductInfo


class EmailNotifier:
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


# 创建通知服务单例
email_notifier = EmailNotifier()
