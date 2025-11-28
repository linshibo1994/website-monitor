# ===========================================
# Arc'teryx 商品监控系统 - Dockerfile
# 使用微软官方 Playwright 镜像，已预装浏览器
# ===========================================

FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

# 复制依赖文件
COPY backend/requirements.txt .

# 安装 Python 依赖（使用国内镜像源加速，增加超时时间）
RUN pip install --no-cache-dir \
    --timeout=120 \
    --retries=5 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    -r requirements.txt

# 复制后端代码
COPY backend/ ./backend/

# 复制前端构建产物（需要先本地执行 npm run build）
COPY frontend/dist/ ./frontend/dist/

# 复制配置文件
COPY config.yaml ./config.yaml

# 创建数据和日志目录
RUN mkdir -p /app/data /app/logs

# 暴露端口
EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# 启动命令
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
