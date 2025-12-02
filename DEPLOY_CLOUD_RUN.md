# Google Cloud Run 部署指南

## 前提条件

1. 安装 Google Cloud SDK
```bash
# macOS
brew install --cask google-cloud-sdk

# 或从官网下载
# https://cloud.google.com/sdk/docs/install
```

2. 初始化并登录
```bash
gcloud init
gcloud auth login
```

3. 设置项目
```bash
# 查看项目列表
gcloud projects list

# 设置项目 ID
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID
```

## 方式1: 命令行部署（推荐）

```bash
# 1. 进入项目目录
cd /path/to/website-monitor

# 2. 提交代码到 Git（如果还没提交）
git add .
git commit -m "feat: 添加 Cloud Run 部署支持"
git push origin main

# 3. 部署到 Cloud Run
gcloud run deploy arcteryx-monitor \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 1 \
  --timeout 3600 \
  --min-instances 0 \
  --max-instances 1

# 注意：端口会自动适配 Cloud Run 的 PORT 环境变量（8080）
# 本地 Docker 仍使用 7080 端口

# 部署成功后会显示 URL，例如：
# Service URL: https://arcteryx-monitor-xxx-uc.a.run.app
```

## 方式2: 从 GitHub 部署

```bash
# 1. 启用 Cloud Build API
gcloud services enable cloudbuild.googleapis.com

# 2. 从 GitHub 仓库部署
gcloud run deploy arcteryx-monitor \
  --source https://github.com/linshibo1994/website-monitor \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 7080 \
  --memory 2Gi \
  --cpu 1
```

## 方式3: 通过 Cloud Console（网页界面）

1. 访问 https://console.cloud.google.com/run
2. 点击 "CREATE SERVICE"
3. 选择 "Continuously deploy from a repository (source-based)"
4. 连接 GitHub 仓库
5. 配置参数：
   - Port: 7080
   - Memory: 2 GiB
   - CPU: 1
   - Min instances: 0
   - Max instances: 1
   - Authentication: Allow unauthenticated

## 配置邮件通知（可选）

部署后，在 Cloud Run 控制台设置环境变量：

```bash
gcloud run services update arcteryx-monitor \
  --update-env-vars \
    EMAIL_SENDER="your-email@qq.com",\
    EMAIL_PASSWORD="your-app-password",\
    EMAIL_RECEIVER="receiver@example.com"
```

## 查看日志

```bash
# 查看实时日志
gcloud run services logs tail arcteryx-monitor

# 或在控制台查看
# https://console.cloud.google.com/run/detail/us-central1/arcteryx-monitor/logs
```

## 更新服务

```bash
# 重新部署（使用最新代码）
gcloud run deploy arcteryx-monitor --source .
```

## 删除服务

```bash
gcloud run services delete arcteryx-monitor
```

## 费用估算

Cloud Run 免费额度（每月）：
- 2 million requests
- 360,000 GB-seconds of memory
- 180,000 vCPU-seconds of compute time

预估费用：
- 本项目设置为最小实例 0，无流量时不收费
- 有流量时约 $0.00002448/秒 ≈ $2/天（如果一直运行）
- 建议设置预算提醒

## 常见问题

### Q: 部署失败，提示找不到 config.yaml
A: 已修复，现在使用 config.example.yaml 模板，运行时自动创建

### Q: 如何设置定时监控？
A: 使用 Cloud Scheduler 定时调用 API
```bash
gcloud scheduler jobs create http check-inventory \
  --schedule="*/10 * * * *" \
  --uri="https://your-service.run.app/api/inventory/check" \
  --http-method=POST
```

### Q: 如何访问部署的服务？
A: 部署成功后会显示 Service URL，直接用浏览器访问即可

### Q: 数据会丢失吗？
A: Cloud Run 是无状态的，容器重启后数据会丢失。建议：
1. 使用 Cloud SQL 或 Cloud Storage 存储数据
2. 或使用持久化存储卷（beta 功能）
