#!/bin/bash
# =========================================
# 乐天商品监控 Docker 快速部署脚本
# =========================================

set -e  # 遇到错误立即退出

echo "======================================"
echo "  乐天商品监控 Docker 部署"
echo "======================================"
echo ""

# 检查 Docker 是否运行
if ! docker info > /dev/null 2>&1; then
    echo "❌ 错误: Docker 未运行，请先启动 Docker"
    exit 1
fi

# 检查 config.yaml 是否存在
if [ ! -f "config.yaml" ]; then
    echo "⚠️  警告: config.yaml 不存在"
    if [ -f "config.example.yaml" ]; then
        echo "📝 从 config.example.yaml 创建 config.yaml..."
        cp config.example.yaml config.yaml
        echo "✅ config.yaml 已创建"
        echo ""
        echo "⚠️  请编辑 config.yaml 填入您的邮箱配置："
        echo "   - email.sender: 发件人邮箱"
        echo "   - email.password: QQ 邮箱授权码"
        echo "   - email.receiver: 收件人邮箱"
        echo ""
        read -p "按 Enter 继续（确保已配置邮箱）..."
    else
        echo "❌ 错误: config.example.yaml 也不存在"
        exit 1
    fi
fi

# 创建数据和日志目录
mkdir -p data logs
echo "✅ 数据目录已创建: data/ logs/"
echo ""

# 构建并启动服务
echo "🚀 开始构建 Docker 镜像..."
echo ""
docker compose build rakuten-monitor

echo ""
echo "✅ 镜像构建完成"
echo ""

echo "🚀 启动乐天监控服务..."
echo ""
docker compose up -d rakuten-monitor

echo ""
echo "======================================"
echo "  部署完成！"
echo "======================================"
echo ""

# 等待服务启动
sleep 3

# 检查服务状态
if docker compose ps rakuten-monitor | grep -q "Up"; then
    echo "✅ rakuten-monitor 服务运行中"
    echo ""
    echo "📊 查看实时日志："
    echo "   docker compose logs -f rakuten-monitor"
    echo ""
    echo "📄 查看监控状态："
    echo "   docker compose exec rakuten-monitor cat /app/data/rakuten_state.json"
    echo "   或直接查看: cat data/rakuten_state.json"
    echo ""
    echo "🛑 停止服务："
    echo "   docker compose stop rakuten-monitor"
    echo ""
    echo "详细使用说明请查看: RAKUTEN_MONITOR_DEPLOY.md"
    echo ""
    echo "======================================"
    echo ""

    # 询问是否查看日志
    read -p "是否查看实时日志？(y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker compose logs -f rakuten-monitor
    fi
else
    echo "❌ 服务启动失败，请查看日志："
    echo "   docker compose logs rakuten-monitor"
    exit 1
fi
