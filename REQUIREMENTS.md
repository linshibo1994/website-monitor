# SCHEELS Arc'teryx 商品监控系统 - 需求文档

> 版本：v1.0
> 创建日期：2024-11-26
> 状态：待确认

---

## 一、项目概述

### 1.1 项目信息

| 项目 | 内容 |
|------|------|
| **项目名称** | website-monitor |
| **项目路径** | `/Users/linshibo/GithubProject/website-monitor` |
| **目标网站** | https://www.scheels.com/c/all/b/arc'teryx/?redirect=arcteryx |
| **监控对象** | SCHEELS 网站 Arc'teryx（始祖鸟）品牌商品 |
| **当前商品数** | 116 件 |

### 1.2 项目目标

构建一个自动化监控系统，实时追踪 SCHEELS 网站上 Arc'teryx 品牌商品的数量变化，当商品数量发生变化时（增加或减少），通过邮件及时通知用户，并提供 Web 界面查看历史数据和商品详情。

### 1.3 核心价值

- 及时发现新上架商品，抢购热门款式
- 追踪商品下架情况，了解库存动态
- 可视化历史数据，分析商品趋势

---

## 二、功能需求

### 2.1 商品监控功能（核心）

#### 2.1.1 监控参数

| 参数 | 值 |
|------|------|
| 监控频率 | 每 10 分钟检查一次 |
| 监控内容 | 商品总数量、商品详情（名称、价格、ID） |
| 触发条件 | 商品数量增加或减少 |

#### 2.1.2 三重检测机制

为确保监控的可靠性，系统采用三重检测机制：

| 检测方法 | 实现方式 | 作用 | 优先级 |
|---------|---------|------|--------|
| **主方法** | 解析页面 "Showing X of Y" 文本 | 快速获取商品总数 | P0 |
| **备选方法** | 统计页面商品卡片(article)数量 | 主方法失败时的备用方案 | P1 |
| **精确方法** | 商品ID集合对比 | 识别具体新增/下架的商品 | P0 |

**检测逻辑**：
```
1. 首先尝试主方法获取总数
2. 如果主方法失败，使用备选方法（点击Load More加载全部后计数）
3. 无论哪种方法，都执行精确方法获取商品详情
4. 通过商品ID集合对比，精确识别变化的商品
```

#### 2.1.3 商品信息提取

每次监控需提取以下商品信息：

| 字段 | 来源 | 示例 |
|------|------|------|
| 商品ID | URL中的产品编号 | `62355571890` |
| 商品名称 | 商品标题 | `Men's Arc'teryx Atom Hooded Jacket` |
| 价格 | 当前售价 | `$300.00` |
| 原价 | 如有折扣显示原价 | `$400.00` |
| 是否促销 | 是否有Sale标记 | `true/false` |
| 商品链接 | 详情页URL | `https://www.scheels.com/p/62355571890` |

---

### 2.2 邮件通知功能

#### 2.2.1 邮件配置

| 配置项 | 值 |
|--------|------|
| 邮件服务 | QQ邮箱 SMTP |
| SMTP服务器 | smtp.qq.com |
| SMTP端口 | 465 (SSL) |
| 认证方式 | 授权码 |

#### 2.2.2 通知触发条件

| 场景 | 是否通知 | 邮件类型 |
|------|---------|---------|
| 商品数量增加 | ✅ 是 | 新品上架通知 |
| 商品数量减少 | ✅ 是 | 商品下架通知 |
| 商品数量不变 | ❌ 否 | - |
| 监控程序异常 | ✅ 是 | 系统告警通知 |

#### 2.2.3 邮件内容模板

**新品上架通知**：
```
主题：【Arc'teryx 新品上架】+4件商品 | 当前共120件

正文：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Arc'teryx 商品数量变化通知
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ 检测时间：2024-11-26 15:30:00
📊 数量变化：116 → 120 (+4)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🆕 新增商品（4件）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Men's Arc'teryx Beta Jacket
   💰 价格：$450.00
   🔗 链接：https://www.scheels.com/p/xxxxx

2. Women's Arc'teryx Atom Hoody
   💰 价格：$300.00（原价 $350.00）🔥促销
   🔗 链接：https://www.scheels.com/p/xxxxx

...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🌐 查看全部商品：
https://www.scheels.com/c/all/b/arc'teryx/

📊 查看监控面板：
http://localhost:8080

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**商品下架通知**：
```
主题：【Arc'teryx 商品下架】-2件商品 | 当前共114件

