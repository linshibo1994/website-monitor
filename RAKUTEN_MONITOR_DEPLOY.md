# 乐天商品监控 Docker 部署指南

## 功能说明

本监控服务用于检测乐天（Rakuten）商品页面是否从 404/错误状态恢复可用，当商品重新上架时会自动发送邮件通知。

- **目标 URL**: https://item.rakuten.co.jp/auc-refalt/531-09893/
- **检测逻辑**:
  - HTTP 404 或标题包含"エラー"或存在 meta refresh → 不可用
  - HTTP 200 且无错误特征 → 可用
- **通知触发**: 仅在从"不可用"变为"可用"时发送邮件
- **检查间隔**: 默认 5 分钟（可通过 `config.yaml` 配置）

---

## 部署步骤

### 1. 确保 config.yaml 已配置

监控脚本会复用项目的 `config.yaml` 中的邮件配置：

```yaml
email:
  smtp_server: "smtp.qq.com"
  smtp_port: 465
  sender: "your_email@qq.com"         # 发件人邮箱
  password: "your_qq_auth_code"       # QQ 邮箱授权码
  receiver: "receiver@example.com"    # 收件人邮箱
  enabled: true                       # 可选：设为 false 禁用邮件通知
```

**字段说明**：
- `sender` → 自动映射为 `sender_email`
- `password` → 自动映射为 `sender_password`
- `receiver` → 自动映射为 `recipient_emails`（支持逗号分隔多个）
- 465 端口会自动使用隐式 SSL 连接

### 2. 构建并启动 Docker 容器

```bash
# 构建并启动所有服务（包括新的 rakuten-monitor）
docker compose up -d --build

# 仅启动乐天监控服务
docker compose up -d --build rakuten-monitor
```

### 3. 查看运行状态

```bash
# 查看所有服务状态
docker compose ps

# 查看乐天监控日志（实时）
docker compose logs -f rakuten-monitor

# 查看最近100行日志
docker compose logs --tail=100 rakuten-monitor
```

### 4. 查看监控状态

```bash
# 查看当前监控状态（JSON 格式）
docker compose exec rakuten-monitor cat /app/data/rakuten_state.json

# 或直接在宿主机查看
cat data/rakuten_state.json
```

**状态文件示例**：
```json
{
  "status": "unavailable",
  "product_name": null,
  "price": null,
  "status_code": 404,
  "last_checked_at": "2025-12-04T07:30:00.123456+00:00",
  "url": "https://item.rakuten.co.jp/auc-refalt/531-09893/"
}
```

---

## 高级配置

### 通过环境变量覆盖邮件配置

如果不想在 `config.yaml` 中存储敏感信息，可以通过环境变量覆盖：

编辑 `docker-compose.yml` 的 `rakuten-monitor` 服务：

```yaml
rakuten-monitor:
  environment:
    - TZ=Asia/Shanghai
    - MONITOR_SENDER_EMAIL=your_email@qq.com
    - MONITOR_SENDER_PASSWORD=your_qq_auth_code
    - MONITOR_RECIPIENTS=receiver1@example.com,receiver2@example.com
```

然后重启服务：

```bash
docker compose up -d --force-recreate rakuten-monitor
```

### 调整检查间隔

编辑 `config.yaml`：

```yaml
monitor:
  check_interval: 300  # 秒，默认 5 分钟（300 秒）
  # 或者使用
  interval_minutes: 5  # 分钟
```

然后重启服务：

```bash
docker compose restart rakuten-monitor
```

### 禁用邮件通知（仅记录状态）

```yaml
email:
  enabled: false  # 禁用邮件，仅记录状态到日志和 JSON 文件
```

---

## 故障排查

### 1. 容器无法启动

```bash
# 查看详细错误日志
docker compose logs rakuten-monitor

# 常见问题：
# - config.yaml 不存在 → 从 config.example.yaml 复制一份
# - 邮件配置缺失 → 检查 email 配置是否完整
```

### 2. 邮件发送失败

```bash
# 查看日志中的错误信息
docker compose logs rakuten-monitor | grep "邮件发送失败"

# 常见原因：
# - QQ 邮箱授权码错误 → 重新生成授权码
# - SMTP 端口被防火墙阻止 → 检查网络连接
# - 收件人地址格式错误 → 检查 receiver 配置
```

### 3. 首次启动就收到通知

这是正常行为已修复。代码现在会检查 `previous_status` 是否为 `None`（首次启动），首次检测不会触发通知。

### 4. 查看 Python 依赖是否正确安装

```bash
docker compose exec rakuten-monitor pip list | grep -E "requests|beautifulsoup4|PyYAML"
```

---

## 停止和删除服务

```bash
# 停止服务（保留数据）
docker compose stop rakuten-monitor

# 删除服务（不删除数据卷）
docker compose rm -f rakuten-monitor

# 完全删除（包括数据卷）
docker compose down -v
```

---

## 数据持久化

以下目录会挂载到宿主机，数据不会因容器重启而丢失：

- `./data/rakuten_state.json` - 监控状态持久化
- `./logs/` - 日志文件（如果配置了日志输出）
- `./config.yaml` - 配置文件

---

## 与其他监控服务的关系

项目中有三个独立的监控服务：

1. **monitor** - Arc'teryx 主监控服务（Web UI + API）
2. **inventory-monitor** - Arc'teryx 库存监控（使用 Playwright）
3. **rakuten-monitor** - 乐天商品监控（使用 requests + BeautifulSoup）

它们相互独立，可以单独启动/停止，共享 `config.yaml` 和 `data/` 目录。

---

## 安全建议

1. **不要将 config.yaml 提交到 Git**
   ```bash
   # 确保 .gitignore 包含
   config.yaml
   ```

2. **使用环境变量存储密码**（推荐）
   - 通过 Docker Compose 的 `environment` 注入
   - 或使用 `.env` 文件（也要加入 `.gitignore`）

3. **定期更换邮箱授权码**

---

## 技术细节

- **语言**: Python 3.10+
- **依赖**: requests, beautifulsoup4, PyYAML, APScheduler
- **基础镜像**: `mcr.microsoft.com/playwright/python:v1.41.0-jammy`
- **重启策略**: `unless-stopped`（异常退出会自动重启）
- **时区**: Asia/Shanghai

---

## 联系与反馈

如有问题或建议，请提 Issue 或联系维护者。
