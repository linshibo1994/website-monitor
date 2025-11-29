"""
FastAPI 应用主入口
"""
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from loguru import logger

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.config import get_config
from backend.app.database import init_db
from backend.app.routers import products, history, settings, monitor, inventory

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("应用启动中...")
    init_db()
    logger.info("数据库初始化完成")

    yield

    # 关闭时
    logger.info("应用关闭中...")


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
app.include_router(products.router, prefix="/api/products", tags=["商品"])
app.include_router(history.router, prefix="/api/history", tags=["历史记录"])
app.include_router(settings.router, prefix="/api/settings", tags=["设置"])
app.include_router(monitor.router, prefix="/api/monitor", tags=["监控"])
app.include_router(inventory.router, prefix="/api/inventory", tags=["库存监控"])


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
