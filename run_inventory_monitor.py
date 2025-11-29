#!/usr/bin/env python3
"""
Arc'teryx 库存监控脚本
监控指定商品的库存变化，补货时发送邮件通知

使用方法:
    # 添加监控商品（监控所有尺寸）
    python run_inventory_monitor.py --add "https://arcteryx.com/us/en/shop/mens/beta-sl-jacket-9685"

    # 添加监控商品（只监控指定尺寸）
    python run_inventory_monitor.py --add "https://arcteryx.com/us/en/shop/mens/beta-sl-jacket-9685" --sizes S M L

    # 执行一次检查
    python run_inventory_monitor.py --once

    # 守护进程模式运行（每5分钟检查一次）
    python run_inventory_monitor.py --daemon --interval 5

    # 查看当前监控状态
    python run_inventory_monitor.py --status

    # 移除监控商品
    python run_inventory_monitor.py --remove "https://arcteryx.com/us/en/shop/mens/beta-sl-jacket-9685"
"""
import sys
import asyncio
import argparse
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from backend.app.services.inventory_monitor import (
    inventory_monitor_service,
    run_inventory_monitor_once,
    run_inventory_monitor_daemon
)
from loguru import logger


def setup_logging():
    """设置日志"""
    logger.remove()
    logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )

    log_file = Path(__file__).parent / 'logs' / 'inventory_monitor.log'
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        str(log_file),
        level="INFO",
        rotation="10 MB",
        retention=5,
        encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Arc'teryx 库存监控工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--add",
        metavar="URL",
        help="添加监控商品URL"
    )
    parser.add_argument(
        "--name",
        metavar="NAME",
        help="商品名称（配合--add使用）"
    )
    parser.add_argument(
        "--sizes",
        nargs="+",
        metavar="SIZE",
        help="要监控的尺寸列表（如 S M L），不指定则监控所有尺寸"
    )
    parser.add_argument(
        "--remove",
        metavar="URL",
        help="移除监控商品"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="执行一次库存检查"
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="守护进程模式运行"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="检查间隔（分钟），默认5分钟"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="查看当前监控状态"
    )

    args = parser.parse_args()

    setup_logging()

    # 添加监控商品
    if args.add:
        inventory_monitor_service.add_product(
            url=args.add,
            name=args.name or "",
            target_sizes=args.sizes
        )
        print(f"✅ 已添加监控: {args.add}")
        if args.sizes:
            print(f"   目标尺寸: {', '.join(args.sizes)}")
        else:
            print("   目标尺寸: 全部")
        return

    # 移除监控商品
    if args.remove:
        inventory_monitor_service.remove_product(args.remove)
        print(f"✅ 已移除监控: {args.remove}")
        return

    # 查看状态
    if args.status:
        status = inventory_monitor_service.get_status()
        print("\n📊 库存监控状态")
        print("=" * 50)
        print(f"运行状态: {'运行中 🟢' if status['is_running'] else '已停止 🔴'}")
        print(f"上次检查: {status['last_check_time'] or '尚未检查'}")
        print(f"监控商品数: {status['monitored_products']}")
        print()

        if status['products']:
            print("📦 监控商品列表:")
            for i, p in enumerate(status['products'], 1):
                print(f"\n  {i}. {p['name'] or '未命名'}")
                print(f"     URL: {p['url']}")
                print(f"     目标尺寸: {', '.join(p['target_sizes']) if p['target_sizes'] else '全部'}")
                print(f"     当前有货: {', '.join(p['last_available']) if p['last_available'] else '无'}")
        else:
            print("⚠️  暂无监控商品，请使用 --add 添加")
        return

    # 执行一次检查
    if args.once:
        if not inventory_monitor_service.monitored_products:
            print("⚠️  暂无监控商品，请先使用 --add 添加商品")
            return
        print("🔍 开始检查库存...")
        result = asyncio.run(run_inventory_monitor_once())
        print(f"\n✅ 检查完成:")
        print(f"   检查商品数: {result['products_checked']}")
        print(f"   检测到变化: {result['changes_detected']}")
        print(f"   发送通知数: {result['notifications_sent']}")
        if result['errors']:
            print(f"   错误: {result['errors']}")
        return

    # 守护进程模式
    if args.daemon:
        if not inventory_monitor_service.monitored_products:
            print("⚠️  暂无监控商品，请先使用 --add 添加商品")
            return
        print(f"🚀 启动库存监控守护进程（间隔: {args.interval} 分钟）")
        print("   按 Ctrl+C 停止")
        try:
            asyncio.run(run_inventory_monitor_daemon(args.interval))
        except KeyboardInterrupt:
            print("\n👋 已停止监控")
        return

    # 默认显示帮助
    parser.print_help()


if __name__ == "__main__":
    main()
