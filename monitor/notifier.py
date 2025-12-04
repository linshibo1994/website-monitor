"""邮件通知器，负责发送商品状态提醒。"""
from __future__ import annotations

import logging
import smtplib
import ssl
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List


class EmailNotifier:
    """基于 SMTP 的邮件通知实现。"""

    def __init__(self, email_config: Dict[str, Any], max_retries: int = 3) -> None:
        self.smtp_server: str = email_config["smtp_server"]
        self.smtp_port: int = email_config["smtp_port"]
        self.use_tls: bool = bool(email_config.get("use_tls", True))
        self.sender_email: str = email_config["sender_email"]
        self.sender_password: str = email_config["sender_password"]
        self.recipient_emails: List[str] = email_config.get("recipient_emails", [])
        self.max_retries = max_retries

    def send_availability_notification(self, monitor_name: str, product_info: Dict[str, Any]) -> None:
        """发送商品重新上架通知。"""
        subject = f"【乐天监控】{monitor_name} 已重新上架"
        html_body = self._build_html_body(monitor_name, product_info)
        self._send_email(subject, html_body)

    def _send_email(self, subject: str, html_body: str) -> None:
        """内部发送逻辑，包含重试机制。"""
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = self.sender_email
        message["To"] = ", ".join(self.recipient_emails)
        message.attach(MIMEText(html_body, "html", "utf-8"))

        for attempt in range(1, self.max_retries + 1):
            server = None
            try:
                # 创建 SSL 上下文以增强兼容性
                context = ssl.create_default_context()

                # 465 端口使用隐式 SSL (SMTP_SSL)，587 端口使用显式 TLS (STARTTLS)
                if self.smtp_port == 465:
                    server = smtplib.SMTP_SSL(
                        self.smtp_server,
                        self.smtp_port,
                        timeout=15,
                        context=context
                    )
                else:
                    server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=15)
                    if self.use_tls:
                        server.starttls(context=context)

                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, self.recipient_emails, message.as_string())
                logging.info("邮件发送成功，收件人: %s", self.recipient_emails)

                # QQ 邮箱关闭连接时可能返回异常响应，但邮件已发送成功，忽略此错误
                try:
                    server.quit()
                except (smtplib.SMTPResponseException, smtplib.SMTPServerDisconnected):
                    pass  # 邮件已发送，忽略关闭连接时的错误

                return

            except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
                logging.error("邮件发送失败(第 %s 次): %s", attempt, exc)
                if attempt == self.max_retries:
                    raise
                time.sleep(min(2 ** attempt, 10))
            finally:
                if server:
                    try:
                        server.close()
                    except:  # noqa: E722 - 清理时忽略所有异常
                        pass

    @staticmethod
    def _build_html_body(monitor_name: str, product_info: Dict[str, Any]) -> str:
        """构造包含商品信息的 HTML 模板。"""
        product_name = product_info.get("product_name") or "未知商品"
        price = product_info.get("price") or "价格未提供"
        url = product_info.get("url")
        status_code = product_info.get("status_code")
        return f"""
        <html>
          <body>
            <h2>🎉 {monitor_name} 已重新上架</h2>
            <p>系统检测到监控页从 404/错误状态切换为正常页面，请尽快完成采购。</p>
            <table border=\"1\" cellpadding=\"6\" cellspacing=\"0\" style=\"border-collapse:collapse;\">
              <tr><th align=\"left\">商品名称</th><td>{product_name}</td></tr>
              <tr><th align=\"left\">参考价格</th><td>{price}</td></tr>
              <tr><th align=\"left\">最近状态码</th><td>{status_code}</td></tr>
              <tr><th align=\"left\">商品链接</th><td><a href=\"{url}\">{url}</a></td></tr>
            </table>
            <p>如需关闭提醒，请修改 monitor.urls 配置或停用任务。</p>
          </body>
        </html>
        """


__all__ = ["EmailNotifier"]
