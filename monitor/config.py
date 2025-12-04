"""配置加载与验证模块。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml


class ConfigError(Exception):
    """配置文件错误时抛出的异常。"""


def load_config(config_path: str | None = None) -> Dict[str, Any]:
    """加载监控配置并应用环境变量覆盖。"""
    resolved_path = _resolve_config_path(config_path)
    if not resolved_path.exists():
        raise ConfigError(f"配置文件不存在: {resolved_path}")

    with resolved_path.open("r", encoding="utf-8") as fp:
        config: Dict[str, Any] = yaml.safe_load(fp) or {}

    _apply_env_overrides(config)
    _validate_config(config)
    return config


def _resolve_config_path(config_path: str | None) -> Path:
    """解析配置路径，优先使用函数参数，其次检查环境变量。"""
    env_path = os.getenv("MONITOR_CONFIG_PATH")
    if config_path:
        return Path(config_path).expanduser().resolve()
    if env_path:
        return Path(env_path).expanduser().resolve()
    # 默认读取项目根目录下的 config.yaml
    return Path("config.yaml").resolve()


def _apply_env_overrides(config: Dict[str, Any]) -> None:
    """使用环境变量覆盖敏感信息，防止直接写入配置文件。"""
    email_cfg = config.setdefault("email", {})
    sender_email = os.getenv("MONITOR_SENDER_EMAIL")
    sender_pwd = os.getenv("MONITOR_SENDER_PASSWORD")
    recipients = os.getenv("MONITOR_RECIPIENTS")

    if sender_email:
        email_cfg["sender_email"] = sender_email
    if sender_pwd:
        email_cfg["sender_password"] = sender_pwd
    if recipients:
        email_cfg["recipient_emails"] = [addr.strip() for addr in recipients.split(",") if addr.strip()]


def _validate_config(config: Dict[str, Any]) -> None:
    """校验配置结构与必填字段。"""
    monitor_cfg = config.get("monitor")
    if not monitor_cfg:
        raise ConfigError("monitor 配置节缺失")

    urls = monitor_cfg.get("urls", [])
    if not urls:
        raise ConfigError("monitor.urls 不能为空")

    for item in urls:
        if "url" not in item:
            raise ConfigError("监控目标缺少 url 字段")
        item.setdefault("name", item["url"])

    interval = monitor_cfg.get("check_interval", 300)
    if not isinstance(interval, int) or interval <= 0:
        raise ConfigError("monitor.check_interval 必须为正整数秒数")

    email_cfg = config.get("email")
    if not email_cfg:
        raise ConfigError("email 配置节缺失")

    required = ["smtp_server", "smtp_port", "sender_email", "sender_password", "recipient_emails"]
    for key in required:
        if not email_cfg.get(key):
            raise ConfigError(f"email.{key} 不能为空，请完善配置或通过环境变量提供")

    if not isinstance(email_cfg.get("recipient_emails", []), list):
        raise ConfigError("email.recipient_emails 必须为列表")

    logging_cfg = config.setdefault("logging", {})
    logging_cfg.setdefault("level", "INFO")
    logging_cfg.setdefault("file", "monitor/logs/monitor.log")


__all__ = ["load_config", "ConfigError"]
