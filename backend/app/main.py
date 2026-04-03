"""
FastAPI 应用主入口
"""
import asyncio
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from loguru import logger

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.config import get_config
from backend.app.database import init_db, get_db_session
from backend.app.routers import products, history, settings, monitor, inventory, auth, tokens, release
from backend.app.services.monitor import monitor_service
from backend.app.services.inventory_monitor import inventory_monitor_service
from backend.app.services.release_monitor import release_monitor_service
from backend.app.services.rakuten_monitor.notifier import EmailNotifier as RakutenEmailNotifier
from backend.scripts.rakuten_monitor_task import (
    TARGET_URL,
    MONITOR_NAME,
    STATE_FILE,
    build_http_session,
    check_availability,
    load_project_config,
    load_state,
    now_iso,
    prepare_email_config,
    resolve_interval,
    save_state,
    should_notify,
)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


def _env_bool(name: str, default: bool) -> bool:
    """读取布尔环境变量"""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    """读取整数环境变量，读取失败时使用默认值"""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value.strip())
        return parsed if parsed > 0 else default
    except ValueError:
        return default


def _build_rakuten_notifier(config: dict) -> Optional[RakutenEmailNotifier]:
    """根据配置构建乐天邮件通知器，失败时降级为仅记录日志"""
    email_cfg = (config or {}).get("email", {})
    if not email_cfg.get("enabled", True):
        logger.info("乐天监控：邮件通知已禁用")
        return None

    try:
        normalized = prepare_email_config(email_cfg)
        return RakutenEmailNotifier(normalized)
    except Exception as e:
        logger.error(f"乐天监控：邮件通知器初始化失败，降级为仅记录日志: {e}")
        return None


async def _run_rakuten_monitor_loop(stop_event: asyncio.Event):
    """
    乐天监控后台循环（单容器内运行）
    使用 requests + BeautifulSoup，内存开销较低。
    """
    config = load_project_config()
    notifier = _build_rakuten_notifier(config)

    configured_interval = resolve_interval(config)
    interval_seconds = _env_int("RAKUTEN_INTERVAL_SECONDS", configured_interval)

    session = build_http_session()
    state = load_state(STATE_FILE)

    logger.info(f"乐天监控后台任务已启动，间隔: {interval_seconds} 秒，URL: {TARGET_URL}")
    if notifier is None:
        logger.info("乐天监控：当前仅记录状态，不发送邮件")

    try:
        while not stop_event.is_set():
            try:
                status, info = await asyncio.to_thread(check_availability, session, TARGET_URL)
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
                    logger.info(f"乐天监控：页面可用，商品: {info.get('product_name') or '未知'}")
                else:
                    logger.info(f"乐天监控：页面不可用，原因: {info.get('reason') or '未知'}")

                if should_notify(previous_status, status):
                    if notifier is None:
                        logger.info("乐天监控：状态恢复可用，但邮件通知已禁用")
                    else:
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
                            logger.info("乐天监控：可用通知发送成功")
                        except Exception as notify_error:
                            logger.exception(f"乐天监控：发送通知失败: {notify_error}")

                save_state(STATE_FILE, state)
            except Exception as loop_error:
                logger.exception(f"乐天监控：本轮检查失败，稍后重试: {loop_error}")

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                continue
    finally:
        session.close()
        logger.info("乐天监控后台任务已停止")


