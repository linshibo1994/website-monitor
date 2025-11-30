# 🏔️ Arc'teryx 商品监控系统

监控 Arc'teryx（始祖鸟）商品库存变化，支持官网单品库存监控和 SCHEELS 经销商商品数量监控。当库存变化（补货/售罄/上架）时自动发送邮件通知。

## 📦 部署方式

| 方式 | 适用场景 | 说明 |
|------|---------|------|
| **Docker 部署**（推荐） | 生产环境、快速部署 | 一键启动，无需配置环境 |
| 本地部署 | 开发调试 | 需要安装 Python 和 Node.js |

## ✨ 功能特性

### 🎯 Arc'teryx 官网库存监控（新功能）

- **单品尺寸级监控**：精确追踪每个尺寸（XS/S/M/L/XL/XXL）的库存状态
- **补货通知**：当目标尺寸从"无货"变为"有货"时发送邮件
- **上架检测**：监测 "Coming Soon" 商品，正式上架时立即通知
- **多商品支持**：可同时监控多个商品，支持指定关注的尺寸
- **智能确认机制**：连续2次检测确认后才发送通知，避免误报

### 📊 SCHEELS 商品数量监控

- **三重检测机制**：确保监控数据准确可靠
  - 主方法：解析页面 "Showing X of Y" 文本
  - 备选方法：统计商品卡片数量
  - 精确方法：商品ID集合对比，识别具体变化
- **实时监控**：每10分钟自动检测（可配置）
- **邮件通知**：商品增加/减少时通过QQ邮箱发送通知

### 🖥️ Web 管理界面

- 仪表盘：实时状态、趋势图表
- 商品列表：浏览、搜索、筛选商品
- 历史记录：查看所有变化记录
- 系统设置：配置监控参数和邮箱

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.10+ / FastAPI / SQLAlchemy |
| 前端 | Vue 3 / Element Plus / ECharts |
| 抓取 | Playwright（无头浏览器） |
| 数据库 | SQLite |
| 邮件 | QQ邮箱 SMTP |

## 📁 项目结构

```
website-monitor/
├── backend/                    # 后端代码
│   ├── app/
│   │   ├── main.py            # FastAPI 应用入口
│   │   ├── config.py          # 配置管理
│   │   ├── database.py        # 数据库连接
│   │   ├── models/            # 数据库模型
│   │   ├── services/          # 业务逻辑
│   │   │   ├── inventory_scraper.py   # Arc'teryx官网库存抓取
│   │   │   ├── inventory_monitor.py   # 库存监控服务
│   │   │   ├── scheels_scraper.py     # SCHEELS网页抓取
│   │   │   ├── scraper.py     # 通用抓取器
│   │   │   ├── storage.py     # 数据存储
│   │   │   ├── notifier.py    # 邮件通知
│   │   │   └── monitor.py     # 监控调度
│   │   ├── routers/           # API 路由
│   │   └── schemas/           # Pydantic 模型
│   └── requirements.txt       # Python 依赖
│
├── frontend/                   # 前端代码
│   ├── src/
│   │   ├── views/             # 页面组件
│   │   ├── router/            # 路由配置
│   │   └── api/               # API 调用
│   ├── package.json
│   └── vite.config.js
│
├── data/                       # 数据目录（自动创建）
│   ├── monitor.db             # SQLite 数据库
│   └── inventory_state.json   # 库存监控状态
├── logs/                       # 日志目录（自动创建）
│
├── config.yaml                 # 配置文件（需手动创建）
├── config.example.yaml         # 配置模板
├── start.sh                    # 启动脚本（本地部署）
├── Dockerfile                  # Docker 镜像构建文件
├── docker-compose.yml          # Docker Compose 配置
├── .dockerignore               # Docker 构建忽略文件
├── REQUIREMENTS.md             # 需求文档
└── README.md                   # 本文件
```

## 🐳 Docker 部署（推荐）

使用 Docker 部署是最简单的方式，无需安装任何依赖环境。

### 前提条件