正文：
（格式同上，显示下架商品列表）
```

---

### 2.3 Web 管理界面

#### 2.3.1 功能概述

提供一个本地 Web 界面，用于：
- 查看实时监控状态
- 浏览历史数据和趋势图表
- 管理监控配置
- 手动触发检测

#### 2.3.2 页面设计

**页面1：仪表盘（Dashboard）** - 路由：`/`

| 区域 | 内容 |
|------|------|
| 顶部状态栏 | 当前商品总数、最后检测时间、监控状态（运行中/已停止） |
| 数量趋势图 | 最近7天/30天商品数量变化折线图 |
| 最近变化 | 最近10条商品变化记录（新增/下架） |
| 快捷操作 | 手动检测按钮、刷新按钮 |

**页面2：商品列表（Products）** - 路由：`/products`

| 区域 | 内容 |
|------|------|
| 筛选栏 | 按状态筛选（全部/在售/已下架）、按价格排序、搜索 |
| 商品表格 | ID、名称、价格、状态、首次发现时间、最后更新时间 |
| 分页 | 每页20条，支持翻页 |

**页面3：历史记录（History）** - 路由：`/history`

| 区域 | 内容 |
|------|------|
| 时间筛选 | 选择日期范围 |
| 变化记录列表 | 时间、变化类型（+/-）、变化数量、详情链接 |
| 详情弹窗 | 点击查看具体新增/下架的商品列表 |

**页面4：设置（Settings）** - 路由：`/settings`

| 区域 | 内容 |
|------|------|
| 监控配置 | 监控URL、检测频率（分钟） |
| 邮件配置 | SMTP服务器、端口、发件人、授权码、收件人 |
| 通知设置 | 开关：新增通知、下架通知、异常通知 |
| 测试功能 | 发送测试邮件按钮 |

#### 2.3.3 技术选型

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端框架 | FastAPI | 轻量、高性能、自带API文档 |
| 前端框架 | Vue 3 + Vite | 现代化、响应式 |
| UI组件库 | Element Plus | 美观、功能丰富 |
| 图表库 | ECharts | 数据可视化 |
| 数据存储 | SQLite | 轻量级数据库 |

#### 2.3.4 API 接口设计

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/status` | GET | 获取监控状态 |
| `/api/products` | GET | 获取商品列表（支持分页、筛选） |
| `/api/products/{id}` | GET | 获取单个商品详情 |
| `/api/history` | GET | 获取历史变化记录 |
| `/api/history/{id}` | GET | 获取某次变化的详情 |
| `/api/statistics` | GET | 获取统计数据（趋势图用） |
| `/api/settings` | GET/PUT | 获取/更新配置 |
| `/api/monitor/trigger` | POST | 手动触发一次检测 |
| `/api/email/test` | POST | 发送测试邮件 |

---

## 三、非功能需求

### 3.1 性能需求

| 指标 | 要求 |
|------|------|
| 单次检测耗时 | < 60秒 |
| Web页面响应时间 | < 500ms |
| 内存占用 | < 500MB |

### 3.2 可靠性需求

| 场景 | 处理方式 |
|------|---------|
| 网络超时 | 自动重试3次，间隔10秒 |
| 页面结构变化 | 使用备选检测方法 |
| 程序异常 | 记录日志，发送告警邮件 |
| 数据库损坏 | 自动备份，支持恢复 |

### 3.3 日志需求

| 日志级别 | 记录内容 |
|---------|---------|
| INFO | 每次检测开始/结束、数量变化 |
| WARNING | 检测方法降级、重试 |
| ERROR | 异常错误、发送失败 |

---

## 四、技术架构

