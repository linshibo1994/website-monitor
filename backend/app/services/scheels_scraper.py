"""
Scheels 商品库存监控模块
监控 scheels.com 商品的各尺寸库存状态
"""
import asyncio
import os
from typing import Optional, List
from datetime import datetime
from loguru import logger

from .inventory_scraper import ProductInventory, VariantStock, InventoryChange


class ScheelsInventoryScraper:
    """Scheels 库存抓取器 - 使用 Playwright 浏览器"""

    # 尺码标准化映射
    SIZE_NORMALIZE = {
        'Small': 'S',
        'Medium': 'M',
        'Large': 'L',
        'XLarge': 'XL',
        '2XLarge': '2XL',
        'XSmall': 'XS',
        '3XLarge': '3XL',
    }

    # 尺寸排序
    SIZE_ORDER = {'XS': 0, 'S': 1, 'M': 2, 'L': 3, 'XL': 4, '2XL': 5, '3XL': 6}

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
        except:
            return False

    def _normalize_size(self, size_text: str) -> str:
        """标准化尺寸名称"""
        size_text = size_text.strip()
        return self.SIZE_NORMALIZE.get(size_text, size_text)

    async def get_available_colors(self, product_url: str, timeout: int = 30000) -> List[dict]:
        """轻量级获取 Scheels 商品颜色（每个 URL 只对应单一颜色）"""
        from playwright.async_api import async_playwright

        browser = None
        playwright_instance = None

        try:
            playwright_instance = await async_playwright().start()

            browser_args = [
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-setuid-sandbox',
            ]

            has_display = os.environ.get('DISPLAY') is not None

            if self.is_docker and has_display:
                logger.info(f"Docker 环境 (DISPLAY={os.environ.get('DISPLAY')})：使用 Xvfb 虚拟显示")
                browser = await playwright_instance.chromium.launch(
                    headless=False,
                    args=browser_args
                )
            elif self.is_docker:
                logger.info("Docker 环境：使用 headless 模式（颜色获取）")
                browser = await playwright_instance.chromium.launch(
                    headless=True,
                    args=browser_args
                )
            else:
                logger.info("本地环境：使用 headless 模式（颜色获取）")
                browser = await playwright_instance.chromium.launch(
                    headless=True,
                    args=browser_args
                )

            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York',
            )

            await context.add_init_script('''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            ''')

            page = await context.new_page()
            page.set_default_timeout(timeout)

            logger.info("加载 Scheels 页面获取颜色信息...")
            await page.goto(product_url, wait_until='domcontentloaded', timeout=timeout)

            # Scheels 颜色与 URL 一一对应，只需解析当前颜色
            color_name = await self._get_current_color(page)
            if color_name:
                return [{'value': color_name, 'label': color_name}]

            logger.warning("未能获取 Scheels 颜色信息")
            return []
        except Exception as e:
            logger.error(f"获取 Scheels 颜色信息失败: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
        finally:
            if browser:
                await browser.close()
            if playwright_instance:
                await playwright_instance.stop()

    async def check_inventory(self, product_url: str, max_retries: int = 3) -> Optional[ProductInventory]:
        """
        检查 Scheels 商品库存（带重试机制）

        Args:
            product_url: 商品页面URL
            max_retries: 最大重试次数

        Returns:
            ProductInventory 或 None（失败时）
        """
        last_error = None

        for attempt in range(max_retries):
            if attempt > 0:
                wait_time = 5 * attempt  # 递增等待时间
                logger.info(f"第 {attempt + 1} 次重试，等待 {wait_time} 秒...")
                await asyncio.sleep(wait_time)

            result = await self._check_inventory_once(product_url)
            if result is not None:
                return result

            logger.warning(f"第 {attempt + 1}/{max_retries} 次尝试失败")

        logger.error(f"Scheels 库存检查失败，已重试 {max_retries} 次: {product_url}")
        return None

    async def _check_inventory_once(self, product_url: str) -> Optional[ProductInventory]:
        """
        单次检查 Scheels 商品库存

        Args:
            product_url: 商品页面URL

        Returns:
            ProductInventory 或 None（失败时）
        """
        from playwright.async_api import async_playwright

        logger.info(f"正在检查 Scheels 库存: {product_url}")

        browser = None
        playwright_instance = None

        try:
            playwright_instance = await async_playwright().start()

            # 浏览器启动参数
            browser_args = [
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-setuid-sandbox',
            ]

            # 检查 DISPLAY 环境变量
            has_display = os.environ.get('DISPLAY') is not None

            if self.is_docker and has_display:
                logger.info(f"Docker 环境 (DISPLAY={os.environ.get('DISPLAY')})：使用 Xvfb 虚拟显示")
                browser = await playwright_instance.chromium.launch(
                    headless=False,
                    args=browser_args
                )
            elif self.is_docker:
                logger.info("Docker 环境：使用 headless 模式")
                browser = await playwright_instance.chromium.launch(
                    headless=True,
                    args=browser_args
                )
            else:
                # 本地环境：使用 headless 模式
                logger.info("本地环境：使用 headless 模式")
                browser = await playwright_instance.chromium.launch(
                    headless=True,
                    args=browser_args
                )

            # 创建浏览器上下文
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York',
            )

            # 移除 webdriver 标记
            await context.add_init_script('''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            ''')

            page = await context.new_page()
            page.set_default_timeout(60000)

            logger.info("正在加载页面...")
            # 使用 domcontentloaded 策略，比 networkidle 更快
            await page.goto(product_url, wait_until='domcontentloaded', timeout=60000)

            # 等待页面基本稳定
            await asyncio.sleep(3)

            # 获取商品名称
            product_name = await self._get_product_name(page)
            logger.info(f"商品名称: {product_name}")

            # 检测是否为 "Coming Soon" 状态
            is_coming_soon = await self._check_coming_soon(page)

            if is_coming_soon:
                logger.info(f"商品状态: Coming Soon (即将上架)")
                inventory = ProductInventory(
                    model_sku=self._extract_sku_from_url(product_url),
                    name=product_name,
                    url=product_url,
                    variants=[],
                    check_time=datetime.now(),
                    status="coming_soon"
                )
                return inventory

            # 等待尺码选择器出现
            try:
                await page.wait_for_selector('button:has-text("Small"), button:has-text("Medium"), button:has-text("Large")', timeout=30000)
                logger.info("检测到尺码选择器")
            except:
                logger.warning("未检测到尺码选择器，尝试继续...")
                # 额外等待
                await asyncio.sleep(5)

            # 尝试关闭可能的弹窗
            try:
                close_button = page.locator('[aria-label="Close"]').first
                if await close_button.is_visible():
                    await close_button.click()
                    await asyncio.sleep(0.5)
            except:
                pass

            # 获取尺码库存状态
            variants = await self._get_size_variants(page)

            if not variants:
                logger.error("无法获取尺寸库存信息")
                return None

            # 按尺寸排序
            variants.sort(key=lambda v: self.SIZE_ORDER.get(v.size, 99))

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
            logger.error(f"检查 Scheels 库存失败: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
        finally:
            if browser:
                await browser.close()
            if playwright_instance:
                await playwright_instance.stop()

    async def _check_coming_soon(self, page) -> bool:
        """检测页面是否为 Coming Soon 状态"""
        try:
            # 首先检查是否有正常商品的标志（尺码选择器或加购按钮）
            # 如果有，则一定不是 Coming Soon
            try:
                size_selector = page.locator('button:has-text("Small"), button:has-text("Medium"), button:has-text("Large")').first
                has_size_selector = await size_selector.is_visible()
                if has_size_selector:
                    logger.debug("检测到尺码选择器，商品已上架")
                    return False
            except:
                pass

            try:
                add_to_cart = page.locator('button:has-text("Add to Cart"), button:has-text("ADD TO CART")').first
                has_add_to_cart = await add_to_cart.is_visible()
                if has_add_to_cart:
                    logger.debug("检测到加购按钮，商品已上架")
                    return False
            except:
                pass

            # 没有正常购买功能，检测是否有 Coming Soon 标记
            html_content = await page.content()
            import re

            # 方法1: 检测 Next.js 数据中的 isComingSoon 标记（最可靠）
            if re.search(r'\\"isComingSoon\\":true', html_content) or re.search(r'"isComingSoon":true', html_content):
                logger.info("检测到 Coming Soon 标记 (isComingSoon: true)")
                return True

            # 方法2: 检测 Coming Soon 按钮
            try:
                coming_soon_button = page.locator('button:has-text("Coming Soon"), button:has-text("COMING SOON")').first
                if await coming_soon_button.is_visible():
                    logger.info("检测到 Coming Soon 按钮")
                    return True
            except:
                pass

            # 方法3: 检测主要内容区域的 Coming Soon 文本（而非整个页面）
            try:
                # 查找商品主区域的 Coming Soon 文本
                main_content = page.locator('[class*="product"], [class*="pdp"], main').first
                if await main_content.is_visible():
                    main_text = await main_content.text_content()
                    if main_text and 'coming soon' in main_text.lower():
                        logger.info("检测到商品区域 Coming Soon 文本")
                        return True
            except:
                pass

            return False
        except Exception as e:
            logger.warning(f"检测 Coming Soon 状态失败: {e}")
            return False

    def _extract_sku_from_url(self, url: str) -> str:
        """从URL中提取商品ID"""
        # URL格式: https://www.scheels.com/p/62355577847
        import re
        match = re.search(r'/p/(\d+)', url)
        return match.group(1) if match else ''

    async def _get_product_name(self, page) -> str:
        """获取商品名称"""
        try:
            # 方法1: 从 title 标签获取
            title = await page.title()
            if title and 'SCHEELS' in title:
                # 格式: "商品名称 | SCHEELS.com"
                name = title.split('|')[0].strip()
                if name:
                    return name

            # 方法2: 从页面 HTML 中提取
            html_content = await page.content()
            import re

            # 从 Next.js 数据中提取商品名称
            # 格式: \"name\":\"Men's Arc'teryx Thorium Hooded Puffer Jacket\"
            name_match = re.search(r'\\"name\\":\\"([^"\\\\]+(?:\\\\.[^"\\\\]*)*)\\"', html_content)
            if name_match:
                name = name_match.group(1).replace('\\"', '"').replace("\\'", "'")
                if len(name) > 5 and len(name) < 200:
                    return name

            # 方法3: 从 og:title 提取
            og_match = re.search(r'property="og:title"\s+content="([^"]+)"', html_content)
            if og_match:
                return og_match.group(1)

            # 方法4: 尝试多种选择器
            selectors = [
                'h1[data-testid="product-title"]',
                'h1.product-title',
                'h1',
                '[class*="product-name"]',
            ]

            for selector in selectors:
                try:
                    element = page.locator(selector).first
                    if await element.is_visible():
                        name = await element.text_content()
                        if name and name.strip() and len(name.strip()) > 5:
                            return name.strip()
                except:
                    continue

            return "Unknown Product"
        except Exception as e:
            logger.warning(f"获取商品名称失败: {e}")
            return "Unknown Product"

    async def _get_current_color(self, page) -> str:
        """获取当前页面已选颜色名称"""
        import re
        try:
            html_content = await page.content()

            # 1) 从页面 HTML 数据中直接匹配颜色字段
            color_patterns = [
                r'\\"color\\":\\"\\d+::([^\\"]+)\\"',    # 转义 JSON 形式
                r'"color":"\d+::([^"\\\\]+)"',          # 未转义 JSON 形式
                r'\\"selectedColor\\":\\"([^\\"]+)\\"',  # 转义的 selectedColor
                r'"selectedColor":"([^"\\\\]+)"',        # 未转义的 selectedColor
            ]

            for pattern in color_patterns:
                match = re.search(pattern, html_content)
                if match:
                    color_name = match.group(1).strip()
                    if color_name:
                        logger.debug(f"从页面数据提取颜色: {color_name}")
                        return color_name

            # 2) DOM 兜底：查找 h2 中的 "Color:xxx"
            try:
                color_heading = page.locator('h2:has-text("Color")').first
                if await color_heading.is_visible():
                    text = await color_heading.text_content()
                    if text:
                        text = text.replace('\n', '').strip()
                        if ':' in text:
                            candidate = text.split(':', 1)[1].strip()
                        else:
                            candidate = text.replace('Color', '').replace('颜色', '').strip(' :')
                        if candidate:
                            logger.debug(f"从 DOM 提取颜色: {candidate}")
                            return candidate
            except Exception as dom_error:
                logger.debug(f"DOM 颜色提取失败: {dom_error}")

            return ""
        except Exception as e:
            logger.warning(f"获取颜色信息失败: {e}")
            return ""

    async def _get_size_variants(self, page) -> List[VariantStock]:
        """获取尺码库存状态"""
        variants = []

        try:
            # 获取当前颜色信息
            current_color = await self._get_current_color(page)
            if current_color:
                logger.info(f"当前颜色: {current_color}")
            else:
                logger.warning("未获取到颜色信息，color_name 将为空")

            # 获取页面 HTML 内容
            html_content = await page.content()

            # 从 URL 提取当前 SKU
            current_url = page.url
            import re
            url_match = re.search(r'/p/(\d+)', current_url)
            current_sku = url_match.group(1) if url_match else ''
            sku_prefix = current_sku[:9] if len(current_sku) >= 9 else current_sku

            logger.info(f"当前 SKU: {current_sku}, 前缀: {sku_prefix}")

            # 正则匹配变体数据（转义的 JSON 格式）
            # 格式: \"sku\":\"62355577847\"...\"apparelSize\":\"133::2XLarge\"...\"isOnStock\":true,\"availableQuantity\":12
            pattern = r'\\"sku\\":\\"(\d+)\\".*?\\"apparelSize\\":\\"(\d+)::([^\\"\\\\]+)\\".*?\\"isOnStock\\":(true|false),\\"availableQuantity\\":(\d+)'

            seen = set()
            matches = re.finditer(pattern, html_content)

            for match in matches:
                sku = match.group(1)
                size_code = match.group(2)
                size_name = match.group(3)
                is_on_stock = match.group(4) == 'true'
                quantity = int(match.group(5))

                # 只获取当前颜色的变体（SKU 前缀相同）
                variant_prefix = sku[:9] if len(sku) >= 9 else sku

                if variant_prefix == sku_prefix and size_name not in seen:
                    seen.add(size_name)
                    normalized_size = self._normalize_size(size_name)
                    stock_status = 'InStock' if is_on_stock else 'OutOfStock'

                    variants.append(VariantStock(
                        variant_sku=sku,
                        size=normalized_size,
                        stock_status=stock_status,
                        color_name=current_color
                    ))
                    logger.debug(f"找到尺码: {size_name} ({normalized_size}), SKU: {sku}, 状态: {stock_status}")

            if variants:
                logger.info(f"从页面数据获取到 {len(variants)} 个尺码")
                return variants

            logger.warning("未能从页面提取尺码数据")
            return []

        except Exception as e:
            logger.error(f"获取尺码信息失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    def compare_inventory(
        self,
        old_inventory: Optional[ProductInventory],
        new_inventory: ProductInventory
    ) -> List[InventoryChange]:
        """
        比较库存变化

        Args:
            old_inventory: 上次的库存状态（可能为None）
            new_inventory: 当前的库存状态

        Returns:
            库存变化列表
        """
        changes = []

        if old_inventory is None:
            # 首次检查，不产生变化记录
            return changes

        # 构建旧状态映射
        old_status_map = {v.size: v.stock_status for v in old_inventory.variants}

        # 比较每个尺寸的库存状态
        for variant in new_inventory.variants:
            old_status = old_status_map.get(variant.size, 'Unknown')
            new_status = variant.stock_status

            if old_status != new_status:
                # 检查是否从无库存变为有库存
                was_available = old_status in ['InStock', 'LowStock']
                is_available = new_status in ['InStock', 'LowStock']

                changes.append(InventoryChange(
                    size=variant.size,
                    old_status=old_status,
                    new_status=new_status,
                    became_available=not was_available and is_available,
                    color_name=variant.color_name
                ))

                logger.info(
                    f"库存变化: {variant.size} - {old_status} -> {new_status}"
                    f" ({'补货了!' if not was_available and is_available else '售罄了'})"
                )

        return changes


# 创建抓取器单例
scheels_scraper = ScheelsInventoryScraper()


async def check_scheels_inventory(product_url: str) -> Optional[ProductInventory]:
    """检查 Scheels 商品库存（模块级函数）"""
    return await scheels_scraper.check_inventory(product_url)