- 安装 [Docker](https://docs.docker.com/get-docker/)
- 安装 [Docker Compose](https://docs.docker.com/compose/install/)

### 第一步：配置邮箱

```bash
# 复制配置模板
cp config.example.yaml config.yaml

# 编辑配置文件，填入你的邮箱信息
nano config.yaml  # 或使用其他编辑器
```

**重点配置邮箱部分**：
```yaml
email:
  enabled: true
  smtp_server: "smtp.qq.com"
  smtp_port: 465
  sender: "你的QQ号@qq.com"        # 你的QQ邮箱
  password: "你的授权码"            # QQ邮箱授权码（不是QQ密码！）
  receiver: "接收通知的邮箱@xx.com"  # 接收通知的邮箱
```

> 📖 如何获取QQ邮箱授权码？请查看下方「获取QQ邮箱授权码」章节。

### 第二步：构建并启动

```bash
# 构建镜像并启动所有服务
docker compose up -d --build

# 首次构建需要下载 Playwright 镜像（约800MB），请耐心等待
```

### 第三步：验证部署

```bash
# 查看容器运行状态
docker compose ps

# 查看日志
docker compose logs -f

# 检查 API 健康状态
curl http://localhost:8080/api/health
```

### Docker 常用命令

```bash
# 启动服务
docker compose up -d

# 停止服务
docker compose down

# 重启服务
docker compose restart

# 查看实时日志
docker compose logs -f

# 查看特定服务日志
docker compose logs -f monitor           # API 服务日志
docker compose logs -f monitor-scheduler # 调度器日志

# 手动执行一次检测
docker compose exec monitor python -m backend.app.services.monitor --once

# 重新构建镜像（代码更新后）
docker compose up -d --build

# 清理并重建
docker compose down && docker compose up -d --build
```

### Docker 服务说明

| 服务名 | 容器名 | 功能 | 端口 |
|-------|--------|------|------|
| `monitor` | `arcteryx-monitor` | Web API 服务 | 8080 |
| `monitor-scheduler` | `arcteryx-scheduler` | 定时监控任务（每10分钟） | - |

### 数据持久化

Docker 部署会自动挂载以下目录，数据不会因容器重启而丢失：

| 宿主机路径 | 容器路径 | 说明 |
|-----------|---------|------|
| `./data/` | `/app/data/` | SQLite 数据库 |
| `./logs/` | `/app/logs/` | 日志文件 |
| `./config.yaml` | `/app/config.yaml` | 配置文件（只读） |

---

## 🖥️ 本地部署

如果你需要开发调试，可以选择本地部署。

### 环境要求

- **Python**: 3.10 或更高版本
- **Node.js**: 18 或更高版本
- **操作系统**: macOS / Linux / Windows

### 安装步骤

**1. 安装依赖**

```bash
# 进入项目目录
cd /Users/linshibo/GithubProject/website-monitor

# 运行安装命令（安装Python依赖、Playwright浏览器、初始化数据库）
./start.sh install
```

如果 `start.sh` 没有执行权限，先运行：
```bash
chmod +x start.sh
```

**2. 配置文件**

```bash
# 复制配置模板
cp config.example.yaml config.yaml

# 编辑配置文件
nano config.yaml  # 或使用其他编辑器
```

> 📖 如何获取QQ邮箱授权码？请查看下方「获取QQ邮箱授权码」章节。

**3. 测试邮件配置**

```bash
./start.sh test-email
```

**4. 执行一次检测**

```bash
./start.sh check
```

---

## 🔑 获取QQ邮箱授权码

⚠️ **注意**：`config.yaml` 中的 `password` 填的是**授权码**，不是QQ密码！

1. 登录 [QQ邮箱网页版](https://mail.qq.com)
2. 点击左上角 **设置** → **账户**
3. 向下滚动找到 **POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务**
4. 点击 **开启** SMTP服务
5. 按提示用手机发送短信验证
6. 获取**授权码**（16位字母）
7. 将授权码填入 `config.yaml` 的 `password` 字段

---

## 📖 使用方法

### Docker 方式（推荐）

```bash
# 启动服务
docker compose up -d

# 停止服务
docker compose down

# 查看日志
docker compose logs -f

# 手动执行一次检测
docker compose exec monitor python -m backend.app.services.monitor --once

# 访问 API
curl http://localhost:8080/api/health
curl http://localhost:8080/api/products
curl http://localhost:8080/api/history
```

### 命令行方式（本地部署）

```bash
# 查看帮助
./start.sh help

# 安装依赖（首次运行）
./start.sh install

# 执行一次检测
./start.sh check

# 启动守护进程（持续监控，每10分钟检测一次）
./start.sh daemon

# 启动 Web 服务
./start.sh web

# 发送测试邮件
./start.sh test-email
```

### Web 界面方式（本地开发）

1. 启动后端服务：
```bash
./start.sh web
```

2. 安装并启动前端（新开一个终端）：
```bash
cd frontend
npm install
npm run dev
```

3. 打开浏览器访问：http://localhost:5173

### Web 界面功能

| 页面 | 路径 | 功能 |
|------|------|------|
| 仪表盘 | `/` | 查看状态、趋势图、手动触发检测 |
| 商品列表 | `/products` | 浏览所有商品、搜索筛选 |
| 历史记录 | `/history` | 查看检测历史、变化详情 |
| 系统设置 | `/settings` | 修改配置、测试邮件 |

### 🎯 库存监控 API（Arc'teryx 官网）

库存监控服务提供以下 API 接口：

**添加监控商品**
```bash
# 监控所有尺寸
curl -X POST http://localhost:8080/api/inventory/products \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://arcteryx.com/us/en/shop/mens/beta-sl-jacket-9685",
    "name": "Beta SL Jacket"
  }'

# 只监控特定尺寸（如 M 和 L）
curl -X POST http://localhost:8080/api/inventory/products \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://arcteryx.com/us/en/shop/mens/beta-sl-jacket-9685",
    "name": "Beta SL Jacket",
    "target_sizes": ["M", "L"]
  }'
```

**查看监控状态**
```bash
curl http://localhost:8080/api/inventory/status
```

**手动执行一次库存检查**
```bash
curl -X POST http://localhost:8080/api/inventory/check
```

**移除监控商品**
```bash
curl -X DELETE "http://localhost:8080/api/inventory/products?url=https://arcteryx.com/..."
```

**支持的 URL 格式**：
- Arc'teryx 官网: `https://arcteryx.com/us/en/shop/...`
- SCHEELS: `https://www.scheels.com/...`

## ⚙️ 配置说明

`config.yaml` 完整配置项：

```yaml
# 监控配置
monitor:
  url: "https://www.scheels.com/c/all/b/arc'teryx/?redirect=arcteryx"  # 监控URL
  interval_minutes: 10      # 检测间隔（分钟）
  timeout_seconds: 60       # 页面加载超时（秒）
  retry_times: 3            # 失败重试次数
  headless: true            # 是否无头模式（后台运行）

# 邮件配置
email:
  enabled: true             # 是否启用邮件通知
  smtp_server: "smtp.qq.com"
  smtp_port: 465
  sender: "xxx@qq.com"      # 发件人邮箱
  password: "授权码"         # QQ邮箱授权码
  receiver: "xxx@xx.com"    # 收件人邮箱

# 通知设置
notification:
  notify_on_added: true     # 商品新增时通知
  notify_on_removed: true   # 商品下架时通知
  notify_on_error: true     # 程序异常时通知

# Web服务配置
web:
  host: "127.0.0.1"
  port: 8080

# 日志配置
logging:
  level: "INFO"             # DEBUG/INFO/WARNING/ERROR
  file: "logs/monitor.log"
```

## 🔄 设置定时任务（可选）

如果你想让监控程序在后台持续运行，可以使用 cron：

```bash
# 编辑 crontab
crontab -e

# 添加定时任务（每10分钟执行一次）
*/10 * * * * cd /Users/linshibo/GithubProject/website-monitor && /usr/bin/python3 -m backend.app.services.monitor --once >> logs/cron.log 2>&1
```

或者使用守护进程模式：
```bash
# 后台运行（使用 nohup）
nohup ./start.sh daemon > logs/daemon.log 2>&1 &
```

## 📧 邮件通知示例

当检测到商品变化时，你会收到类似这样的邮件：

```
主题：【Arc'teryx 新品上架】+3件商品 | 当前共119件

正文：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Arc'teryx 商品数量变化通知
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ 检测时间：2024-11-26 15:30:00
📊 数量变化：116 → 119 (+3)

🆕 新增商品（3件）
1. Men's Arc'teryx Beta Jacket
   💰 价格：$450.00
   🔗 链接：https://...

2. Women's Arc'teryx Atom Hoody
   💰 价格：$300.00（原价 $350.00）🔥促销
   🔗 链接：https://...
```

## ❓ 常见问题

### Docker 相关

#### Q: Docker 镜像构建很慢怎么办？

首次构建需要下载 Playwright 官方镜像（约800MB），这取决于网络速度。可以使用国内镜像加速：
```bash
# 配置 Docker 镜像加速（修改 Docker Desktop 设置或 /etc/docker/daemon.json）
```

#### Q: Docker 容器无法启动？

```bash
# 查看容器日志排查问题
docker compose logs monitor

# 重新构建镜像
docker compose down && docker compose up -d --build
```

#### Q: 如何查看 Docker 中的数据库？

```bash
# 进入容器
docker compose exec monitor bash

# 查看数据库
sqlite3 /app/data/monitor.db
```

### 本地部署相关

#### Q: 执行检测时报错 "浏览器未安装"
```bash
# 重新安装 Playwright 浏览器
python3 -m playwright install chromium
```

#### Q: 邮件发送失败
1. 检查授权码是否正确（不是QQ密码）
2. 检查 SMTP 服务是否已开启
3. 运行 `./start.sh test-email` 查看详细错误

#### Q: 前端页面无法访问 API
确保后端服务正在运行：
```bash
./start.sh web
```

### 通用问题

#### Q: 如何修改监控频率？
编辑 `config.yaml`：
```yaml
monitor:
  interval_minutes: 5  # 改为5分钟
```
Docker 用户需要重启服务：`docker compose restart`

#### Q: 数据存储在哪里？
- 数据库：`data/monitor.db`（SQLite）
- 日志：`logs/monitor.log`

## 📝 更新日志

### v1.2.0 (2024-11-30)
- 新增 Arc'teryx 官网单品库存监控功能
- 支持按尺寸追踪库存状态（InStock/OutOfStock）
- 新增补货通知和上架通知
- 优化监控稳定性，增加重试机制
- 支持 SCHEELS 和 Arc'teryx 官网双站点监控

### v1.1.0 (2024-11-27)
- 新增 Docker 部署支持
- 优化文档结构

### v1.0.0 (2024-11-26)
- 初始版本
- 实现三重检测机制
- 支持 QQ 邮箱通知
- 提供 Web 管理界面

## 📄 许可证

MIT License

## 👤 作者

**linshibo**

- GitHub: [@linshibo](https://github.com/linshibo)

---

**如有问题，请提交 Issue。**
