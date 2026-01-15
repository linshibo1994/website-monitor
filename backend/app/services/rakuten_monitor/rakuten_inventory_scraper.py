"""
Rakuten (乐天) 商品库存监控模块
使用 Playwright 抓取商品页面，提取 variantMappedInventories 库存数据
"""
import asyncio
import json
import os
import re
import traceback
from typing import Optional, List, Dict, Any
from datetime import datetime
from urllib.parse import urlparse
from loguru import logger

from ..inventory_scraper import ProductInventory, VariantStock, InventoryChange


class RakutenInventoryScraper:
    """Rakuten 库存抓取器 - 使用 Playwright 浏览器"""

    def __init__(self):
        # 检测是否在 Docker 环境中运行
        self.is_docker = self._is_running_in_docker()

    def _is_running_in_docker(self) -> bool:
        """检测是否在 Docker 容器中运行"""
        if os.path.exists('/.dockerenv'):
            return True
        try:
            with open('/proc/1/cgroup', 'r') as f:
                return 'docker' in f.read()
        except Exception:
            return False

    async def _create_browser(self, playwright_instance, timeout: int = 30000):
        """创建浏览器实例"""
        browser_args = [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--disable-setuid-sandbox',
        ]

        has_display = os.environ.get('DISPLAY') is not None

        if self.is_docker and has_display:
            logger.info(f"Docker 环境 (DISPLAY={os.environ.get('DISPLAY')}): 使用 Xvfb 虚拟显示")
            browser = await playwright_instance.chromium.launch(
                headless=False,
                args=browser_args
            )
        elif self.is_docker:
            logger.info("Docker 环境: 使用 headless 模式")
            browser = await playwright_instance.chromium.launch(
                headless=True,
                args=browser_args
            )
        else:
            logger.info("本地环境: 使用 headless 模式")
            browser = await playwright_instance.chromium.launch(
                headless=True,
                args=browser_args
            )

        # 创建浏览器上下文 - 使用日本地区设置
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='ja-JP',
            timezone_id='Asia/Tokyo',
        )

        # 移除 webdriver 标记
        await context.add_init_script('''
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        ''')

        page = await context.new_page()
        page.set_default_timeout(timeout)

        return browser, context, page

    def _validate_url(self, url: str) -> bool:
        """验证 URL 是否为有效的 Rakuten 域名"""
        try:
            parsed = urlparse(url)
            valid_domains = ['rakuten.co.jp', 'item.rakuten.co.jp']
            return any(parsed.netloc.endswith(domain) for domain in valid_domains)
        except Exception:
            return False

    def _extract_sku_from_url(self, url: str) -> str:
        """从 URL 中提取商品标识"""
        # 验证 URL 域名
        if not self._validate_url(url):
            logger.warning(f"非 Rakuten URL: {url}")
            return 'unknown'

        # 乐天 URL 格式: https://item.rakuten.co.jp/shop-name/item-id/
        match = re.search(r'/([^/]+)/([^/?]+)/?(?:\?|$)', url)
        if match:
            return f"{match.group(1)}_{match.group(2)}"
        return url.split('/')[-1].split('?')[0] or 'unknown'

    async def _get_product_name(self, page) -> str:
        """获取商品名称"""
        try:
            # 方法1: 从 og:title 获取
            og_title = await page.query_selector('meta[property="og:title"]')
            if og_title:
                content = await og_title.get_attribute('content')
                if content:
                    return content.strip()

            # 方法2: 从 title 标签获取
            title = await page.title()
            if title:
                # 移除常见后缀
                title = re.sub(r'\s*[|\-:]\s*楽天市場.*$', '', title)
                return title.strip()

            # 方法3: 从 h1 获取
            h1 = await page.query_selector('h1')
            if h1:
                text = await h1.text_content()
                if text:
                    return text.strip()

            return "Unknown Product"
        except Exception as e:
            logger.warning(f"获取商品名称失败: {e}")
            return "Unknown Product"

    async def _extract_variant_inventories(self, page) -> List[Dict[str, Any]]:
        """从页面提取 variantMappedInventories 数据"""
        try:
            html_content = await page.content()

            # 正则匹配 variantMappedInventories
            pattern = r'"variantMappedInventories"\s*:\s*(\[.*?\])'
            match = re.search(pattern, html_content, re.DOTALL)

            if match:
                try:
                    inventories = json.loads(match.group(1))
                    logger.info(f"成功提取 variantMappedInventories: {len(inventories)} 个变体")
                    return inventories
                except json.JSONDecodeError as e:
                    logger.warning(f"解析 variantMappedInventories JSON 失败: {e}")

            logger.debug("未找到 variantMappedInventories 数据")
            return []
        except Exception as e:
            logger.error(f"提取 variantMappedInventories 失败: {e}")
            return []

    async def _extract_sku_data(self, page) -> List[Dict[str, Any]]:
        """从页面提取 skuData 数据（包含变体详情）"""
        try:
            html_content = await page.content()

            # 正则匹配 skuData
            pattern = r'"skuData"\s*:\s*(\[.*?\])'
            match = re.search(pattern, html_content, re.DOTALL)

            if match:
                try:
                    sku_data = json.loads(match.group(1))
                    logger.info(f"成功提取 skuData: {len(sku_data)} 个 SKU")
                    return sku_data
                except json.JSONDecodeError as e:
                    logger.warning(f"解析 skuData JSON 失败: {e}")

            logger.debug("未找到 skuData 数据")
            return []
        except Exception as e:
            logger.error(f"提取 skuData 失败: {e}")
            return []

    def _parse_selector_values(self, selector_values: List[Dict]) -> Dict[str, str]:
        """解析 selectorValues 获取尺码和颜色"""
        result = {'size': '', 'color': ''}

        for sv in selector_values or []:
            selector_type = sv.get('selectorType', '').lower()
            value = sv.get('value', '')

            if 'size' in selector_type or selector_type in ['s', 'サイズ']:
                result['size'] = value
            elif 'color' in selector_type or selector_type in ['c', 'カラー', '色']:
                result['color'] = value

        # 如果没有明确的类型，尝试从值推断
        if not result['size'] and not result['color']:
            for sv in selector_values or []:
                value = sv.get('value', '')
                if value:
                    # 简单启发式：数字或常见尺码名可能是尺码
                    if re.match(r'^(XS|S|M|L|XL|XXL|\d+)$', value, re.IGNORECASE):
                        result['size'] = value
                    else:
                        result['color'] = value

        return result

    async def check_inventory(self, product_url: str, max_retries: int = 3) -> Optional[ProductInventory]:
        """
        检查 Rakuten 商品库存（带重试机制）

        Args:
            product_url: 商品页面 URL
            max_retries: 最大重试次数

        Returns:
            ProductInventory 或 None（失败时）
        """
        for attempt in range(max_retries):
            if attempt > 0:
                wait_time = 5 * attempt
                logger.info(f"第 {attempt + 1} 次重试，等待 {wait_time} 秒...")
                await asyncio.sleep(wait_time)

            result = await self._check_inventory_once(product_url)
            if result is not None:
                return result

            logger.warning(f"第 {attempt + 1}/{max_retries} 次尝试失败")

        logger.error(f"Rakuten 库存检查失败，已重试 {max_retries} 次: {product_url}")
        return None

    async def _check_inventory_once(self, product_url: str) -> Optional[ProductInventory]:
        """单次检查 Rakuten 商品库存"""
        from playwright.async_api import async_playwright

        logger.info(f"正在检查 Rakuten 库存: {product_url}")

        browser = None
        playwright_instance = None

        try:
            playwright_instance = await async_playwright().start()
            browser, context, page = await self._create_browser(playwright_instance)

            logger.info("正在加载页面...")
            await page.goto(product_url, wait_until='domcontentloaded', timeout=60000)

            # 等待页面稳定
            await asyncio.sleep(3)

            # 获取商品名称
            product_name = await self._get_product_name(page)
            logger.info(f"商品名称: {product_name}")

            # 提取库存数据
            inventories = await self._extract_variant_inventories(page)
            sku_data = await self._extract_sku_data(page)

            # 构建 SKU 到详情的映射
            sku_details: Dict[str, Dict] = {}
            for sku in sku_data:
                sku_id = sku.get('sku', '')
                if sku_id:
                    selector_values = sku.get('selectorValues', [])
                    parsed = self._parse_selector_values(selector_values)
                    sku_details[sku_id] = {
                        'size': parsed['size'],
                        'color': parsed['color'],
                        'price': sku.get('price', 0),
                        'variantId': sku.get('variantId', '')
                    }

            # 构建变体库存列表
            variants: List[VariantStock] = []
            seen = set()

            for inv in inventories:
                sku = inv.get('sku', '')
                quantity = inv.get('quantity', 0)

                # 获取 SKU 详情
                details = sku_details.get(sku, {})
                size = details.get('size', '') or sku
                color = details.get('color', '')

                # 去重
                key = f"{color}_{size}"
                if key in seen:
                    continue
                seen.add(key)

                # 判断库存状态
                if quantity > 0:
                    stock_status = 'InStock' if quantity > 5 else 'LowStock'
                else:
                    stock_status = 'OutOfStock'

                variants.append(VariantStock(
                    variant_sku=sku,
                    size=size,
                    stock_status=stock_status,
                    color_name=color,
                    quantity=quantity if quantity > 0 else None
                ))

                logger.debug(f"变体: SKU={sku}, 尺码={size}, 颜色={color}, 库存={quantity}, 状态={stock_status}")

            if not variants:
                # 兜底：检查页面是否有售罄标识
                html_content = await page.content()
                if '売り切れ' in html_content or 'SOLD OUT' in html_content.upper():
                    logger.info("商品已售罄")
                    variants.append(VariantStock(
                        variant_sku='default',
                        size='Default',
                        stock_status='OutOfStock',
                        quantity=0
                    ))
                else:
                    logger.warning("未能获取库存数据")
                    return None

            inventory = ProductInventory(
                model_sku=self._extract_sku_from_url(product_url),
                name=product_name,
                url=product_url,
                variants=variants,
                check_time=datetime.now(),
                status="available"
            )

            logger.info(f"库存检查完成: {inventory.name}")
            logger.info(f"有库存: {inventory.get_available_sizes()}")
            logger.info(f"无库存: {inventory.get_out_of_stock_sizes()}")

            return inventory

        except Exception as e:
            logger.error(f"检查 Rakuten 库存失败: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
        finally:
            if browser:
                await browser.close()
            if playwright_instance:
                await playwright_instance.stop()

    async def get_available_sizes(self, product_url: str, timeout: int = 30000) -> List[str]:
        """获取可用尺码列表"""
        inventory = await self.check_inventory(product_url, max_retries=1)
        if inventory:
            return inventory.get_available_sizes()
        return []

    def compare_inventory(
        self,
        old_inventory: Optional[ProductInventory],
        new_inventory: ProductInventory
    ) -> List[InventoryChange]:
        """
        比较库存变化

        Args:
            old_inventory: 上次的库存状态（可能为 None）
            new_inventory: 当前的库存状态

        Returns:
            库存变化列表
        """
        changes = []

        if old_inventory is None:
            # 首次检查，不产生变化记录
            return changes

        # 构建旧状态映射，使用 (颜色, 尺寸) 作为 key
        old_status_map = {
            (v.color_name, v.size): (v.stock_status, v.quantity)
            for v in old_inventory.variants
        }

        # 比较每个变体的库存状态
        for variant in new_inventory.variants:
            key = (variant.color_name, variant.size)
            old_data = old_status_map.get(key, ('Unknown', None))
            old_status = old_data[0]
            new_status = variant.stock_status

            if old_status != new_status:
                # 检查是否从无库存变为有库存
                was_available = old_status in ['InStock', 'LowStock']
                is_available = new_status in ['InStock', 'LowStock']

                change = InventoryChange(
                    size=variant.size,
                    old_status=old_status,
                    new_status=new_status,
                    became_available=not was_available and is_available,
                    color_name=variant.color_name,
                    quantity=variant.quantity
                )

                changes.append(change)

                logger.info(
                    f"库存变化: {variant.color_name} {variant.size} - {old_status} -> {new_status}"
                    f" ({'补货了!' if not was_available and is_available else '售罄了'})"
                    f" 库存: {variant.quantity}"
                )

        return changes


# 创建抓取器单例
rakuten_inventory_scraper = RakutenInventoryScraper()


async def check_rakuten_inventory(product_url: str) -> Optional[ProductInventory]:
    """检查 Rakuten 商品库存（模块级函数）"""
    return await rakuten_inventory_scraper.check_inventory(product_url)
