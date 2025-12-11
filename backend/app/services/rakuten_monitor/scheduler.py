"""定时调度器，负责周期性触发监控任务。"""
from __future__ import annotations

import logging
import signal
import threading
import time
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .rakuten_monitor import RakutenMonitor, create_monitor


class MonitorScheduler:
    """包装 APScheduler，提供优雅启动与停止。"""

    def __init__(self, monitor: RakutenMonitor, interval_seconds: int) -> None:
        self.monitor = monitor
        self.interval_seconds = interval_seconds
        self.scheduler = BackgroundScheduler()
        self.job = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """启动调度任务。"""
        if self.job:
            logging.info("调度器已启动，无需重复启动")
            return
        trigger = IntervalTrigger(seconds=self.interval_seconds)
        self.job = self.scheduler.add_job(self._run_job, trigger, max_instances=1, coalesce=True)
        self.scheduler.start()
        logging.info("调度器已启动，检查间隔 %s 秒", self.interval_seconds)

    def _run_job(self) -> None:
        """防御性执行真实任务，避免未捕获异常导致任务终止。"""
        if self._stop_event.is_set():
            return
        try:
            self.monitor.run_once()
        except Exception:
            logging.exception("定时任务执行失败")

    def stop(self) -> None:
        """优雅停止调度器。"""
        if not self.scheduler.running:
            return
        self._stop_event.set()
        self.scheduler.shutdown(wait=False)
        logging.info("调度器已停止")


def main(config_path: Optional[str] = None) -> None:
    """命令行入口，加载配置并启动调度循环。"""
    monitor = create_monitor(config_path)
    interval = monitor.config["monitor"]["check_interval"]
    scheduler = MonitorScheduler(monitor, interval)
    scheduler.start()

    def handle_signal(signum, frame):  # noqa: D401 - APScheduler 需要此钩子
        logging.info("收到信号 %s，准备退出", signum)
        scheduler.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        while scheduler.scheduler.running:
            time.sleep(1)
    finally:
        scheduler.stop()


if __name__ == "__main__":
    main()
