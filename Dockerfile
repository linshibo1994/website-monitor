# ===========================================
# Arc'teryx 商品监控系统 - Dockerfile
# 使用微软官方 Playwright 镜像，已预装浏览器
# 作者：linshibo
# ===========================================

FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

# 镜像元数据
LABEL maintainer="linshibo"
LABEL description="Arc'teryx 商品监控系统"
LABEL version="1.2.0"

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

# 安装 Xvfb（虚拟显示）用于绕过 headless 检测
RUN apt-get update && apt-get install -y \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY backend/requirements.txt .

# 安装 Python 依赖（使用阿里云镜像源加速，增加超时时间）
RUN pip install --no-cache-dir \
    --timeout=120 \
    --retries=5 \
    -i https://mirrors.aliyun.com/pypi/simple \
    --trusted-host mirrors.aliyun.com \
    -r requirements.txt

# 复制后端代码
COPY backend/ ./backend/

# 复制前端构建产物（需要先本地执行 npm run build）
COPY frontend/dist/ ./frontend/dist/

# 复制配置文件模板
COPY config.example.yaml ./config.example.yaml

# 复制库存监控脚本
COPY run_inventory_monitor.py ./run_inventory_monitor.py

# 创建启动脚本
RUN echo '#!/bin/bash\n\
# 如果 config.yaml 不存在，从模板复制\n\
if [ ! -f /app/config.yaml ]; then\n\
    echo "Creating config.yaml from template..."\n\
    cp /app/config.example.yaml /app/config.yaml\n\
fi\n\
\n\
# 启动应用\n\
exec uvicorn backend.app.main:app --host 0.0.0.0 --port 7080\n\
' > /app/start.sh && chmod +x /app/start.sh

# 创建数据和日志目录
RUN mkdir -p /app/data /app/logs

# 暴露端口
EXPOSE 7080

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:7080/api/health || exit 1

# 启动命令
CMD ["/app/start.sh"]
