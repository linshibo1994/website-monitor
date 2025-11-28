"""
监控主程序
负责调度抓取任务、处理数据、发送通知
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.app.config import get_config, config_manager
from backend.app.database import init_db
from backend.app.services.scraper import scrape_products, ScrapeResult, init_last_successful_count
from backend.app.services.storage import storage_service
from backend.app.services.notifier import email_notifier


class MonitorService:
    """监控服务"""

    def __init__(self):
        self.config = get_config()
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.is_running = False
        self.last_check_time: Optional[datetime] = None
        self.last_result: Optional[ScrapeResult] = None

        # 设置日志
        self._setup_logging()

        # 初始化数据库
        init_db()

        # 从数据库初始化历史成功计数（用于数据合理性检查）
        previous_count = storage_service.get_previous_count()
        if previous_count > 0:
            init_last_successful_count(previous_count)
            logger.info(f"从数据库加载上次成功计数: {previous_count}")

    def _setup_logging(self):
        """设置日志"""
        log_config = self.config.logging

        # 移除默认处理器
        logger.remove()

        # 添加控制台输出
        if log_config.console:
            logger.add(
                sys.stdout,
                level=log_config.level,
                format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
            )

        # 添加文件输出
        log_file = Path(__file__).parent.parent.parent.parent / log_config.file
        log_file.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            str(log_file),
            level=log_config.level,
            rotation=f"{log_config.max_size_mb} MB",
            retention=log_config.backup_count,
            encoding="utf-8",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
        )

    async def run_check(self) -> dict:
        """执行一次检测"""
        logger.info("=" * 50)
        logger.info("开始执行商品监控检测")

        try:
            # 获取上次的数量
            previous_count = storage_service.get_previous_count()
            logger.info(f"上次商品数量: {previous_count}")

            # 执行抓取
            result = await scrape_products()
            self.last_result = result
            self.last_check_time = datetime.now()

            if not result.success:
                logger.error(f"抓取失败: {result.error_message}")
                # 保存失败记录
                storage_service.save_failed_result(
                    result.error_message or "未知错误",
                    result.duration_seconds
                )
                # 发送错误通知
                email_notifier.send_error_notification(result.error_message or "抓取失败")
                return {
                    "success": False,
                    "error": result.error_message
                }

            # 检测变化
            added_products, removed_products = storage_service.process_scrape_result(result)

            # 保存结果
            monitor_log = storage_service.save_scrape_result(
                result,
                added_products,
                removed_products
            )

            # 发送通知（如果有变化）
            if added_products or removed_products:
                logger.info(f"检测到变化: 新增={len(added_products)}, 下架={len(removed_products)}")
                email_notifier.send_change_notification(
                    previous_count,
                    result.total_count,
                    added_products,
                    removed_products
                )
            else:
                logger.info("商品数量无变化")

            logger.info(f"检测完成: 当前商品数={result.total_count}, 耗时={result.duration_seconds:.2f}秒")
            logger.info("=" * 50)

            return {
                "success": True,
                "total_count": result.total_count,
                "previous_count": previous_count,
                "added_count": len(added_products),
                "removed_count": len(removed_products),
                "duration": result.duration_seconds,
                "method": result.detection_method
            }

        except Exception as e:
            logger.exception(f"监控检测异常: {e}")
            email_notifier.send_error_notification(str(e))
            return {
                "success": False,
                "error": str(e)
            }

    def start_scheduler(self):
        """启动定时调度器"""
        if self.scheduler is not None:
            logger.warning("调度器已在运行")
            return

        interval_minutes = self.config.monitor.interval_minutes

        # 使用 UTC 时区避免 tzlocal 兼容性问题
        import pytz
        self.scheduler = AsyncIOScheduler(timezone=pytz.UTC)
        self.scheduler.add_job(
            self.run_check,
            trigger=IntervalTrigger(minutes=interval_minutes, timezone=pytz.UTC),
            id='monitor_job',
            name='商品监控任务',
            replace_existing=True
        )

        self.scheduler.start()
        self.is_running = True

        logger.info(f"定时调度器已启动，检测间隔: {interval_minutes} 分钟")

    def stop_scheduler(self):
        """停止定时调度器"""
        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler = None
            self.is_running = False
            logger.info("定时调度器已停止")

    def get_status(self) -> dict:
        """获取监控状态"""
        last_log = storage_service.get_last_monitor_log()

        return {
            "is_running": self.is_running,
            "last_check_time": self.last_check_time.isoformat() if self.last_check_time else None,
            "interval_minutes": self.config.monitor.interval_minutes,
            "last_total_count": last_log.total_count if last_log else 0,
            "last_status": last_log.status if last_log else None
        }


# 创建监控服务单例
monitor_service = MonitorService()


async def run_once():
    """执行一次检测（命令行调用）"""
    result = await monitor_service.run_check()
    return result


async def run_daemon():
    """守护进程模式运行"""
    logger.info("启动监控守护进程...")

    # 先执行一次
    await monitor_service.run_check()

    # 启动定时任务
    monitor_service.start_scheduler()

    # 保持运行
    try:
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止...")
        monitor_service.stop_scheduler()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Arc'teryx 商品监控")
    parser.add_argument("--once", action="store_true", help="只执行一次检测")
    parser.add_argument("--daemon", action="store_true", help="守护进程模式运行")

    args = parser.parse_args()

    if args.once:
        asyncio.run(run_once())
    elif args.daemon:
        asyncio.run(run_daemon())
    else:
        # 默认执行一次
        asyncio.run(run_once())
