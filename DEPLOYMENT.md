# Arc'teryx 商品监控系统 - 详细部署文档

> 版本：v1.2.0
> 作者：linshibo
> 更新日期：2024-11-30

---

## 目录

1. [系统要求](#1-系统要求)
2. [Docker 部署（推荐）](#2-docker-部署推荐)
3. [本地部署](#3-本地部署)
4. [配置说明](#4-配置说明)
5. [服务管理](#5-服务管理)
6. [故障排除](#6-故障排除)
7. [性能优化](#7-性能优化)

---

## 1. 系统要求

### 1.1 硬件要求

| 配置项 | 最低要求 | 推荐配置 |
|--------|----------|----------|
| CPU | 1 核心 | 2 核心+ |
| 内存 | 1 GB | 2 GB+ |
| 磁盘空间 | 2 GB | 5 GB+ |
| 网络 | 稳定连接 | 稳定连接 |

### 1.2 软件版本要求

#### Docker 部署

| 软件 | 最低版本 | 推荐版本 | 说明 |
|------|----------|----------|------|
| Docker | 20.10.0 | 24.0+ | 容器运行时 |
| Docker Compose | 2.0.0 | 2.20+ | 容器编排工具 |
| 操作系统 | Linux/macOS/Windows | Ubuntu 22.04 LTS | 支持 Docker 的系统 |

#### 本地部署

| 软件 | 最低版本 | 推荐版本 | 说明 |
|------|----------|----------|------|
| Python | 3.10 | 3.11+ | 后端运行环境 |
| Node.js | 18.0 | 20 LTS | 前端构建环境 |
| npm | 8.0 | 10+ | 包管理器 |
| pip | 21.0 | 23+ | Python 包管理 |
| Git | 2.30 | 2.40+ | 版本控制（可选） |

### 1.3 网络要求

| 用途 | 端口 | 协议 | 说明 |
|------|------|------|------|
| Web 服务 | 7080 (Docker) / 8080 (本地) | HTTP | API 和前端界面 |
| SMTP | 465 | SSL/TLS | QQ 邮箱发送邮件 |
| 外部访问 | 443 | HTTPS | 访问 Arc'teryx/SCHEELS 网站 |

---

## 2. Docker 部署（推荐）

### 2.1 前置条件检查

```bash
# 检查 Docker 版本
docker --version
# 期望输出: Docker version 24.x.x 或更高

# 检查 Docker Compose 版本
docker compose version
# 期望输出: Docker Compose version v2.x.x 或更高

# 检查 Docker 服务状态
docker info
# 应该能正常输出 Docker 信息
```

### 2.2 Docker 安装（如未安装）

#### macOS
```bash
# 使用 Homebrew 安装
brew install --cask docker

# 或下载 Docker Desktop
# https://www.docker.com/products/docker-desktop/
```

#### Ubuntu/Debian
```bash
# 更新包索引
sudo apt-get update

# 安装依赖
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# 添加 Docker 官方 GPG 密钥
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# 设置仓库
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装 Docker
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 启动 Docker 并设置开机自启
sudo systemctl start docker
sudo systemctl enable docker

# 将当前用户添加到 docker 组（免 sudo）
sudo usermod -aG docker $USER
# 注意：需要重新登录才能生效
```

#### CentOS/RHEL
```bash
# 安装 yum-utils
sudo yum install -y yum-utils

# 添加 Docker 仓库
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

# 安装 Docker
sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 启动 Docker
sudo systemctl start docker
sudo systemctl enable docker

# 将当前用户添加到 docker 组
sudo usermod -aG docker $USER
```

#### Windows
1. 下载 Docker Desktop: https://www.docker.com/products/docker-desktop/
2. 运行安装程序
3. 启用 WSL 2（如果提示）
4. 重启电脑

### 2.3 部署步骤

#### 步骤 1：克隆项目
```bash
# 克隆仓库
git clone https://github.com/linshibo/website-monitor.git
cd website-monitor

# 或直接下载压缩包解压
```

#### 步骤 2：配置文件
```bash
# 复制配置模板
cp config.example.yaml config.yaml

# 编辑配置文件
nano config.yaml  # 或使用 vim/vi/code 等编辑器
```

**必须配置的项目**：
```yaml
email:
  enabled: true
  smtp_server: "smtp.qq.com"
  smtp_port: 465
  sender: "你的QQ号@qq.com"        # 发件人 QQ 邮箱
  password: "你的授权码"            # 16位授权码（非QQ密码）
  receiver: "接收通知@example.com"  # 收件人邮箱
```

#### 步骤 3：构建前端（首次部署）
```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 构建生产版本
npm run build

# 返回项目根目录
cd ..
```

#### 步骤 4：构建并启动 Docker 服务
```bash
# 构建镜像并启动所有服务（首次需要下载约 1.5GB 镜像）
docker compose up -d --build

# 查看构建日志
docker compose logs -f
```

#### 步骤 5：验证部署
```bash
# 检查容器状态
docker compose ps

# 期望输出类似：
# NAME                      STATUS          PORTS
# arcteryx-monitor          Up (healthy)    0.0.0.0:7080->7080/tcp
# arcteryx-scheduler        Up
# arcteryx-inventory-monitor Up

# 检查 API 健康状态
curl http://localhost:7080/api/health
# 期望输出: {"status":"ok","timestamp":"..."}

# 查看实时日志
docker compose logs -f
```

### 2.4 Docker 服务架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose 服务                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │   arcteryx-      │  │   arcteryx-      │                │
│  │   monitor        │  │   scheduler      │                │
│  │   (Web API)      │  │   (SCHEELS监控)   │                │
│  │   Port: 7080     │  │   每10分钟执行     │                │
│  └────────┬─────────┘  └────────┬─────────┘                │
│           │                      │                          │
│           │    ┌─────────────────┤                          │
│           │    │                 │                          │
│           ▼    ▼                 ▼                          │
│  ┌──────────────────────────────────────┐                  │
│  │        arcteryx-inventory-monitor     │                  │
│  │        (Arc'teryx官网库存监控)         │                  │
│  │        每5分钟执行 + Xvfb虚拟显示       │                  │
│  └──────────────────────────────────────┘                  │
│                                                              │
│  ┌──────────────────────────────────────┐                  │
│  │              共享数据卷                 │                  │
│  │  ./data/  →  /app/data/  (数据库)     │                  │
│  │  ./logs/  →  /app/logs/  (日志)       │                  │
│  │  ./config.yaml → /app/config.yaml     │                  │
│  └──────────────────────────────────────┘                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.5 Docker 镜像详情

| 镜像 | 基础镜像 | 大小 | 说明 |
|------|----------|------|------|
| arcteryx-monitor | mcr.microsoft.com/playwright/python:v1.41.0-jammy | ~1.5GB | 包含 Playwright + Chromium |

**基础镜像组件**：
- Ubuntu 22.04 LTS (Jammy)
- Python 3.10
- Playwright 1.41.0
- Chromium 浏览器（预安装）
- 系统依赖（fonts, libs 等）

---

## 3. 本地部署

### 3.1 Python 环境配置

#### 检查 Python 版本
```bash
python3 --version
# 期望输出: Python 3.10.x 或更高
```

#### 安装 Python（如需要）

**macOS**:
```bash
# 使用 Homebrew
brew install python@3.11

# 或使用 pyenv
brew install pyenv
pyenv install 3.11.0
pyenv global 3.11.0
```

**Ubuntu/Debian**:
```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip
```

#### 创建虚拟环境（推荐）
```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate  # Linux/macOS
# 或
.\venv\Scripts\activate   # Windows
```

### 3.2 Node.js 环境配置

#### 检查 Node.js 版本
```bash
node --version
# 期望输出: v18.x.x 或更高

npm --version
# 期望输出: 8.x.x 或更高
```

#### 安装 Node.js（如需要）

**使用 nvm（推荐）**:
```bash
# 安装 nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# 重新加载 shell
source ~/.bashrc  # 或 ~/.zshrc

# 安装 Node.js LTS
nvm install --lts
nvm use --lts
```

**macOS (Homebrew)**:
```bash
brew install node@20
```

**Ubuntu/Debian**:
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### 3.3 安装步骤

#### 步骤 1：安装后端依赖
```bash
# 进入项目目录
cd /path/to/website-monitor

# 激活虚拟环境（如果使用）
source venv/bin/activate

# 安装 Python 依赖
pip install -r backend/requirements.txt

# 安装 Playwright 浏览器
python -m playwright install chromium
```

#### 步骤 2：安装前端依赖
```bash
cd frontend
npm install
cd ..
```

#### 步骤 3：配置文件
```bash
cp config.example.yaml config.yaml
# 编辑 config.yaml 填入邮箱配置
```

#### 步骤 4：初始化数据库
```bash
mkdir -p data logs
python -c "from backend.app.database import init_db; init_db()"
```

#### 步骤 5：测试运行
```bash
# 测试邮件配置
./start.sh test-email

# 执行一次检测
./start.sh check
```

### 3.4 后端依赖版本详情

| 包名 | 版本 | 用途 |
|------|------|------|
| fastapi | 0.109.0 | Web 框架 |
| uvicorn | 0.27.0 | ASGI 服务器 |
| sqlalchemy | 2.0.25 | ORM 数据库操作 |
| aiosqlite | 0.19.0 | 异步 SQLite |
| playwright | 1.41.0 | 浏览器自动化 |
| aiohttp | 3.9.1 | 异步 HTTP 客户端 |
| pyyaml | 6.0.1 | YAML 配置解析 |
| pydantic | 2.5.3 | 数据验证 |
| pydantic-settings | 2.1.0 | 配置管理 |
| aiosmtplib | 3.0.1 | 异步邮件发送 |
| apscheduler | 3.10.4 | 定时任务调度 |
| loguru | 0.7.2 | 日志管理 |
| httpx | 0.26.0 | HTTP 客户端 |
| pytest | 7.4.4 | 测试框架 |
| pytest-asyncio | 0.23.3 | 异步测试支持 |

### 3.5 前端依赖版本详情

| 包名 | 版本 | 用途 |
|------|------|------|
| vue | ^3.4.0 | 前端框架 |
| vue-router | ^4.2.5 | 路由管理 |
| axios | ^1.6.5 | HTTP 请求 |
| echarts | ^5.4.3 | 图表可视化 |
| element-plus | ^2.5.0 | UI 组件库 |
| @element-plus/icons-vue | ^2.3.1 | 图标库 |
| dayjs | ^1.11.10 | 日期处理 |
| vite | ^5.0.11 | 构建工具 |
| @vitejs/plugin-vue | ^5.0.3 | Vue 插件 |
| sass | ^1.70.0 | CSS 预处理器 |

---

## 4. 配置说明

### 4.1 完整配置文件示例

```yaml
# ==========================================
# Arc'teryx 商品监控系统配置文件
# ==========================================

# 监控配置
monitor:
  # SCHEELS 目标URL
  url: "https://www.scheels.com/c/all/b/arc'teryx/?redirect=arcteryx"
  # 检测间隔（分钟）
  interval_minutes: 10
  # 请求超时（秒）
  timeout_seconds: 60
  # 失败重试次数
  retry_times: 3
  # 重试间隔（秒）
  retry_interval: 10
  # 是否无头模式运行浏览器
  headless: true

# 邮件配置（QQ邮箱）
email:
  # 是否启用邮件通知
  enabled: true
  # SMTP服务器
  smtp_server: "smtp.qq.com"
  # SMTP端口（SSL）
  smtp_port: 465
  # 发件人邮箱
  sender: "your_qq_number@qq.com"
  # QQ邮箱授权码（非QQ密码）
  password: "your_smtp_authorization_code"
  # 收件人邮箱
  receiver: "receiver_email@qq.com"

# 通知设置
notification:
  # 商品增加时通知
  notify_on_added: true
  # 商品减少时通知
  notify_on_removed: true
  # 程序异常时通知
  notify_on_error: true

# Web服务配置
web:
  # 主机地址
  host: "0.0.0.0"      # Docker 中使用 0.0.0.0
  # 端口
  port: 7080           # Docker 端口
  # 是否开启调试模式
  debug: false
  # 允许的跨域来源
  cors_origins:
    - "http://localhost:5173"
    - "http://127.0.0.1:5173"
    - "http://localhost:7080"

# 数据库配置
database:
  # SQLite数据库路径
  path: "data/monitor.db"
  # 自动备份
  auto_backup: true
  # 备份保留天数
  backup_retention_days: 30

# 日志配置
logging:
  # 日志级别：DEBUG/INFO/WARNING/ERROR
  level: "INFO"
  # 日志文件路径
  file: "logs/monitor.log"
  # 单个日志文件最大大小（MB）
  max_size_mb: 10
  # 保留日志文件数量
  backup_count: 5
  # 是否输出到控制台
  console: true
```

### 4.2 环境变量（可选）

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `TZ` | 时区 | `Asia/Shanghai` |
| `DISPLAY` | X11 显示（Docker 中用于 Xvfb） | `:99` |
| `PYTHONDONTWRITEBYTECODE` | 禁止生成 .pyc 文件 | `1` |
| `PYTHONUNBUFFERED` | 禁用输出缓冲 | `1` |

---

## 5. 服务管理

### 5.1 Docker 服务管理

```bash
# 启动所有服务
docker compose up -d

# 停止所有服务
docker compose down

# 重启所有服务
docker compose restart

# 重启单个服务
docker compose restart monitor

# 查看服务状态
docker compose ps

# 查看实时日志（所有服务）
docker compose logs -f

# 查看特定服务日志
docker compose logs -f monitor
docker compose logs -f monitor-scheduler
docker compose logs -f inventory-monitor

# 进入容器调试
docker compose exec monitor bash

# 手动执行 SCHEELS 检测
docker compose exec monitor python -m backend.app.services.monitor --once

# 手动执行 Arc'teryx 库存检测
docker compose exec inventory-monitor python run_inventory_monitor.py --once

# 重新构建镜像
docker compose build --no-cache

# 完全重置（删除容器和网络）
docker compose down -v
docker compose up -d --build
```

### 5.2 本地服务管理

```bash
# 使用启动脚本
./start.sh help          # 查看帮助
./start.sh install       # 安装依赖
./start.sh check         # 执行一次检测
./start.sh daemon        # 启动守护进程
./start.sh web           # 启动 Web 服务
./start.sh test-email    # 发送测试邮件

# 手动启动后端
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload

# 手动启动前端开发服务器
cd frontend
npm run dev
```

### 5.3 定时任务配置（本地部署）

```bash
# 编辑 crontab
crontab -e

# 添加定时任务（每10分钟执行一次 SCHEELS 检测）
*/10 * * * * cd /path/to/website-monitor && /usr/bin/python3 -m backend.app.services.monitor --once >> logs/cron.log 2>&1

# 添加定时任务（每5分钟执行一次 Arc'teryx 库存检测）
*/5 * * * * cd /path/to/website-monitor && /usr/bin/python3 run_inventory_monitor.py --once >> logs/inventory_cron.log 2>&1
```

---

## 6. 故障排除

### 6.1 常见问题

#### Docker 相关

**问题：Docker 镜像构建失败**
```bash
# 清理构建缓存重试
docker compose build --no-cache

# 检查网络连接
ping mcr.microsoft.com

# 使用镜像加速（中国大陆）
# 编辑 /etc/docker/daemon.json 添加：
# {"registry-mirrors": ["https://docker.mirrors.ustc.edu.cn"]}
```

**问题：容器启动后立即退出**
```bash
# 查看容器日志
docker compose logs monitor

# 检查配置文件是否正确
cat config.yaml

# 检查数据目录权限
ls -la data/ logs/
```

**问题：无法访问 Web 界面**
```bash
# 检查端口是否被占用
lsof -i :7080
# 或
netstat -tlnp | grep 7080

# 检查防火墙设置
sudo ufw status
sudo ufw allow 7080
```

#### 本地部署相关

**问题：Playwright 浏览器安装失败**
```bash
# 重新安装
python -m playwright install chromium --with-deps

# 检查系统依赖（Ubuntu）
sudo apt-get install -y libgtk-3-0 libgbm1 libnss3 libxss1
```

**问题：邮件发送失败**
1. 确认使用的是授权码而非 QQ 密码
2. 确认 SMTP 服务已开启
3. 检查网络是否能访问 smtp.qq.com:465
4. 运行测试命令：`./start.sh test-email`

**问题：数据库损坏**
```bash
# 备份当前数据库
cp data/monitor.db data/monitor.db.bak

# 删除并重建
rm data/monitor.db
python -c "from backend.app.database import init_db; init_db()"
```

### 6.2 日志分析

```bash
# Docker 环境查看日志
docker compose logs --tail=100 monitor

# 本地环境查看日志
tail -f logs/monitor.log

# 搜索错误信息
grep -i error logs/monitor.log

# 查看最近的检测记录
grep "检测完成" logs/monitor.log | tail -10
```

---

## 7. 性能优化

### 7.1 Docker 优化

```yaml
# docker-compose.yml 中添加资源限制
services:
  monitor:
    # ... 其他配置 ...
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

### 7.2 监控频率调整

根据需求调整检测间隔：
- 高频监控（热门商品）：5 分钟
- 常规监控：10 分钟
- 低频监控：30 分钟

```yaml
# config.yaml
monitor:
  interval_minutes: 5  # 根据需要调整
```

### 7.3 数据库优化

```bash
# 定期清理旧数据（保留最近30天）
sqlite3 data/monitor.db "DELETE FROM monitor_logs WHERE created_at < datetime('now', '-30 days');"

# 优化数据库
sqlite3 data/monitor.db "VACUUM;"
```

---

## 附录

### A. 端口说明

| 端口 | 服务 | 用途 |
|------|------|------|
| 7080 | Docker Web API | Docker 部署的 API 端口 |
| 8080 | 本地 Web API | 本地部署的 API 端口 |
| 5173 | Vite Dev Server | 前端开发服务器 |

### B. 文件目录说明

```
website-monitor/
├── backend/              # 后端 Python 代码
├── frontend/             # 前端 Vue 代码
├── data/                 # 数据目录（自动创建）
│   ├── monitor.db        # SQLite 数据库
│   └── inventory_state.json  # 库存监控状态
├── logs/                 # 日志目录（自动创建）
│   └── monitor.log       # 应用日志
├── config.yaml           # 配置文件（需手动创建）
├── config.example.yaml   # 配置模板
├── docker-compose.yml    # Docker Compose 配置
├── Dockerfile            # Docker 镜像配置
├── start.sh              # 本地启动脚本
├── README.md             # 项目说明
├── DEPLOYMENT.md         # 本文件
└── REQUIREMENTS.md       # 需求文档
```

### C. 获取 QQ 邮箱授权码

1. 登录 QQ 邮箱网页版：https://mail.qq.com
2. 点击「设置」→「账户」
3. 找到「POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务」
4. 开启「SMTP服务」
5. 按提示发送短信获取授权码（16位字母）
6. 将授权码填入 `config.yaml` 的 `password` 字段

---

**文档维护**：linshibo

**最后更新**：2024-11-30
