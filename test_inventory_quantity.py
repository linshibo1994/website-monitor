#!/usr/bin/env python3
"""
测试库存数量获取功能

使用方法:
    python test_inventory_quantity.py <product_url>

示例:
    python test_inventory_quantity.py "https://arcteryx.com/us/en/shop/mens/beta-sl-jacket-9685"
"""
import asyncio
import sys
from backend.app.services.inventory_scraper import check_product_inventory


async def test_inventory_quantity(product_url: str):
    """测试库存数量获取"""
    print(f"\n{'='*60}")
    print(f"测试商品: {product_url}")
    print(f"{'='*60}\n")

    print("正在检查库存...")
    inventory = await check_product_inventory(product_url)

    if inventory is None:
        print("❌ 库存检查失败")
        return

    print(f"\n✅ 库存检查成功!")
    print(f"\n商品名称: {inventory.name}")
    print(f"商品SKU: {inventory.model_sku}")
    print(f"商品状态: {inventory.status}")
    print(f"检查时间: {inventory.check_time}")

    print(f"\n{'='*60}")
    print("库存详情:")
    print(f"{'='*60}")

    # 按状态分组显示
    in_stock_variants = [v for v in inventory.variants if v.stock_status == 'InStock']
    low_stock_variants = [v for v in inventory.variants if v.stock_status == 'LowStock']
    out_of_stock_variants = [v for v in inventory.variants if v.stock_status == 'OutOfStock']

    if in_stock_variants:
        print("\n🟢 充足库存 (InStock):")
        for v in in_stock_variants:
            color_text = f" - {v.color_name}" if v.color_name else ""
            print(f"  • {v.size:4s}{color_text:15s} | {v.quantity_display()}")

    if low_stock_variants:
        print("\n🟡 低库存 (LowStock):")
        for v in low_stock_variants:
            color_text = f" - {v.color_name}" if v.color_name else ""
            qty_detail = f"(精确数量: {v.quantity})" if v.quantity is not None else "(未获取精确数量)"
            print(f"  • {v.size:4s}{color_text:15s} | {v.quantity_display():12s} {qty_detail}")

    if out_of_stock_variants:
        print("\n🔴 无库存 (OutOfStock):")
        for v in out_of_stock_variants:
            color_text = f" - {v.color_name}" if v.color_name else ""
            print(f"  • {v.size:4s}{color_text:15s} | {v.quantity_display()}")

    print(f"\n{'='*60}")
    print("测试完成!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python test_inventory_quantity.py <product_url>")
        print("\n示例:")
        print('  python test_inventory_quantity.py "https://arcteryx.com/us/en/shop/mens/beta-sl-jacket-9685"')
        sys.exit(1)

    product_url = sys.argv[1]
    asyncio.run(test_inventory_quantity(product_url))