### 4.1 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        用户层                                │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Web浏览器   │    │   邮件客户端  │    │   定时任务    │  │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘  │
└─────────┼───────────────────┼───────────────────┼───────────┘
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────┐
│                       应用层                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                  FastAPI 后端服务                      │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │  │
│  │  │ API路由  │ │ 监控服务 │ │ 通知服务 │ │ 配置服务 │    │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘    │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                  Vue 3 前端应用                        │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │  │
│  │  │ 仪表盘   │ │ 商品列表 │ │ 历史记录 │ │  设置   │    │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────┐
│                       数据层                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │    SQLite    │    │   日志文件    │    │   配置文件    │  │
│  │  (商品数据)   │    │  (运行日志)   │    │ (config.yaml)│  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                       外部服务                               │
│  ┌──────────────┐    ┌──────────────┐                      │
│  │ SCHEELS网站  │    │ QQ邮箱SMTP   │                      │
│  └──────────────┘    └──────────────┘                      │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 项目目录结构

```
website-monitor/
├── backend/                    # 后端代码
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI 入口
│   │   ├── config.py          # 配置管理
│   │   ├── database.py        # 数据库连接
│   │   ├── models/            # 数据模型
│   │   │   ├── __init__.py
│   │   │   ├── product.py     # 商品模型
│   │   │   └── history.py     # 历史记录模型
│   │   ├── services/          # 业务逻辑
│   │   │   ├── __init__.py
│   │   │   ├── scraper.py     # 网页抓取（三重检测）
│   │   │   ├── monitor.py     # 监控调度
│   │   │   └── notifier.py    # 邮件通知
│   │   ├── routers/           # API路由
│   │   │   ├── __init__.py
│   │   │   ├── products.py
│   │   │   ├── history.py
│   │   │   ├── settings.py
│   │   │   └── monitor.py
│   │   └── schemas/           # Pydantic模型
│   │       ├── __init__.py
│   │       └── schemas.py
│   ├── requirements.txt       # Python依赖
│   └── alembic/               # 数据库迁移
│
├── frontend/                   # 前端代码
│   ├── src/
│   │   ├── main.js
│   │   ├── App.vue
│   │   ├── router/            # 路由配置
│   │   ├── views/             # 页面组件
│   │   │   ├── Dashboard.vue
│   │   │   ├── Products.vue
│   │   │   ├── History.vue
│   │   │   └── Settings.vue
│   │   ├── components/        # 通用组件
│   │   ├── api/               # API调用
│   │   └── assets/            # 静态资源
│   ├── package.json
│   └── vite.config.js
│
├── data/                       # 数据目录
│   ├── monitor.db             # SQLite数据库
│   └── backups/               # 数据备份
│
├── logs/                       # 日志目录
│   └── monitor.log
│
├── config.yaml                 # 配置文件
├── config.example.yaml         # 配置模板
├── docker-compose.yml          # Docker编排（可选）
├── setup_cron.sh              # Cron配置脚本
├── start.sh                   # 启动脚本
├── REQUIREMENTS.md            # 需求文档（本文件）
└── README.md                  # 项目说明
```

### 4.3 数据模型

#### 商品表 (products)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，自增 |
| product_id | VARCHAR(50) | 商品ID（唯一） |
| name | VARCHAR(255) | 商品名称 |
| price | DECIMAL(10,2) | 当前价格 |
| original_price | DECIMAL(10,2) | 原价（可为空） |
| is_on_sale | BOOLEAN | 是否促销 |
| url | VARCHAR(500) | 商品链接 |
| status | VARCHAR(20) | 状态：active/removed |
| first_seen_at | DATETIME | 首次发现时间 |
| last_seen_at | DATETIME | 最后发现时间 |
| removed_at | DATETIME | 下架时间（可为空） |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

#### 监控记录表 (monitor_logs)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，自增 |
| check_time | DATETIME | 检测时间 |
| total_count | INTEGER | 商品总数 |
| previous_count | INTEGER | 上次数量 |
| added_count | INTEGER | 新增数量 |
| removed_count | INTEGER | 下架数量 |
| detection_method | VARCHAR(50) | 检测方法 |
| status | VARCHAR(20) | 状态：success/failed |
| error_message | TEXT | 错误信息（可为空） |
| duration_seconds | FLOAT | 检测耗时 |
| created_at | DATETIME | 创建时间 |

#### 变化详情表 (change_details)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，自增 |
| monitor_log_id | INTEGER | 关联监控记录ID |
| product_id | VARCHAR(50) | 商品ID |
| change_type | VARCHAR(20) | 变化类型：added/removed |
| product_name | VARCHAR(255) | 商品名称 |
| product_price | DECIMAL(10,2) | 商品价格 |
| created_at | DATETIME | 创建时间 |

