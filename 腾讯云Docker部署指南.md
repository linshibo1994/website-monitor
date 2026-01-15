# 🚀 腾讯云服务器 Docker 部署指南

## 📋 目录
1. [服务器前置条件检查](#1-服务器前置条件检查)
2. [Docker 环境安装](#2-docker-环境安装)
3. [项目部署步骤](#3-项目部署步骤)
4. [服务管理与运维](#4-服务管理与运维)
5. [安全配置建议](#5-安全配置建议)
6. [常见问题排查](#6-常见问题排查)

---

## 1. 服务器前置条件检查

### 1.1 系统要求

**推荐配置**：
- **CPU**：2核及以上
- **内存**：2GB 及以上（推荐 4GB，因为项目使用 Playwright 浏览器）
- **磁盘**：20GB 及以上可用空间
- **操作系统**：
  - Ubuntu 20.04/22.04 LTS（推荐）
  - CentOS 7/8
  - Debian 10/11

### 1.2 检查服务器状态

登录腾讯云服务器后，执行以下命令进行检查：

```bash
# 1. 检查操作系统版本
cat /etc/os-release

# 2. 检查 CPU 核心数
nproc

# 3. 检查内存
free -h

# 4. 检查磁盘空间
df -h

# 5. 检查系统架构（应该是 x86_64 或 aarch64）
uname -m

# 6. 检查网络连通性
ping -c 4 google.com
```

### 1.3 检查是否已安装 Docker

```bash
# 检查 Docker 是否已安装
docker --version

# 检查 Docker Compose 是否已安装
docker compose version

# 检查 Docker 服务状态
systemctl status docker
```

如果以上命令都能正常执行且有输出，说明 Docker 环境已就绪，可以跳到 [第3步：项目部署](#3-项目部署步骤)。

---

## 2. Docker 环境安装

### 2.1 安装 Docker（Ubuntu/Debian）

```bash
# 更新软件包索引
sudo apt-get update

# 安装必要的依赖
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# 添加 Docker 官方 GPG 密钥
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# 设置 Docker APT 仓库
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 更新软件包索引
sudo apt-get update

# 安装 Docker Engine、CLI 和 Containerd
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 启动 Docker 服务
sudo systemctl start docker
sudo systemctl enable docker

# 验证安装
sudo docker run hello-world
```

### 2.2 安装 Docker（CentOS）

```bash
# 卸载旧版本（如果有）
sudo yum remove docker docker-client docker-client-latest docker-common docker-latest docker-latest-logrotate docker-logrotate docker-engine

# 安装必要的依赖
sudo yum install -y yum-utils

# 添加 Docker 仓库
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

# 安装 Docker Engine
sudo yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 启动 Docker 服务
sudo systemctl start docker
sudo systemctl enable docker

# 验证安装
sudo docker run hello-world
```

### 2.3 配置 Docker 镜像加速（重要！）

⚠️ **2025年注意事项**：由于 2024年6月后国内主要镜像源（阿里云、腾讯云、中科大等）已停止公共服务，需要配置替代镜像源。

```bash
# 创建 Docker 配置目录
sudo mkdir -p /etc/docker

# 编辑 daemon.json 配置文件
sudo tee /etc/docker/daemon.json > /dev/null <<EOF
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker-0.unsee.tech",
    "https://docker.m.daocloud.io"
  ],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  },
  "storage-driver": "overlay2"
}
EOF

# 重启 Docker 服务使配置生效
sudo systemctl daemon-reload
sudo systemctl restart docker

# 验证配置
sudo docker info | grep -A 10 "Registry Mirrors"
```

### 2.4 配置 Docker 用户权限（可选但推荐）

```bash
# 将当前用户添加到 docker 组，避免每次都用 sudo
sudo usermod -aG docker $USER

# 刷新用户组（或重新登录）
newgrp docker

# 验证权限
docker ps
```

---

## 3. 项目部署步骤

### 3.1 安装 Git 并克隆项目

```bash
# 安装 Git
sudo apt-get install -y git  # Ubuntu/Debian
# 或
sudo yum install -y git       # CentOS

# 克隆你的项目（替换为你的仓库地址）
cd ~
git clone https://github.com/你的用户名/website-monitor.git
cd website-monitor
```

### 3.2 配置项目

```bash
# 1. 复制配置模板
cp config.example.yaml config.yaml

# 2. 编辑配置文件（推荐使用 nano 或 vim）
nano config.yaml
```

**重点配置邮箱部分**（必须配置）：

```yaml
email:
  enabled: true
  smtp_server: "smtp.qq.com"
  smtp_port: 465
  sender: "你的QQ号@qq.com"          # 替换为你的 QQ 邮箱
  password: "你的QQ邮箱授权码"       # 不是 QQ 密码！是授权码
  receiver: "接收通知的邮箱@xx.com"  # 替换为接收通知的邮箱
```

**端口配置**（确保端口未被占用）：

```yaml
# docker-compose.yml 中的端口映射
ports:
  - "7080:7080"  # 可修改为其他端口，如 8080:7080
```

### 3.3 构建前端（重要！）

⚠️ 由于 Dockerfile 中需要 `frontend/dist/` 目录，需要先在本地构建前端：

**方法1：在本地构建后上传**（推荐）

```bash
# 在你的本地开发机上执行
cd frontend
npm install
npm run build

# 将整个项目（包括 dist 目录）上传到服务器
# 使用 scp 或 git 推送
```

**方法2：在服务器上构建**

```bash
# 在服务器上安装 Node.js（Ubuntu）
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# 构建前端
cd frontend
npm install
npm run build
cd ..
```

### 3.4 启动 Docker 服务

```bash
# 确保在项目根目录
cd ~/website-monitor

# 首次启动：构建镜像并启动所有服务
docker compose up -d --build

# 查看构建进度（首次构建需要下载 Playwright 镜像，约 800MB，需要 5-15 分钟）
docker compose logs -f
```

### 3.5 验证部署

```bash
# 1. 查看容器运行状态（所有容器的 STATUS 应该是 Up）
docker compose ps

# 输出示例：
# NAME                      STATUS    PORTS
# arcteryx-monitor          Up        0.0.0.0:7080->7080/tcp
# arcteryx-scheduler        Up
# arcteryx-inventory-monitor Up
# rakuten-monitor           Up

# 2. 检查 API 健康状态
curl http://localhost:7080/api/health

# 应该返回：{"status":"healthy"}

# 3. 测试 API 接口
curl http://localhost:7080/api/products

# 4. 查看实时日志
docker compose logs -f monitor
```

### 3.6 配置防火墙（重要！）

```bash
# Ubuntu/Debian 使用 ufw
sudo ufw allow 7080/tcp
sudo ufw reload

# CentOS 使用 firewalld
sudo firewall-cmd --permanent --add-port=7080/tcp
sudo firewall-cmd --reload

# 或者在腾讯云控制台配置安全组规则：
# 入站规则 → 添加规则 → TCP:7080 → 来源：0.0.0.0/0（或指定 IP）
```

### 3.7 访问 Web 界面

在浏览器中访问：

```
http://你的服务器公网IP:7080
```

如果无法访问，请检查：
1. 防火墙是否开放 7080 端口
2. 腾讯云安全组是否配置正确
3. Docker 容器是否正常运行

---

## 4. 服务管理与运维

### 4.1 常用 Docker Compose 命令

```bash
# 启动所有服务
docker compose up -d

# 停止所有服务
docker compose down

# 重启所有服务
docker compose restart

# 重启单个服务
docker compose restart monitor

# 查看容器状态
docker compose ps

# 查看实时日志（所有服务）
docker compose logs -f

# 查看特定服务日志
docker compose logs -f monitor           # API 服务
docker compose logs -f monitor-scheduler # 调度器
docker compose logs -f inventory-monitor # 库存监控
docker compose logs -f rakuten-monitor   # 乐天监控

# 查看最近 100 行日志
docker compose logs --tail=100 monitor

# 手动执行一次检测
docker compose exec monitor python -m backend.app.services.monitor --once

# 进入容器内部（调试用）
docker compose exec monitor bash

# 查看容器资源占用
docker stats
```

### 4.2 代码更新流程

```bash
# 1. 停止服务
cd ~/website-monitor
docker compose down

# 2. 拉取最新代码
git pull origin main

# 3. 如果前端有更新，重新构建
cd frontend
npm run build
cd ..

# 4. 重新构建并启动
docker compose up -d --build

# 5. 验证服务状态
docker compose ps
docker compose logs -f
```

### 4.3 数据备份

```bash
# 备份数据库和配置
cd ~/website-monitor
tar -czf backup-$(date +%Y%m%d-%H%M%S).tar.gz data/ logs/ config.yaml

# 下载备份到本地（在你的本地机器上执行）
scp root@你的服务器IP:~/website-monitor/backup-*.tar.gz ./

# 恢复备份
cd ~/website-monitor
tar -xzf backup-20251211-123456.tar.gz
```

### 4.4 日志管理

```bash
# 清理旧日志（防止磁盘占满）
cd ~/website-monitor
find logs/ -name "*.log" -mtime +30 -delete

# 配置日志轮转（可选）
sudo tee /etc/logrotate.d/website-monitor > /dev/null <<EOF
/home/*/website-monitor/logs/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
EOF
```

---

## 5. 安全配置建议

### 5.1 配置反向代理（推荐使用 Nginx）

为了安全和支持 HTTPS，建议配置 Nginx 反向代理：

```bash
# 安装 Nginx
sudo apt-get install -y nginx

# 创建配置文件
sudo nano /etc/nginx/sites-available/website-monitor
```

配置内容：

```nginx
server {
    listen 80;
    server_name 你的域名.com;  # 或使用服务器IP

    # 限制请求大小
    client_max_body_size 10M;

    # API 代理
    location / {
        proxy_pass http://localhost:7080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支持（如果需要）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # 限流配置（防止滥用）
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    limit_req zone=api_limit burst=20 nodelay;
}
```

```bash
# 启用配置
sudo ln -s /etc/nginx/sites-available/website-monitor /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 5.2 配置 HTTPS（可选但推荐）

```bash
# 安装 Certbot
sudo apt-get install -y certbot python3-certbot-nginx

# 获取 SSL 证书（需要有域名）
sudo certbot --nginx -d 你的域名.com

# 自动续期
sudo certbot renew --dry-run
```

### 5.3 其他安全建议

```bash
# 1. 修改 SSH 默认端口（防止暴力破解）
sudo nano /etc/ssh/sshd_config
# 修改 Port 22 为其他端口，如 Port 2222
sudo systemctl restart sshd

# 2. 禁用 root 直接登录
# 在 /etc/ssh/sshd_config 中设置：PermitRootLogin no

# 3. 配置 fail2ban（防止暴力破解）
sudo apt-get install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# 4. 定期更新系统
sudo apt-get update && sudo apt-get upgrade -y
```

---

## 6. 常见问题排查

### 6.1 容器无法启动

```bash
# 查看详细错误日志
docker compose logs monitor

# 常见原因：
# 1. 端口被占用
sudo lsof -i :7080
# 如果被占用，修改 docker-compose.yml 中的端口映射

# 2. 配置文件错误
cat config.yaml
# 检查 YAML 格式是否正确

# 3. 磁盘空间不足
df -h
docker system df  # 查看 Docker 占用空间
docker system prune -a  # 清理无用镜像和容器（谨慎使用）
```

### 6.2 镜像构建失败

```bash
# 原因1：国内网络问题（下载 Playwright 镜像慢）
# 解决：配置 Docker 镜像加速（见 2.3 节）

# 原因2：pip 安装依赖失败
# Dockerfile 已配置阿里云镜像源，如果仍失败可尝试：
# 临时修改 Dockerfile 中的 pip 镜像源为其他源

# 原因3：内存不足
# 解决：升级服务器配置或关闭其他服务释放内存
```

### 6.3 监控服务不发送邮件

```bash
# 1. 检查邮箱配置
docker compose exec monitor cat /app/config.yaml

# 2. 手动测试邮件发送（进入容器）
docker compose exec monitor python -c "
from backend.app.config import settings
from backend.app.services.notifier import Notifier
notifier = Notifier(settings)
notifier.send_email('测试邮件', '这是一封测试邮件')
"

# 3. 常见错误：
# - 授权码错误：确认是 QQ 邮箱授权码，不是 QQ 密码
# - SMTP 端口被封：腾讯云默认封禁 25 端口，需使用 465 或 587
# - 网络问题：检查服务器能否访问 smtp.qq.com
ping smtp.qq.com
```

### 6.4 Playwright 浏览器启动失败

```bash
# 查看 inventory-monitor 容器日志
docker compose logs inventory-monitor

# 常见原因：内存不足
# 解决：增加服务器内存或减少同时运行的浏览器实例
```

### 6.5 无法访问 Web 界面

```bash
# 1. 检查容器是否运行
docker compose ps

# 2. 检查端口监听
sudo netstat -tlnp | grep 7080

# 3. 检查防火墙
sudo ufw status
sudo iptables -L -n | grep 7080

# 4. 检查腾讯云安全组规则
# 登录腾讯云控制台 → 云服务器 → 安全组 → 添加入站规则

# 5. 本地测试
curl http://localhost:7080/api/health
# 如果本地可以访问但外网不行，说明是防火墙/安全组问题
```

---

## 📚 参考资料

- [腾讯云轻量服务器 Docker 安装文档](https://cloud.tencent.com/document/product/1207/45596)
- [2025年9月 Docker 国内镜像加速大全](https://cloud.tencent.com/developer/article/2570065)
- [腾讯云服务器搭建 Docker 指南](https://cloud.tencent.com/document/product/213/46000)
- [12月9日更新 2025 最新 Docker 镜像源](https://cloud.tencent.com/developer/article/2485043)

---

## ✅ 部署检查清单

完成部署后，请确认以下事项：

- [ ] Docker 和 Docker Compose 已正确安装
- [ ] Docker 镜像加速已配置
- [ ] 前端已构建（`frontend/dist/` 目录存在）
- [ ] `config.yaml` 已正确配置邮箱信息
- [ ] 所有容器状态为 `Up`
- [ ] API 健康检查返回正常：`http://服务器IP:7080/api/health`
- [ ] 防火墙/安全组已开放 7080 端口
- [ ] 能在浏览器访问 Web 界面
- [ ] 收到测试邮件通知
- [ ] 日志输出正常，无错误信息

---

## 🆘 获取帮助

如遇到其他问题，可以：
1. 查看项目 README.md 文档
2. 检查 GitHub Issues
3. 查看容器日志排查错误

**祝你部署顺利！** 🎉
