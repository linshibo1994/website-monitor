#!/bin/bash
# ===========================================
# 服务器 Docker 更新脚本
# 功能：拉取最新代码 + 必要时构建前端 + 重建并重启容器 + 清理 Docker 垃圾
# 用法：./update.sh [分支名] [选项]
# 示例：./update.sh main --prune-all
# ===========================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BRANCH="main"
BRANCH_SET=false
PRUNE_MODE="safe"   # safe | none | all
PRUNE_VOLUMES=false

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
  echo -e "${BLUE}[INFO]${NC} $1"
}

log_ok() {
  echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

log_err() {
  echo -e "${RED}[ERROR]${NC} $1"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log_err "缺少命令: $1"
    exit 1
  fi
}

show_help() {
  cat <<'EOF'
用法:
  ./update.sh [分支名] [选项]

参数:
  分支名                 默认 main

选项:
  --no-prune            部署后不做 Docker 清理
  --prune-all           部署后执行激进清理（清理所有未使用镜像与构建缓存）
  --prune-volumes       仅与 --prune-all 配合使用，额外清理未使用 volumes
  -h, --help            显示帮助

说明:
  默认会执行安全清理（推荐）：
  - 清理停止容器
  - 清理 dangling 镜像
  - 清理 7 天前的构建缓存
  - 清理未使用网络
EOF
}

parse_args() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --no-prune)
        PRUNE_MODE="none"
        ;;
      --prune-all)
        PRUNE_MODE="all"
        ;;
      --prune-volumes)
        PRUNE_VOLUMES=true
        ;;
      -h|--help)
        show_help
        exit 0
        ;;
      -*)
        log_err "未知选项: $1"
        show_help
        exit 1
        ;;
      *)
        if [ "$BRANCH_SET" = false ]; then
          BRANCH="$1"
          BRANCH_SET=true
        else
          log_err "只允许一个分支参数，收到多余参数: $1"
          show_help
          exit 1
        fi
        ;;
    esac
    shift
  done
}

cleanup_safe() {
  log_info "执行安全清理（停止容器 / dangling 镜像 / 旧构建缓存 / 未使用网络）..."
  docker container prune -f >/dev/null || true
  docker image prune -f >/dev/null || true
  docker builder prune -f --filter "until=168h" >/dev/null || true
  docker network prune -f >/dev/null || true
  log_ok "安全清理完成"
}

cleanup_all() {
  log_warn "执行激进清理（所有未使用镜像和构建缓存）..."
  docker container prune -f >/dev/null || true
  docker image prune -af >/dev/null || true
  docker builder prune -af >/dev/null || true
  docker network prune -f >/dev/null || true
  if [ "$PRUNE_VOLUMES" = true ]; then
    log_warn "额外清理未使用 volumes..."
    docker volume prune -f >/dev/null || true
  else
    log_warn "未清理 volumes（如需清理请加 --prune-volumes）"
  fi
  log_ok "激进清理完成"
}

parse_args "$@"

require_cmd git
require_cmd docker

if ! docker compose version >/dev/null 2>&1; then
  log_err "当前环境不可用: docker compose"
  exit 1
fi

# 仅检查已跟踪文件变更，避免误覆盖服务器上的本地改动
if ! git diff --quiet || ! git diff --cached --quiet; then
  log_err "检测到已跟踪文件存在未提交修改，请先提交/暂存后再更新。"
  exit 1
fi

OLD_REV="$(git rev-parse HEAD)"
log_info "当前版本: ${OLD_REV:0:8}"

log_info "拉取分支: $BRANCH"
git pull --ff-only origin "$BRANCH"

NEW_REV="$(git rev-parse HEAD)"
log_info "最新版本: ${NEW_REV:0:8}"

if [ "$OLD_REV" = "$NEW_REV" ]; then
  log_warn "代码没有变化，本次无需重建。"
  exit 0
fi

CHANGED_FILES="$(git diff --name-only "$OLD_REV" "$NEW_REV")"

FRONTEND_SRC_CHANGED=false
FRONTEND_DIST_CHANGED=false

if echo "$CHANGED_FILES" | grep -Eq '^frontend/(src/|public/|index\.html|package\.json|package-lock\.json|vite\.config\.js)'; then
  FRONTEND_SRC_CHANGED=true
fi

if echo "$CHANGED_FILES" | grep -Eq '^frontend/dist/'; then
  FRONTEND_DIST_CHANGED=true
fi

# Dockerfile 会 COPY frontend/dist，所以当前端源码更新但 dist 未更新时，需要在服务器重新构建前端
if [ "$FRONTEND_SRC_CHANGED" = true ] && [ "$FRONTEND_DIST_CHANGED" = false ]; then
  require_cmd npm
  log_info "检测到前端源码变更，开始构建 frontend/dist ..."
  (
    cd frontend
    npm ci
    npm run build
  )
  log_ok "前端构建完成"
fi

log_info "重建并启动 Docker 服务..."
docker compose up -d --build

log_info "容器状态："
docker compose ps

case "$PRUNE_MODE" in
  none)
    log_info "按参数要求跳过 Docker 清理（--no-prune）"
    ;;
  safe)
    cleanup_safe
    ;;
  all)
    cleanup_all
    ;;
  *)
    log_err "无效清理模式: $PRUNE_MODE"
    exit 1
    ;;
esac

log_info "当前 Docker 空间占用："
docker system df || true

if command -v curl >/dev/null 2>&1; then
  log_info "健康检查: http://localhost:7080/api/health"
  if curl -fsS "http://localhost:7080/api/health" >/dev/null 2>&1; then
    log_ok "健康检查通过"
  else
    log_warn "健康检查未通过，请检查日志：docker compose logs -f --tail=200 monitor"
  fi
fi

log_ok "更新完成"