---

## 五、配置说明

### 5.1 配置文件模板 (config.example.yaml)

```yaml
# ==========================================
# SCHEELS Arc'teryx 商品监控系统配置文件
# ==========================================

# 监控配置
monitor:
  # 目标URL
  url: "https://www.scheels.com/c/all/b/arc'teryx/?redirect=arcteryx"
  # 检测间隔（分钟）
  interval_minutes: 10
  # 请求超时（秒）
  timeout_seconds: 30
  # 失败重试次数
  retry_times: 3
  # 重试间隔（秒）
  retry_interval: 10

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
  password: "your_authorization_code"
  # 收件人邮箱（可以和发件人相同）
  receiver: "your_email@example.com"

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
  host: "127.0.0.1"
  # 端口
  port: 8080
  # 是否开启调试模式
  debug: false

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
```

---

## 六、部署说明

### 6.1 环境要求

| 环境 | 版本要求 |
|------|---------|
| Python | 3.10+ |
| Node.js | 18+ |
| 操作系统 | macOS / Linux / Windows |

### 6.2 快速启动

```bash
# 1. 进入项目目录
cd /Users/linshibo/GithubProject/website-monitor

# 2. 安装后端依赖
cd backend
pip install -r requirements.txt
playwright install chromium

# 3. 安装前端依赖
cd ../frontend
npm install

# 4. 配置
cp config.example.yaml config.yaml
# 编辑 config.yaml，填入QQ邮箱配置

# 5. 初始化数据库
cd ../backend
python -m app.database init

# 6. 启动服务
./start.sh
```

### 6.3 定时任务配置

```bash
# 编辑 crontab
crontab -e

# 添加定时任务（每10分钟执行一次）
*/10 * * * * cd /Users/linshibo/GithubProject/website-monitor && python -m backend.app.services.monitor >> logs/cron.log 2>&1
```

---

## 七、验收标准

### 7.1 功能验收

| 功能点 | 验收标准 |
|--------|---------|
| 商品数量检测 | 能正确获取当前商品总数 |
| 三重检测机制 | 主方法失败时能自动切换备选方法 |
| 商品详情提取 | 能提取商品名称、价格、ID |
| 邮件通知 | 数量变化时能收到邮件 |
| Web仪表盘 | 能显示当前状态和趋势图 |
| Web商品列表 | 能浏览、搜索、筛选商品 |
| Web历史记录 | 能查看历史变化记录 |
| Web设置 | 能修改配置并生效 |

### 7.2 性能验收

| 指标 | 标准 |
|------|------|
| 单次检测时间 | < 60秒 |
| Web页面加载 | < 3秒 |
| 邮件发送延迟 | < 30秒 |

---

## 八、风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| 网站反爬虫 | 无法获取数据 | 使用Playwright模拟真实浏览器，添加随机延迟 |
| 页面结构变化 | 检测失败 | 三重检测机制，失败时告警 |
| QQ邮箱限制 | 发送失败 | 控制发送频率，使用授权码 |
| 数据库损坏 | 数据丢失 | 定期自动备份 |

---

## 九、后续规划（可选）

| 版本 | 功能 |
|------|------|
| v1.1 | 支持监控多个品牌 |
| v1.2 | 价格变化监控与通知 |
| v1.3 | 移动端适配 |
| v2.0 | Docker一键部署 |

---

## 十、附录

### 10.1 QQ邮箱授权码获取方式

1. 登录 QQ邮箱网页版：https://mail.qq.com
2. 点击「设置」→「账户」
3. 找到「POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务」
4. 开启「SMTP服务」
5. 按提示发送短信获取授权码
6. 将授权码填入 config.yaml

### 10.2 参考链接

- 目标网站：https://www.scheels.com/c/all/b/arc'teryx/?redirect=arcteryx
- Playwright文档：https://playwright.dev/python/
- FastAPI文档：https://fastapi.tiangolo.com/
- Vue 3文档：https://vuejs.org/
- Element Plus：https://element-plus.org/

---

**文档状态**：待用户确认后开始开发