async def _run_release_monitor_loop(stop_event: asyncio.Event):
    """
    上线监控后台循环（单容器内运行）
    周期性执行 release_monitor_service.check_all_products。
    """
    interval_seconds = _env_int("RELEASE_MONITOR_INTERVAL_SECONDS", 300)
    logger.info(f"上线监控后台任务已启动，间隔: {interval_seconds} 秒")

    try:
        while not stop_event.is_set():
            try:
                def _check_all():
                    with get_db_session() as db:
                        return release_monitor_service.check_all_products(db)

                result = await asyncio.to_thread(_check_all)
                logger.info(
                    "上线监控后台任务执行完成: "
                    f"total={result.get('total', 0)}, "
                    f"checked={result.get('checked', 0)}, "
                    f"available={result.get('available', 0)}, "
                    f"notifications_sent={result.get('notifications_sent', 0)}"
                )
            except Exception as loop_error:
                logger.exception(f"上线监控：本轮检查失败，稍后重试: {loop_error}")

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                continue
    finally:
        logger.info("上线监控后台任务已停止")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("应用启动中...")
    init_db()
    logger.info("数据库初始化完成")

    # 记录后台任务句柄，便于优雅退出
    app.state.rakuten_stop_event = None
    app.state.rakuten_task = None
    app.state.release_stop_event = None
    app.state.release_task = None

    # 单容器模式下自动启动两个调度器（可通过环境变量关闭）
    auto_monitor_scheduler = _env_bool("AUTO_START_MONITOR_SCHEDULER", True)
    auto_inventory_scheduler = _env_bool("AUTO_START_INVENTORY_SCHEDULER", True)
    inventory_interval = _env_int("INVENTORY_INTERVAL_MINUTES", 5)

    if auto_monitor_scheduler and not monitor_service.is_running:
        monitor_service.start_scheduler()
        logger.info("启动 monitor 定时任务（单容器模式）")

    if auto_inventory_scheduler and not inventory_monitor_service.is_running:
        inventory_monitor_service.start_scheduler(inventory_interval)
        logger.info(f"启动 inventory 定时任务（单容器模式，间隔 {inventory_interval} 分钟）")

    # 轻量任务：乐天监控内聚到同一容器（可通过环境变量关闭）
    auto_rakuten_monitor = _env_bool("AUTO_START_RAKUTEN_MONITOR", True)
    if auto_rakuten_monitor:
        stop_event = asyncio.Event()
        app.state.rakuten_stop_event = stop_event
        app.state.rakuten_task = asyncio.create_task(_run_rakuten_monitor_loop(stop_event))

    auto_release_monitor = _env_bool("AUTO_START_RELEASE_MONITOR", True)
    if auto_release_monitor:
        stop_event = asyncio.Event()
        app.state.release_stop_event = stop_event
        app.state.release_task = asyncio.create_task(_run_release_monitor_loop(stop_event))

    yield

    # 关闭时
    logger.info("应用关闭中...")

    # 停止乐天后台任务
    rakuten_stop_event = getattr(app.state, "rakuten_stop_event", None)
    rakuten_task = getattr(app.state, "rakuten_task", None)
    if rakuten_stop_event is not None:
        rakuten_stop_event.set()
    if rakuten_task is not None:
        try:
            await asyncio.wait_for(rakuten_task, timeout=20)
        except asyncio.TimeoutError:
            logger.warning("等待乐天后台任务退出超时，继续关闭流程")
        except Exception as e:
            logger.warning(f"关闭乐天后台任务时出现异常: {e}")

    # 停止上线监控后台任务
    release_stop_event = getattr(app.state, "release_stop_event", None)
    release_task = getattr(app.state, "release_task", None)
    if release_stop_event is not None:
        release_stop_event.set()
    if release_task is not None:
        try:
            await asyncio.wait_for(release_task, timeout=20)
        except asyncio.TimeoutError:
            logger.warning("等待上线监控后台任务退出超时，继续关闭流程")
        except Exception as e:
            logger.warning(f"关闭上线监控后台任务时出现异常: {e}")

    # 停止调度器
    if inventory_monitor_service.is_running:
        inventory_monitor_service.stop_scheduler()
    if monitor_service.is_running:
        monitor_service.stop_scheduler()


# 创建 FastAPI 应用
app = FastAPI(
    title="Arc'teryx 商品监控系统",
    description="监控 SCHEELS 网站 Arc'teryx 品牌商品数量变化",
    version="1.0.0",
    lifespan=lifespan
)

# 配置 CORS
config = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.web.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "Arc'teryx Monitor"}


# 注册路由（API 路由必须在静态文件之前）
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(tokens.router, prefix="/api/tokens", tags=["Token管理"])
app.include_router(products.router, prefix="/api/products", tags=["商品"])
app.include_router(history.router, prefix="/api/history", tags=["历史记录"])
app.include_router(settings.router, prefix="/api/settings", tags=["设置"])
app.include_router(monitor.router, prefix="/api/monitor", tags=["监控"])
app.include_router(inventory.router, prefix="/api/inventory", tags=["库存监控"])
app.include_router(release.router, prefix="/api/release", tags=["上线监控"])


# 静态文件服务（前端构建后的文件）
if FRONTEND_DIST.exists():
    # 挂载静态资源目录
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    # SPA 路由：所有非 API 路由返回 index.html
    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """服务 SPA 前端"""
        # 如果请求的是 API 路径，跳过（不应该到达这里）
        if full_path.startswith("api/"):
            return {"error": "Not found"}

        # 返回 index.html
        index_path = FRONTEND_DIST / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"error": "Frontend not built"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.web.host,
        port=config.web.port,
        reload=config.web.debug
    )
