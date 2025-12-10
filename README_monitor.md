# 乐天商品监控模块

本模块在不影响原有业务的前提下，额外提供一个独立的乐天商品库存监控方案，专门监控 `https://item.rakuten.co.jp/auc-refalt/531-09893/` 等商品。当页面从 404/错误状态恢复为正常页面时，系统会立即发送邮件提醒。

## 功能特性
- requests + BeautifulSoup 检测页面状态码、标题与 meta refresh 标签
- APScheduler 定时巡检，可按秒级配置检查频率
- smtplib HTML 邮件通知，包含商品名称、参考价格与链接
- YAML 配置 + 环境变量覆盖敏感字段
- JSON 状态持久化、日志文件留痕，便于审计

## 安装步骤
1. 进入项目根目录
2. 安装依赖
   ```bash
   pip install -r requirements-monitor.txt
   ```
3. 复制示例配置
   ```bash
   cp config.yaml.example config.yaml
   ```
4. 根据实际邮箱与监控需求修改 `config.yaml`

## 配置说明
`config.yaml`（或任何通过 `MONITOR_CONFIG_PATH` 指定的文件）包含下列节：
- `monitor.urls`：待监控的商品列表，`name` 仅用于邮件展示
- `monitor.check_interval`：检查间隔，单位秒
- `email.*`：SMTP 参数与收件人列表，建议通过环境变量提供账户与密码
- `logging.*`：日志级别与输出文件，默认写入 `monitor/logs/monitor.log`

## 环境变量
| 变量名 | 作用 |
| --- | --- |
| `MONITOR_CONFIG_PATH` | 指定自定义配置文件路径 |
| `MONITOR_SENDER_EMAIL` | 覆盖 `email.sender_email` |
| `MONITOR_SENDER_PASSWORD` | 覆盖 `email.sender_password` |
| `MONITOR_RECIPIENTS` | 逗号分隔的收件人列表 |

## 运行方式
### 单次巡检
```bash
python -m monitor.rakuten_monitor
```

### 常驻定时任务
```bash
python -m monitor.scheduler
```
上述命令会按配置的 `check_interval` 周期性执行，支持 Ctrl+C/信号优雅退出。

## 状态与日志
- 状态文件：`monitor/data/monitor_state.json`，记录最近状态与通知时间
- 日志文件：`monitor/logs/monitor.log`，包含检测信息与错误

## 常见问题
1. **邮件发送失败**：确认 SMTP 端口、TLS 选项与授权码，必要时开启“应用专用密码”。
2. **无法写入日志**：检查 `monitor/logs` 权限，或在配置中指向其他可写目录。
3. **需要监控多条 URL**：在 `monitor.urls` 中新增条目即可，系统会自动分别记录状态与通知。
