"""乐天商品监控核心逻辑。"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .config import load_config
from .detector import RakutenPageDetector
from .notifier import EmailNotifier

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent  # 项目根目录
STATE_FILE = BASE_DIR / "data" / "rakuten_monitor_state.json"


class RakutenMonitor:
    """负责单次巡检、状态变更判断与通知派发。"""

    def __init__(self, config: Dict[str, Any], state_file: Path | None = None) -> None:
        self.config = config
        self.detector = RakutenPageDetector()
        self.notifier = EmailNotifier(config["email"])
        self.state_file = state_file or STATE_FILE
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.state_file.exists():
            self.state_file.write_text("{}", encoding="utf-8")

    def run_once(self) -> None:
        """执行一次完整巡检流程。"""
        logging.info("开始执行乐天商品监控巡检")
        state = self._load_state()
        updated = False

        for monitor_item in self.config["monitor"]["urls"]:
            url = monitor_item["url"]
            name = monitor_item.get("name", url)
            try:
                result = self.detector.check(url)
            except Exception:  # 捕获所有异常防止任务中断
                logging.exception("检测 URL %s 失败", url)
                continue

            previous = state.get(url, {})
            previous_status = previous.get("status")
            state[url] = {
                "status": result.status,
                "product_name": result.info.get("product_name"),
                "price": result.info.get("price"),
                "checked_at": self._now_iso(),
            }
            updated = True

            logging.info(
                "URL=%s 状态=%s (上一状态=%s)", url, result.status, previous_status or "未知"
            )

            if self._should_notify(previous_status, result.status):
                try:
                    self.notifier.send_availability_notification(name, result.info)
                    state[url]["notified_at"] = self._now_iso()
                except Exception:
                    logging.exception("发送通知失败: %s", url)

        if updated:
            self._save_state(state)

    @staticmethod
    def _should_notify(previous_status: str | None, current_status: str) -> bool:
        """仅在状态由不可用转为可用时触发通知。"""
        return current_status == "available" and previous_status != "available"

    def _load_state(self) -> Dict[str, Any]:
        """读取上一轮巡检状态。"""
        try:
            with self.state_file.open("r", encoding="utf-8") as fp:
                return json.load(fp)
        except json.JSONDecodeError:
            logging.warning("状态文件损坏，重新初始化: %s", self.state_file)
            return {}
        except FileNotFoundError:
            logging.info("状态文件不存在，已创建: %s", self.state_file)
            self.state_file.write_text("{}", encoding="utf-8")
            return {}

    def _save_state(self, state: Dict[str, Any]) -> None:
        """持久化当前监控状态。"""
        with self.state_file.open("w", encoding="utf-8") as fp:
            json.dump(state, fp, ensure_ascii=False, indent=2)

    @staticmethod
    def _now_iso() -> str:
        """统一的时间戳格式，便于追踪。"""
        return datetime.now(timezone.utc).isoformat()


def setup_logging(logging_config: Dict[str, Any]) -> None:
    """根据配置初始化 logging。"""
    level_name = logging_config.get("level", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    log_file = logging_config.get("file", "logs/rakuten_monitor.log")
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handlers = [logging.StreamHandler()]
    try:
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    except OSError:
        logging.warning("无法写入日志文件，将仅输出到控制台: %s", log_path)

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=handlers,
        force=True,
    )


def create_monitor(config_path: str | None = None) -> RakutenMonitor:
    """封装配置加载、日志初始化与监控实例创建。"""
    config = load_config(config_path)
    setup_logging(config.get("logging", {}))
    return RakutenMonitor(config)


if __name__ == "__main__":
    monitor = create_monitor()
    monitor.run_once()
