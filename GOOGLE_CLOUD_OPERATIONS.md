# Google Cloud 运维操作手册

本文档记录了 website-monitor 项目在 Google Cloud Platform 上的部署、运维和故障排查方法。

---

## 目录

- [1. 项目基本信息](#1-项目基本信息)
- [2. SSH 连接方法](#2-ssh-连接方法)
- [3. 防火墙配置](#3-防火墙配置)
- [4. 远程部署步骤](#4-远程部署步骤)
- [5. 常见问题与解决方案](#5-常见问题与解决方案)
- [6. 运维注意事项](#6-运维注意事项)
- [7. 故障排查工具](#7-故障排查工具)

---

## 1. 项目基本信息

### 1.1 服务器配置

| 配置项 | 值 |
|--------|-----|
| **项目 ID** | sunlit-inquiry-480008-u4 |
| **实例名称** | instance-20260115-065606 |
| **区域/可用区** | us-central1-f |
| **机器类型** | e2-medium (2 vCPU, 4 GB 内存) |
| **静态外部 IP** | 34.134.213.196 |
| **内部 IP** | 10.128.0.2 |
| **磁盘容量** | 10 GB |
| **操作系统** | Debian GNU/Linux 12 (bookworm) |

### 1.2 访问地址

| 服务 | 访问地址 |
|------|----------|
| **主网站** | http://34.134.213.196:7080/history |
| **健康检查** | http://34.134.213.196:7080/api/health |

### 1.3 部署路径

- **项目根目录**: `/opt/website/website-monitor/`
- **数据目录**: `/opt/website/website-monitor/data/`
- **日志目录**: `/opt/website/website-monitor/logs/`
- **配置文件**: `/opt/website/website-monitor/config.yaml`

### 1.4 Docker 容器

| 容器名称 | 服务 | 端口 | 重启策略 |
|---------|------|------|---------|
| arcteryx-monitor | 主 Web 服务 | 7080 | unless-stopped |
| arcteryx-scheduler | 定时监控任务 | - | unless-stopped |
| arcteryx-inventory-monitor | 库存监控 | - | unless-stopped |
| rakuten-monitor | 乐天商品监控 | - | unless-stopped |

---

## 2. SSH 连接方法

### 2.1 使用 gcloud CLI 连接（推荐）

#### 基本连接
```bash
# 设置项目（首次使用）
gcloud config set project sunlit-inquiry-480008-u4

# 连接到实例
gcloud compute ssh instance-20260115-065606 --zone=us-central1-f
```

#### 执行单条命令
```bash
gcloud compute ssh instance-20260115-065606 \
  --zone=us-central1-f \
  --command="docker ps"
```

#### 通过 IAP 隧道连接（网络受限时）
```bash
gcloud compute ssh instance-20260115-065606 \
  --zone=us-central1-f \
  --tunnel-through-iap
```

### 2.2 使用传统 SSH 连接

```bash
# 使用静态 IP 连接
ssh -i ~/.ssh/google_compute_engine linshibo1994@34.134.213.196
```

### 2.3 SSH 连接故障排查

```bash
# 运行自动故障排查工具
gcloud compute ssh instance-20260115-065606 \
  --zone=us-central1-f \
  --troubleshoot

# 检查 IAP 隧道问题
gcloud compute ssh instance-20260115-065606 \
  --zone=us-central1-f \
  --troubleshoot \
  --tunnel-through-iap
```

**参考资料**:
- [Google Cloud SSH 连接文档](https://cloud.google.com/compute/docs/instances/ssh)
- [SSH 故障排查](https://docs.cloud.google.com/compute/docs/troubleshooting/troubleshooting-ssh-errors)

---

## 3. 防火墙配置

### 3.1 当前防火墙规则

| 规则名称 | 方向 | 优先级 | 源范围 | 协议/端口 | 说明 |
|---------|------|-------|--------|----------|------|
| allow-website-monitor | INGRESS | 1000 | 0.0.0.0/0 | tcp:7080 | 网站监控服务端口 |
| default-allow-ssh | INGRESS | 65534 | 0.0.0.0/0 | tcp:22 | SSH 连接 |
| default-allow-icmp | INGRESS | 65534 | 0.0.0.0/0 | icmp | PING 诊断 |
| default-allow-internal | INGRESS | 65534 | 10.128.0.0/9 | 所有端口 | VPC 内部通信 |
| default-allow-rdp | INGRESS | 65534 | 0.0.0.0/0 | tcp:3389 | 远程桌面（未使用） |

### 3.2 查看防火墙规则

```bash
# 列出所有防火墙规则
gcloud compute firewall-rules list

# 查看特定规则详情
gcloud compute firewall-rules describe allow-website-monitor
```

### 3.3 创建新的防火墙规则

```bash
# 示例：开放新端口
gcloud compute firewall-rules create allow-custom-port \
  --network=default \
  --allow=tcp:8080 \
  --source-ranges=0.0.0.0/0 \
  --description="自定义端口"
```

### 3.4 防火墙最佳实践

1. **最小权限原则**: 默认阻止所有流量，仅允许必需的流量
2. **限制源 IP**: 避免使用 `0.0.0.0/0`，指定具体 IP 范围
3. **使用标签**: 通过网络标签对实例分组管理
4. **定期审查**: 定期检查并删除不必要的规则

**参考资料**:
- [VPC 防火墙规则](https://cloud.google.com/vpc/docs/firewalls?hl=zh-cn)
- [防火墙最佳实践](https://docs.cloud.google.com/firewall/docs/using-firewalls?hl=zh-cn)

---

## 4. 远程部署步骤

### 4.1 首次部署

#### 步骤 1: 准备本地代码
```bash
# 在本地项目目录
git pull origin main
```

#### 步骤 2: 连接到服务器
```bash
gcloud compute ssh instance-20260115-065606 --zone=us-central1-f
```

#### 步骤 3: 克隆或更新代码
```bash
# 如果首次部署
sudo mkdir -p /opt/website
cd /opt/website
sudo git clone https://github.com/你的用户名/website-monitor.git
sudo chown -R $USER:$USER /opt/website/website-monitor

# 如果已存在项目
cd /opt/website/website-monitor
git pull origin main
```

#### 步骤 4: 配置文件
```bash
# 复制配置示例
cd /opt/website/website-monitor
cp config.example.yaml config.yaml

# 编辑配置文件
nano config.yaml
# 修改邮件配置、通知渠道等
```

#### 步骤 5: 构建并启动服务
```bash
# 构建 Docker 镜像
docker-compose build

# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps
```

#### 步骤 6: 验证部署
```bash
# 检查容器状态
docker ps

# 查看日志
docker-compose logs -f monitor

# 测试健康检查
curl http://localhost:7080/api/health
```

### 4.2 代码更新部署

```bash
# SSH 连接到服务器
gcloud compute ssh instance-20260115-065606 --zone=us-central1-f

# 进入项目目录
cd /opt/website/website-monitor

# 拉取最新代码
git pull origin main

# 重新构建并重启服务
docker-compose down
docker-compose build
docker-compose up -d

# 验证服务状态
docker-compose ps
docker-compose logs -f --tail=50
```

### 4.3 仅重启服务（不更新代码）

```bash
# 重启所有服务
docker-compose restart

# 重启特定服务
docker-compose restart monitor
docker-compose restart rakuten-monitor
```

### 4.4 数据备份

```bash
# 备份数据库和配置
cd /opt/website/website-monitor
sudo tar -czf backup-$(date +%Y%m%d-%H%M%S).tar.gz data/ config.yaml

# 下载备份到本地
gcloud compute scp instance-20260115-065606:/opt/website/website-monitor/backup-*.tar.gz . \
  --zone=us-central1-f
```

---

## 5. 常见问题与解决方案

### 5.1 网络故障：无法访问网站

**问题现象**:
```
curl: (7) Failed to connect to 34.134.213.196 port 7080: Operation timed out
或
curl: (28) Connection timed out
```

**故障原因**:
1. 实例网络接口未正确初始化（metadata server unreachable）
2. 防火墙规则被误删或修改
3. Docker 服务未启动
4. 应用程序崩溃

**排查步骤**:

```bash
# 1. 检查实例状态
gcloud compute instances describe instance-20260115-065606 \
  --zone=us-central1-f \
  --format="value(status)"
# 应该显示 RUNNING

# 2. 测试网络连通性
ping -c 3 34.134.213.196

# 3. 测试 SSH 连接
gcloud compute ssh instance-20260115-065606 --zone=us-central1-f

# 4. 检查防火墙规则
gcloud compute firewall-rules list --filter="name:allow-website-monitor"

# 5. 检查容器状态
docker ps
docker-compose ps
```

**解决方案**:

#### 方案 1: 重启实例（最有效）
```bash
# 停止实例
gcloud compute instances stop instance-20260115-065606 --zone=us-central1-f

# 等待完全停止（约 30 秒）
sleep 30

# 启动实例
gcloud compute instances start instance-20260115-065606 --zone=us-central1-f

# 等待启动完成（约 1 分钟）
sleep 60

# 测试连接
curl http://34.134.213.196:7080/api/health
```

#### 方案 2: 检查并重启 Docker 服务
```bash
# SSH 连接到服务器
gcloud compute ssh instance-20260115-065606 --zone=us-central1-f

# 检查 Docker 状态
sudo systemctl status docker

# 重启 Docker
sudo systemctl restart docker

# 重启应用容器
cd /opt/website/website-monitor
docker-compose up -d
```

#### 方案 3: 检查系统日志
```bash
# 查看实例串行端口输出
gcloud compute instances get-serial-port-output instance-20260115-065606 \
  --zone=us-central1-f \
  --start=-50000 | tail -100

# 查找关键错误
# 常见错误：network is unreachable, metadata server unreachable
```

---

### 5.2 配置文件错误：容器持续重启

**问题现象**:
```bash
$ docker ps
CONTAINER ID   STATUS
abc123         Restarting (1) 5 seconds ago
```

**故障原因**:
1. `config.yaml` 被错误创建为目录而非文件
2. 配置文件格式错误
3. 必需的环境变量缺失

**解决方案**:

```bash
# 检查配置文件类型
cd /opt/website/website-monitor
file config.yaml
# 应该显示: config.yaml: Unicode text, UTF-8 text

# 如果显示为目录
test -d config.yaml && echo "错误：config.yaml 是目录"

# 修复：删除目录并创建正确的文件
sudo rm -rf config.yaml
sudo cp config.example.yaml config.yaml

# 检查配置文件语法
python3 -c "import yaml; yaml.safe_load(open('config.yaml'))"

# 重新创建容器
docker-compose down
docker-compose up -d
```

---

### 5.3 Xvfb Display 端口冲突

**问题现象**:
```
Fatal server error:
(EE) Server is already active for display 99
```

**解决方案**:

已在 docker-compose.yml 中修复，启动时自动清理锁定文件：

```yaml
command: >
  bash -c "
    rm -f /tmp/.X99-lock
    Xvfb :99 -screen 0 1920x1080x24 &
    sleep 2
    python -m backend.scripts.run_inventory_monitor --daemon --interval 5
  "
```

如果仍然出现问题：
```bash
# 手动清理
gcloud compute ssh instance-20260115-065606 --zone=us-central1-f \
  --command="sudo rm -f /tmp/.X99-lock && sudo pkill -9 Xvfb"

# 重启容器
docker-compose restart inventory-monitor
```

---

### 5.4 IP 地址变化

**问题现象**:
- 重启实例后无法通过原 IP 访问
- DNS 解析失败

**故障原因**:
- 使用的是临时（ephemeral）IP，重启后会变化

**解决方案（已完成）**:

静态 IP 已配置为 `34.134.213.196`，重启不会变化。

如需重新配置静态 IP：
```bash
# 创建静态 IP
gcloud compute addresses create website-monitor-ip --region=us-central1

# 查看分配的 IP
gcloud compute addresses describe website-monitor-ip \
  --region=us-central1 \
  --format="value(address)"

# 删除当前 IP 配置
gcloud compute instances delete-access-config instance-20260115-065606 \
  --zone=us-central1-f \
  --access-config-name="External NAT"

# 分配静态 IP
gcloud compute instances add-access-config instance-20260115-065606 \
  --zone=us-central1-f \
  --access-config-name="External NAT" \
  --address=$(gcloud compute addresses describe website-monitor-ip \
    --region=us-central1 --format="value(address)")
```

---

### 5.5 磁盘空间不足

**问题现象**:
```
No space left on device
df: /dev/sda1: 100% Used
```

**排查步骤**:

```bash
# 检查磁盘使用情况
df -h

# 查找大文件
du -h /opt/website/website-monitor/logs | sort -rh | head -10
du -h /var/lib/docker | sort -rh | head -10

# 检查 Docker 占用
docker system df
```

**解决方案**:

```bash
# 清理日志文件
cd /opt/website/website-monitor/logs
sudo find . -name "*.log" -type f -mtime +7 -delete

# 清理 Docker 未使用资源
docker system prune -a --volumes -f

# 如果仍不够，扩容磁盘
gcloud compute disks resize instance-20260115-065606 \
  --size=20GB \
  --zone=us-central1-f

# 扩容后需要在系统内扩展分区
sudo resize2fs /dev/sda1
```

---

### 5.6 容器健康检查失败

**问题现象**:
```bash
$ docker ps
STATUS
Up 5 minutes (unhealthy)
```

**排查步骤**:

```bash
# 查看健康检查日志
docker inspect --format='{{json .State.Health}}' arcteryx-monitor | python3 -m json.tool

# 手动执行健康检查命令
docker exec arcteryx-monitor curl -f http://localhost:7080/api/health

# 查看应用日志
docker logs --tail 50 arcteryx-monitor
```

**解决方案**:

```bash
# 如果应用正常运行但健康检查失败，可能是超时
# 修改 docker-compose.yml 中的健康检查配置
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:7080/api/health"]
  interval: 30s
  timeout: 10s          # 增加超时时间
  retries: 3
  start_period: 60s     # 增加启动等待时间

# 重新创建容器
docker-compose up -d --force-recreate
```

---

## 6. 运维注意事项

### 6.1 重启实例前的检查

在重启实例前，请确认：

1. **数据已备份**
   ```bash
   cd /opt/website/website-monitor
   sudo tar -czf backup-$(date +%Y%m%d).tar.gz data/ config.yaml
   ```

2. **了解当前运行状态**
   ```bash
   docker ps
   docker-compose ps
   ```

3. **通知相关人员**
   - 重启会导致服务短暂不可用（约 2-3 分钟）

4. **选择合适的时间**
   - 避免业务高峰期
   - 建议在凌晨或访问量低谷期

### 6.2 IP 地址变化警告

虽然已配置静态 IP，但在以下操作后需要验证 IP 是否正确：

- 删除并重新创建实例
- 修改网络接口配置
- 删除静态 IP 预留

验证方法：
```bash
gcloud compute instances describe instance-20260115-065606 \
  --zone=us-central1-f \
  --format="value(networkInterfaces[0].accessConfigs[0].natIP)"
```

### 6.3 配置文件管理

**重要提示**:
- `config.yaml` 必须是文件，不能是目录
- 包含敏感信息（邮箱密码、API 密钥）
- 不要提交到 Git 仓库
- 修改后需要重启容器生效

**正确的配置流程**:
```bash
# 1. 备份当前配置
cp config.yaml config.yaml.bak

# 2. 编辑配置
nano config.yaml

# 3. 验证语法
python3 -c "import yaml; yaml.safe_load(open('config.yaml'))"

# 4. 重启相关服务
docker-compose restart
```

### 6.4 Docker 容器管理

**重启策略说明**:
- `unless-stopped`: 除非手动停止，否则始终重启（推荐）
- `always`: 总是重启
- `on-failure`: 仅在失败时重启
- `no`: 不自动重启

**查看重启次数**:
```bash
docker inspect arcteryx-monitor --format='重启次数: {{.RestartCount}}'
```

**如果容器频繁重启**（重启次数 > 10）:
1. 查看日志找到根本原因
2. 修复问题后再重启
3. 避免让容器在错误状态下无限重启

### 6.5 资源监控

**监控磁盘使用**:
```bash
# 设置告警阈值：超过 80% 需要清理
df -h | awk '$5+0 > 80 {print "警告：磁盘使用超过 80%"}'
```

**监控内存使用**:
```bash
free -h
docker stats --no-stream
```

**定期清理**:
```bash
# 每月清理一次旧日志
find /opt/website/website-monitor/logs -name "*.log" -mtime +30 -delete

# 每周清理一次 Docker 缓存
docker system prune -f
```

### 6.6 安全建议

1. **限制 SSH 访问**
   - 考虑配置防火墙规则，仅允许特定 IP 访问 SSH
   ```bash
   gcloud compute firewall-rules update default-allow-ssh \
     --source-ranges=你的IP地址/32
   ```

2. **定期更新系统**
   ```bash
   sudo apt update
   sudo apt upgrade -y
   ```

3. **启用自动备份**
   - 使用 Google Cloud 快照功能
   ```bash
   gcloud compute disks snapshot instance-20260115-065606 \
     --zone=us-central1-f \
     --snapshot-names=website-monitor-snapshot-$(date +%Y%m%d)
   ```

4. **审计日志**
   - 定期检查访问日志和错误日志
   - 查找异常访问模式

---

## 7. 故障排查工具

### 7.1 Google Cloud 工具

```bash
# 查看实例详细信息
gcloud compute instances describe instance-20260115-065606 \
  --zone=us-central1-f

# 查看实例串行端口输出（系统日志）
gcloud compute instances get-serial-port-output instance-20260115-065606 \
  --zone=us-central1-f

# 运行 SSH 连接诊断
gcloud compute ssh instance-20260115-065606 \
  --zone=us-central1-f \
  --troubleshoot

# 查看网络状态
gcloud compute networks describe default
```

### 7.2 服务器诊断命令

```bash
# 网络连接测试
ping -c 3 8.8.8.8                    # 测试外网连接
ping -c 3 169.254.169.254            # 测试 metadata server

# 端口监听检查
sudo netstat -tulpn | grep :7080     # 检查端口是否被监听
sudo lsof -i :7080                   # 查看占用端口的进程

# 防火墙检查（服务器级别）
sudo iptables -L -n -v               # 查看 iptables 规则

# Docker 诊断
docker info                          # Docker 系统信息
docker logs --tail 100 容器名        # 查看容器日志
docker inspect 容器名                # 查看容器详细配置
docker stats                         # 查看容器资源使用
```

### 7.3 日志位置

| 日志类型 | 路径 |
|---------|------|
| 应用日志 | `/opt/website/website-monitor/logs/` |
| Docker 容器日志 | `docker logs 容器名` |
| 系统日志 | `/var/log/syslog` |
| Docker 守护进程日志 | `/var/log/docker.log` |

### 7.4 快速诊断脚本

创建诊断脚本：
```bash
# 在服务器上创建
cat > /opt/website/diagnose.sh << 'EOF'
#!/bin/bash
echo "=== 实例信息 ==="
hostname
uptime

echo -e "\n=== 磁盘使用 ==="
df -h | grep -E 'Filesystem|/dev/sda1'

echo -e "\n=== 内存使用 ==="
free -h

echo -e "\n=== Docker 容器状态 ==="
docker ps -a

echo -e "\n=== 端口监听 ==="
sudo netstat -tulpn | grep -E ':7080|:22'

echo -e "\n=== 网络连接测试 ==="
ping -c 2 8.8.8.8
curl -s -o /dev/null -w "网站访问: HTTP %{http_code}\n" http://localhost:7080/api/health

echo -e "\n=== 最近的应用日志 ==="
docker logs --tail 20 arcteryx-monitor 2>&1
EOF

chmod +x /opt/website/diagnose.sh
```

运行诊断：
```bash
/opt/website/diagnose.sh
```

---

## 8. 参考资料

### 8.1 官方文档

- [Google Cloud SSH 连接](https://cloud.google.com/compute/docs/instances/ssh)
- [SSH 故障排查](https://docs.cloud.google.com/compute/docs/troubleshooting/troubleshooting-ssh-errors)
- [VPC 防火墙规则](https://cloud.google.com/vpc/docs/firewalls?hl=zh-cn)
- [防火墙最佳实践](https://docs.cloud.google.com/firewall/docs/using-firewalls?hl=zh-cn)
- [网络故障排查](https://cloud.google.com/compute/docs/troubleshooting/troubleshooting-networking)
- [Compute Engine FAQ](https://docs.cloud.google.com/compute/docs/faq)

### 8.2 项目相关文档

- 项目 README: `/opt/website/website-monitor/README.md`
- 部署文档: `/opt/website/website-monitor/DEPLOYMENT.md`
- 需求文档: `/opt/website/website-monitor/REQUIREMENTS.md`

---

## 9. 版本历史

| 日期 | 版本 | 变更说明 |
|------|------|---------|
| 2026-02-06 | v1.0 | 初始版本，记录首次网络故障排查经验 |

---

## 10. 联系方式

如有问题，请通过以下方式联系：
- 邮箱: linshibo1994@gmail.com
- GitHub: https://github.com/你的用户名/website-monitor

---

**最后更新**: 2026-02-06
**维护者**: linshibo
