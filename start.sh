#!/bin/bash
# SCHEELS Arc'teryx 商品监控系统 - 启动脚本

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查 Python 环境
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        print_error "Python 未安装，请先安装 Python 3.10+"
        exit 1
    fi

    PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    print_info "Python 版本: $PYTHON_VERSION"
}

# 检查配置文件
check_config() {
    if [ ! -f "config.yaml" ]; then
        print_warning "配置文件不存在，从模板创建..."
        cp config.example.yaml config.yaml
        print_warning "请编辑 config.yaml 填入你的 QQ 邮箱配置"
        exit 1
    fi
    print_info "配置文件已就绪"
}

# 安装依赖
install_deps() {
    print_info "安装 Python 依赖..."
    cd backend
    pip install -r requirements.txt -q
    cd ..
    print_success "依赖安装完成"
}

# 安装 Playwright 浏览器
install_browser() {
    print_info "安装 Playwright 浏览器..."
    $PYTHON_CMD -m playwright install chromium
    print_success "浏览器安装完成"
}

# 初始化数据库
init_database() {
    print_info "初始化数据库..."
    mkdir -p data logs
    $PYTHON_CMD -c "from backend.app.database import init_db; init_db()"
    print_success "数据库初始化完成"
}

# 执行一次检测
run_once() {
    print_info "执行一次检测..."
    $PYTHON_CMD -m backend.app.services.monitor --once
}

# 启动监控守护进程
run_daemon() {
    print_info "启动监控守护进程..."
    $PYTHON_CMD -m backend.app.services.monitor --daemon
}

# 启动 Web 服务
run_web() {
    print_info "启动 Web 服务..."
    cd backend
    uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
}

# 发送测试邮件
send_test_email() {
    print_info "发送测试邮件..."
    $PYTHON_CMD -c "
from backend.app.services.notifier import email_notifier
if email_notifier.send_test_email():
    print('测试邮件发送成功！')
else:
    print('测试邮件发送失败，请检查配置')
"
}

# 显示帮助
show_help() {
    echo ""
    echo "SCHEELS Arc'teryx 商品监控系统"
    echo ""
    echo "用法: ./start.sh [命令]"
    echo ""
    echo "命令:"
    echo "  install     安装所有依赖（首次运行必须执行）"
    echo "  check       执行一次检测"
    echo "  daemon      启动监控守护进程（持续运行）"
    echo "  web         启动 Web 管理界面"
    echo "  test-email  发送测试邮件"
    echo "  help        显示此帮助信息"
    echo ""
    echo "首次使用步骤:"
    echo "  1. ./start.sh install   # 安装依赖"
    echo "  2. 编辑 config.yaml      # 配置邮箱"
    echo "  3. ./start.sh test-email # 测试邮件"
    echo "  4. ./start.sh check      # 执行一次检测"
    echo "  5. ./start.sh daemon     # 启动持续监控"
    echo ""
}

# 主逻辑
main() {
    check_python

    case "${1:-help}" in
        install)
            check_config
            install_deps
            install_browser
            init_database
            print_success "安装完成！请编辑 config.yaml 配置邮箱后运行 ./start.sh check"
            ;;
        check)
            check_config
            run_once
            ;;
        daemon)
            check_config
            run_daemon
            ;;
        web)
            check_config
            run_web
            ;;
        test-email)
            check_config
            send_test_email
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
