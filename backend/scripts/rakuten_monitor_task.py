#!/usr/bin/env python3
"""乐天单品巡检任务，负责检测特定商品是否恢复可用并发送通知。"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

import requests
import yaml
from bs4 import BeautifulSoup

from backend.app.services.rakuten_monitor.config import ConfigError, load_config
from backend.app.services.rakuten_monitor.notifier import EmailNotifier

TARGET_URL = "https://item.rakuten.co.jp/auc-refalt/531-09893/"
MONITOR_NAME = "乐天 Refalt 商品监控"
STATE_FILE = Path("data/rakuten_state.json")
DEFAULT_INTERVAL_SECONDS = 300
REQUEST_TIMEOUT = 30  # 乐天网站响应较慢，需要约11秒，设置30秒确保稳定


def load_project_config(config_path: str | None = None) -> Dict[str, Any]:
    """优先使用项目内的 load_config，失败时退回到直接解析 YAML（保留环境变量覆盖）。"""
    try:
        return load_config(config_path)
    except ConfigError as exc:
        # monitor.urls 校验失败是预期行为，因为本脚本不需要该字段
        if "monitor.urls" in str(exc):
            logging.debug("跳过 monitor.urls 校验（本脚本不需要该字段），直接读取配置")
        else:
            logging.warning("load_config 校验失败，尝试直接读取配置并应用环境变量: %s", exc)
    except FileNotFoundError as exc:
        logging.warning("未找到配置文件，使用空配置: %s", exc)
        return {}

    # Fallback 路径：直接读取 YAML 但仍应用环境变量覆盖
    import os
    resolved_path = Path(config_path or "config.yaml").resolve()
    if not resolved_path.exists():
        logging.error("未找到配置文件: %s", resolved_path)
        return {}

    with resolved_path.open("r", encoding="utf-8") as fp:
        config = yaml.safe_load(fp) or {}

    # 应用环境变量覆盖，保持与 load_config 一致的行为
    email_cfg = config.setdefault("email", {})
    if sender_email := os.getenv("MONITOR_SENDER_EMAIL"):
        email_cfg["sender_email"] = sender_email
    if sender_pwd := os.getenv("MONITOR_SENDER_PASSWORD"):
        email_cfg["sender_password"] = sender_pwd
    if recipients := os.getenv("MONITOR_RECIPIENTS"):
        email_cfg["recipient_emails"] = [addr.strip() for addr in recipients.split(",") if addr.strip()]

    return config


def prepare_email_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """将通用 email 配置转换为 EmailNotifier 所需格式。"""
    if not config:
        raise ValueError("email 配置缺失，无法构建通知器")

    normalized: Dict[str, Any] = dict(config)
    sender = normalized.pop("sender", None)
    password = normalized.pop("password", None)
    receiver = normalized.pop("receiver", None)
    receivers = normalized.pop("receivers", None)

    if sender and not normalized.get("sender_email"):
        normalized["sender_email"] = sender
    if password and not normalized.get("sender_password"):
        normalized["sender_password"] = password

    if receiver and not normalized.get("recipient_emails"):
        normalized["recipient_emails"] = _ensure_list(receiver)
    elif receivers and not normalized.get("recipient_emails"):
        normalized["recipient_emails"] = _ensure_list(receivers)
    else:
        normalized["recipient_emails"] = _ensure_list(normalized.get("recipient_emails"))

    # 根据配置或端口智能设置 TLS（EmailNotifier 已支持 465 端口的 SMTP_SSL）
    if "use_tls" not in normalized:
        # 587 端口默认启用 STARTTLS，465 端口使用隐式 SSL 不需要 STARTTLS
        normalized["use_tls"] = normalized.get("smtp_port") != 465

    missing = [key for key in ("smtp_server", "smtp_port", "sender_email", "sender_password") if not normalized.get(key)]
    if missing:
        raise ValueError(f"email 配置缺少必要字段: {', '.join(missing)}")
    if not normalized.get("recipient_emails"):
        raise ValueError("至少需要配置一个收件人")

    return normalized


def _ensure_list(value: Any) -> list[str]:
    """把不同类型的收件人配置统一转换为字符串列表。"""
    if not value:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def resolve_interval(config: Dict[str, Any]) -> int:
    """根据配置推导巡检间隔，默认 5 分钟。"""
    monitor_cfg = config.get("monitor") or {}
    interval = monitor_cfg.get("check_interval")
    if isinstance(interval, int) and interval > 0:
        return interval

    minutes = monitor_cfg.get("interval_minutes")
    if isinstance(minutes, (int, float)) and minutes > 0:
        return int(minutes * 60)

    return DEFAULT_INTERVAL_SECONDS


def build_http_session() -> requests.Session:
    """构建带有完整请求头的 Session，模拟真实浏览器行为。"""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
    )
    return session


def check_availability(session: requests.Session, url: str) -> Tuple[str, Dict[str, Any]]:
    """使用 requests + BeautifulSoup 检测页面可用性。"""
    info: Dict[str, Any] = {"url": url}
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        error_msg = str(exc)
        info["error"] = error_msg
        info["reason"] = f"网络请求失败: {error_msg[:100]}"  # 限制长度避免日志过长
        return "unavailable", info

    info["status_code"] = response.status_code
    if response.status_code == 404:
        info["reason"] = "HTTP 404"
        return "unavailable", info

    if response.status_code != 200:
        info["reason"] = f"HTTP {response.status_code}"
        return "unavailable", info

    soup = BeautifulSoup(response.text, "html.parser")
    title = (soup.title.string.strip() if soup.title and soup.title.string else "") or None
    info["page_title"] = title
    if title and "エラー" in title:
        info["reason"] = "标题提示エラー"
        return "unavailable", info

    meta_refresh = soup.find(
        "meta",
        attrs={"http-equiv": lambda value: isinstance(value, str) and value.lower() == "refresh"},
    )
    if meta_refresh:
        info["meta_refresh"] = meta_refresh.get("content")
        info["reason"] = "存在 meta refresh"
        return "unavailable", info

    info.update(_extract_product_info(soup))

    # 必须提取到商品名称才算真正可用
    if not info.get("product_name"):
        info["reason"] = "未提取到商品信息"
        return "unavailable", info

    return "available", info


def _extract_product_info(soup: BeautifulSoup) -> Dict[str, Any]:
    """从页面中提取商品名称与价格等基础信息。"""
    import re

    name = None
    price = None

    # 提取商品名称：优先使用 og:title
    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        name = og_title.get("content").strip()
    if not name and soup.title and soup.title.string:
        name = soup.title.string.strip()

    # 改进的价格提取逻辑
    # 方法1: 尝试从页面文本中正则提取价格（最可靠）
    page_text = soup.get_text()
    price_pattern = re.search(r'(\d{1,3}(?:[,，]\d{3})+|\d+)\s*円', page_text)
    if price_pattern:
        price = price_pattern.group(0).strip()

    # 方法2: 如果正则失败，尝试多个常见的价格选择器
    if not price:
        price_selectors = [
            "meta[property='og:price:amount']",
            "[itemprop=price]",
            ".price-value",
            ".price",
            "[class*='price']"
        ]
        for selector in price_selectors:
            price_node = soup.select_one(selector)
            if price_node:
                # 尝试从 content 属性或文本内容获取
                price = price_node.get("content") or price_node.get_text()
                if price:
                    price = price.strip()
                    # 验证是否包含价格信息
                    if re.search(r'\d', price):
                        break

    return {"product_name": name, "price": price}


def load_state(state_file: Path) -> Dict[str, Any]:
    """读取上次巡检结果，若不存在则返回空字典。"""
    if not state_file.exists():
        return {}
    try:
        with state_file.open("r", encoding="utf-8") as fp:
            return json.load(fp)
    except (json.JSONDecodeError, OSError):
        logging.warning("状态文件损坏，将重新生成: %s", state_file)
        return {}


def save_state(state_file: Path, state: Dict[str, Any]) -> None:
    """将最新巡检结果持久化到磁盘。"""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with state_file.open("w", encoding="utf-8") as fp:
        json.dump(state, fp, ensure_ascii=False, indent=2)


def should_notify(previous_status: str | None, current_status: str) -> bool:
    """仅在状态从不可用切换为可用时触发通知（首次检测不触发）。"""
    if previous_status is None:
        return False  # 首次启动时不发送通知，避免误报
    return previous_status != "available" and current_status == "available"


def now_iso() -> str:
    """生成统一的 ISO8601 时间戳，便于日志与状态追踪。"""
    return datetime.now(timezone.utc).isoformat()


def run_monitor_loop(interval: int, notifier: EmailNotifier | None) -> None:
    """循环执行巡检任务，并在状态恢复时触发通知。"""
    session = build_http_session()
    state = load_state(STATE_FILE)
    logging.info("开始监控 %s，间隔 %s 秒", TARGET_URL, interval)
    if notifier is None:
        logging.info("邮件通知已禁用，仅记录状态变化")

    try:
        while True:
            status, info = check_availability(session, TARGET_URL)
            previous_status = state.get("status")

            state.update(
                {
                    "status": status,
                    "product_name": info.get("product_name"),
                    "price": info.get("price"),
                    "status_code": info.get("status_code"),
                    "last_checked_at": now_iso(),
                    "url": TARGET_URL,
                }
            )

            if status == "available":
                logging.info("页面可用，商品: %s", info.get("product_name") or "未知")
            else:
                logging.info("页面不可用，原因: %s", info.get("reason") or "未知")

            if should_notify(previous_status, status):
                if notifier is None:
                    logging.info("状态恢复可用，但邮件通知已禁用")
                else:
                    logging.info("状态恢复可用，准备发送邮件通知")
                    try:
                        notifier.send_availability_notification(
                            MONITOR_NAME,
                            {
                                "product_name": info.get("product_name"),
                                "price": info.get("price"),
                                "url": TARGET_URL,
                                "status_code": info.get("status_code"),
                            },
                        )
                        state["notified_at"] = now_iso()
                    except Exception as exc:  # noqa: BLE001 - 需要捕获所有异常防止循环终止
                        logging.exception("发送通知失败: %s", exc)

            save_state(STATE_FILE, state)
            time.sleep(interval)
    except KeyboardInterrupt:
        logging.info("收到中断信号，退出监控")


def main() -> None:
    """脚本入口，负责读取配置、初始化通知器并启动循环。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    config = load_project_config()

    # 检查邮件通知是否启用
    email_cfg = config.get("email", {})
    if not email_cfg.get("enabled", True):
        logging.warning("邮件通知已禁用（email.enabled=false），将仅记录状态变化")
        notifier = None
    else:
        email_config = prepare_email_config(email_cfg)
        notifier = EmailNotifier(email_config)

    interval = resolve_interval(config)
    run_monitor_loop(interval, notifier)


if __name__ == "__main__":
    main()
