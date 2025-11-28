"""
配置管理模块
从 config.yaml 加载配置
"""
import os
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field
import yaml
from loguru import logger

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent


@dataclass
class MonitorConfig:
    """监控配置"""
    url: str = "https://www.scheels.com/c/all/b/arc'teryx/?redirect=arcteryx"
    interval_minutes: int = 10
    timeout_seconds: int = 60
    retry_times: int = 3
    retry_interval: int = 10
    headless: bool = True


@dataclass
class EmailConfig:
    """邮件配置"""
    enabled: bool = True
    smtp_server: str = "smtp.qq.com"
    smtp_port: int = 465
    sender: str = ""
    password: str = ""
    receiver: str = ""


@dataclass
class NotificationConfig:
    """通知设置"""
    notify_on_added: bool = True
    notify_on_removed: bool = True
    notify_on_error: bool = True


@dataclass
class WebConfig:
    """Web服务配置"""
    host: str = "127.0.0.1"
    port: int = 8080
    debug: bool = False
    cors_origins: List[str] = field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])


@dataclass
class DatabaseConfig:
    """数据库配置"""
    path: str = "data/monitor.db"
    auto_backup: bool = True
    backup_retention_days: int = 30


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"
    file: str = "logs/monitor.log"
    max_size_mb: int = 10
    backup_count: int = 5
    console: bool = True


@dataclass
class AppConfig:
    """应用总配置"""
    monitor: MonitorConfig = field(default_factory=MonitorConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    notification: NotificationConfig = field(default_factory=NotificationConfig)
    web: WebConfig = field(default_factory=WebConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


class ConfigManager:
    """配置管理器"""

    _instance: Optional['ConfigManager'] = None
    _config: Optional[AppConfig] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config is None:
            self.load_config()

    def load_config(self, config_path: Optional[str] = None) -> AppConfig:
        """加载配置文件"""
        if config_path is None:
            # 默认配置文件路径
            config_path = PROJECT_ROOT / "config.yaml"

        config_path = Path(config_path)

        if not config_path.exists():
            # 如果配置文件不存在，使用默认配置
            logger.warning(f"配置文件不存在: {config_path}，使用默认配置")
            self._config = AppConfig()
            return self._config

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}

            # 解析各部分配置
            monitor_data = data.get('monitor', {})
            email_data = data.get('email', {})
            notification_data = data.get('notification', {})
            web_data = data.get('web', {})
            database_data = data.get('database', {})
            logging_data = data.get('logging', {})

            self._config = AppConfig(
                monitor=MonitorConfig(**monitor_data) if monitor_data else MonitorConfig(),
                email=EmailConfig(**email_data) if email_data else EmailConfig(),
                notification=NotificationConfig(**notification_data) if notification_data else NotificationConfig(),
                web=WebConfig(**web_data) if web_data else WebConfig(),
                database=DatabaseConfig(**database_data) if database_data else DatabaseConfig(),
                logging=LoggingConfig(**logging_data) if logging_data else LoggingConfig(),
            )

            logger.info(f"配置文件加载成功: {config_path}")

        except Exception as e:
            logger.error(f"配置文件加载失败: {e}，使用默认配置")
            self._config = AppConfig()

        return self._config

    def reload(self, config_path: Optional[str] = None):
        """重新加载配置"""
        self._config = None
        return self.load_config(config_path)

    @property
    def config(self) -> AppConfig:
        """获取配置"""
        if self._config is None:
            self.load_config()
        return self._config

    def save_config(self, config_path: Optional[str] = None):
        """保存配置到文件"""
        if config_path is None:
            config_path = PROJECT_ROOT / "config.yaml"

        config_path = Path(config_path)

        data = {
            'monitor': {
                'url': self._config.monitor.url,
                'interval_minutes': self._config.monitor.interval_minutes,
                'timeout_seconds': self._config.monitor.timeout_seconds,
                'retry_times': self._config.monitor.retry_times,
                'retry_interval': self._config.monitor.retry_interval,
                'headless': self._config.monitor.headless,
            },
            'email': {
                'enabled': self._config.email.enabled,
                'smtp_server': self._config.email.smtp_server,
                'smtp_port': self._config.email.smtp_port,
                'sender': self._config.email.sender,
                'password': self._config.email.password,
                'receiver': self._config.email.receiver,
            },
            'notification': {
                'notify_on_added': self._config.notification.notify_on_added,
                'notify_on_removed': self._config.notification.notify_on_removed,
                'notify_on_error': self._config.notification.notify_on_error,
            },
            'web': {
                'host': self._config.web.host,
                'port': self._config.web.port,
                'debug': self._config.web.debug,
                'cors_origins': self._config.web.cors_origins,
            },
            'database': {
                'path': self._config.database.path,
                'auto_backup': self._config.database.auto_backup,
                'backup_retention_days': self._config.database.backup_retention_days,
            },
            'logging': {
                'level': self._config.logging.level,
                'file': self._config.logging.file,
                'max_size_mb': self._config.logging.max_size_mb,
                'backup_count': self._config.logging.backup_count,
                'console': self._config.logging.console,
            },
        }

        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        logger.info(f"配置文件已保存: {config_path}")

    def update_email_config(self, **kwargs):
        """更新邮件配置"""
        for key, value in kwargs.items():
            if hasattr(self._config.email, key):
                setattr(self._config.email, key, value)

    def update_monitor_config(self, **kwargs):
        """更新监控配置"""
        for key, value in kwargs.items():
            if hasattr(self._config.monitor, key):
                setattr(self._config.monitor, key, value)

    def update_notification_config(self, **kwargs):
        """更新通知配置"""
        for key, value in kwargs.items():
            if hasattr(self._config.notification, key):
                setattr(self._config.notification, key, value)


# 全局配置管理器实例
config_manager = ConfigManager()


def get_config() -> AppConfig:
    """获取全局配置"""
    return config_manager.config
