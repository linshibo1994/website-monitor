"""
Arc'teryx 商品库存监控模块
监控单个商品的各尺寸库存状态变化
支持多种获取方式：API、页面抓取
"""
import re
import json
import asyncio
import aiohttp
import os
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from loguru import logger

from ..config import get_config


@dataclass
class VariantStock:
    """变体库存信息"""
    variant_sku: str      # 变体SKU
    size: str             # 尺寸
    stock_status: str     # 库存状态: InStock / OutOfStock / LowStock
    color_id: str = ""    # 颜色ID
    color_name: str = ""  # 颜色名称（如 Black, Void 等）
    quantity: Optional[int] = None  # 精确库存（LowStock 时可用）

    def is_available(self) -> bool:
        """是否有库存"""
        return self.stock_status in ['InStock', 'LowStock']

    def quantity_display(self) -> str:
        """格式化剩余数量的展示文本"""
        if self.stock_status == 'InStock':
            return '充足 (>5 件)'
        if self.stock_status == 'OutOfStock':
            return '0 件'
        if self.stock_status == 'LowStock':
            if self.quantity is None:
                return '未知'
            return f"{self.quantity} 件"
        return '未知'


@dataclass
class ProductInventory:
    """商品库存信息"""
    model_sku: str                    # 商品SKU
    name: str                         # 商品名称
    url: str                          # 商品URL
    variants: List[VariantStock]      # 各尺寸库存
    check_time: datetime              # 检查时间
    status: str = "available"         # 商品状态: available / coming_soon / unavailable

    def get_available_sizes(self) -> List[str]:
        """获取有库存的尺寸"""
        return [v.size for v in self.variants if v.is_available()]

    def get_out_of_stock_sizes(self) -> List[str]:
        """获取无库存的尺寸"""
        return [v.size for v in self.variants if not v.is_available()]

    def is_coming_soon(self) -> bool:
        """是否为即将上架状态"""
        return self.status == "coming_soon"

    def is_available(self) -> bool:
        """是否为正常可购买状态"""
        return self.status == "available"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'model_sku': self.model_sku,
            'name': self.name,
            'url': self.url,
            'variants': [asdict(v) for v in self.variants],
            'check_time': self.check_time.isoformat(),
            'status': self.status
        }


@dataclass
class InventoryChange:
    """库存变化记录"""
    size: str                    # 尺寸
    old_status: str              # 旧状态
    new_status: str              # 新状态
    became_available: bool       # 是否变为有库存
    color_name: str = ""         # 颜色名称


class ArcteryxInventoryScraper:
    """Arc'teryx 库存抓取器 - 使用 Playwright 浏览器"""

    # 尺寸排序
    SIZE_ORDER = {'XS': 0, 'S': 1, 'M': 2, 'L': 3, 'XL': 4, 'XXL': 5}
    CART_FETCH_SCRIPT = """
        async ({ endpoint, payload, method }) => {
            try {
                const options = {
                    method,
                    headers: {
                        'accept': 'application/json, text/plain, */*'
                    }
                };
                if (method !== 'GET') {
                    options.headers['content-type'] = 'application/json';
                    if (payload) {
                        options.body = JSON.stringify(payload);
                    }
                }
                const response = await fetch(endpoint, options);
                const text = await response.text();
                let data = null;
                try {
                    data = text ? JSON.parse(text) : null;
                } catch (err) {
                    data = null;
                }
                return {
                    ok: response.ok,
                    status: response.status,
                    data
                };
            } catch (error) {
                return {
                    ok: false,
                    status: 0,
                    error: String(error)
                };
            }
        }
    """

    def __init__(self):
        self.config = get_config()
        # 检测是否在 Docker 环境中运行
        self.is_docker = self._is_running_in_docker()

    def _is_running_in_docker(self) -> bool:
        """检测是否在 Docker 容器中运行"""
        import os
        # 检查 /.dockerenv 文件或 cgroup
        if os.path.exists('/.dockerenv'):
            return True
        try:
            with open('/proc/1/cgroup', 'r') as f:
                return 'docker' in f.read()
        except:
            return False

    def _extract_sku_from_url(self, url: str) -> Optional[str]:
        """从URL中提取SKU"""
        # URL格式: https://arcteryx.com/us/en/shop/mens/beta-sl-jacket-9685
        match = re.search(r'-(\d+)(?:\?|$|/)?$', url.split('?')[0])
        if match:
            sku_num = match.group(1)
            full_sku = f"X{sku_num.zfill(9)}"
            return full_sku
        return None

    async def get_available_colors(self, product_url: str, timeout: int = 30000) -> List[dict]:
        """
        轻量级获取可用颜色列表（仅解析颜色，不抓取库存）

        Args:
            product_url: 商品页面URL
            timeout: 页面加载和操作超时时间（毫秒）

        Returns:
            颜色选项列表，例如 [{"value": "11281", "label": "Void"}]
        """
        from playwright.async_api import async_playwright

        browser = None
        playwright_instance = None
        colors: List[dict] = []
        seen_keys = set()

        # 统一颜色去重与追加逻辑
        def add_color(value: str, label: str):
            val = (value or '').strip()
            lbl = (label or '').strip()
            key = val or lbl
            if not key or key in seen_keys:
                return
            seen_keys.add(key)
            colors.append({'value': val or lbl, 'label': lbl or val})

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
                logger.info("本地环境：使用非 headless 模式（颜色获取）")
                browser_args.append('--window-position=-10000,-10000')
                browser = await playwright_instance.chromium.launch(
                    headless=False,
                    args=browser_args
                )

            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York',
                geolocation={'latitude': 40.7128, 'longitude': -74.0060},
                permissions=['geolocation']
            )

            await context.add_init_script('''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            ''')

            page = await context.new_page()
            page.set_default_timeout(timeout)

            logger.info("加载页面获取颜色信息...")
            await page.goto(product_url, wait_until='domcontentloaded', timeout=timeout)

            try:
                await page.wait_for_selector('#__NEXT_DATA__', state='attached', timeout=5000)
            except Exception:
                logger.debug("未及时检测到 __NEXT_DATA__，尝试直接解析页面")

            product_data = await page.evaluate('''() => {
                const nextData = document.getElementById('__NEXT_DATA__');
                if (nextData) {
                    try {
                        const data = JSON.parse(nextData.textContent);
                        const product = data?.props?.pageProps?.product;
                        if (product) {
                            if (typeof product === 'string') {
                                return JSON.parse(product);
                            }
                            return product;
                        }
                    } catch (e) {
                        console.error('解析 __NEXT_DATA__ 失败:', e);
                    }
                }
                return null;
            }''')

            if not product_data:
                logger.warning("未能从页面数据中获取产品信息，颜色列表可能为空")
                return []

            colour_options = product_data.get('colourOptions', {}) if isinstance(product_data, dict) else {}
            if isinstance(colour_options, dict):
                options_list = colour_options.get('options', [])
            elif isinstance(colour_options, list):
                options_list = colour_options
            else:
                options_list = []

            # 优先从 colourOptions 中获取颜色
            for opt in options_list:
                if not isinstance(opt, dict):
                    continue
                value = str(opt.get('value', '')).strip()
                label = (opt.get('label', '') or '').strip()
                add_color(value, label)

            # 补充：从变体中合并遗漏的颜色
            if isinstance(product_data, dict):
                for variant in product_data.get('variants', []):
                    if not isinstance(variant, dict):
                        continue
                    color_id = str(variant.get('colourId', '')).strip()
                    colour_alternate_views = variant.get('colourAlternateViews') or []
                    colour_label = ''
                    if colour_alternate_views and isinstance(colour_alternate_views[0], dict):
                        colour_label = (colour_alternate_views[0].get('colourLabel', '') or '').strip()
                    # add_color 内部已有 lbl or val 回退逻辑
                    add_color(color_id, colour_label)

            return colors
        except Exception as e:
            logger.error(f"获取 Arc'teryx 颜色信息失败: {type(e).__name__}: {e}")
            return []
        finally:
            if browser:
                await browser.close()
            if playwright_instance:
                await playwright_instance.stop()

    async def check_inventory(self, product_url: str, max_retries: int = 3) -> Optional[ProductInventory]:
        """
        检查商品库存（带重试机制）

        Args:
            product_url: 商品页面URL
            max_retries: 最大重试次数

        Returns:
            ProductInventory 或 None（失败时）
        """
        for attempt in range(max_retries):
            if attempt > 0:
                wait_time = 5 * attempt  # 递增等待时间
                logger.info(f"第 {attempt + 1} 次重试，等待 {wait_time} 秒...")
                await asyncio.sleep(wait_time)

            result = await self._check_inventory_once(product_url)
            if result is not None:
                return result

            logger.warning(f"第 {attempt + 1}/{max_retries} 次尝试失败")

        logger.error(f"Arc'teryx 库存检查失败，已重试 {max_retries} 次: {product_url}")
        return None

    async def get_exact_quantity(
        self,
        page: Any,
        variant: VariantStock,
        cart_params: Optional[Dict[str, str]]
    ) -> Optional[int]:
        """
        通过购物车 API 获取 LowStock 变体的精确库存（1-4件）
        """
        if variant.stock_status != 'LowStock':
            return None

        cart_params = cart_params or {}
        size_id = str(cart_params.get('size_id') or cart_params.get('sizeId') or '').strip()
        colour_id = str(cart_params.get('colour_id') or cart_params.get('colourId') or variant.color_id or '').strip()
        variant_sku = variant.variant_sku

        if not (variant_sku and size_id and colour_id):
            logger.debug(f"缺少购物车参数，无法获取精确库存: SKU={variant_sku}")
            return None

        async def call_cart_api(endpoint: str, method: str = 'POST', payload: Optional[dict] = None, fallback: Optional[str] = None) -> Optional[dict]:
            try:
                result = await page.evaluate(self.CART_FETCH_SCRIPT, {
                    'endpoint': endpoint,
                    'payload': payload,
                    'method': method
                })
            except Exception as e:
                logger.debug(f"调用 {endpoint} 失败: {e}")
                result = None

            if (not result or not result.get('ok')) and fallback:
                try:
                    result = await page.evaluate(self.CART_FETCH_SCRIPT, {
                        'endpoint': endpoint,
                        'payload': payload,
                        'method': fallback
                    })
                except Exception as e:
                    logger.debug(f"调用 {endpoint}({fallback}) 失败: {e}")
                    result = None

            if not result or not result.get('ok'):
                return None

            data = result.get('data')
            return data if isinstance(data, dict) else {}

        def unwrap_cart(data: Optional[dict]) -> dict:
            if not isinstance(data, dict):
                return {}
            result = data.get('result')
            if isinstance(result, dict):
                nested = result.get('data', {})
                json_payload = nested.get('json')
                if isinstance(json_payload, dict):
                    return json_payload
            return data

        def find_line_item(data: dict) -> Optional[dict]:
            payload = unwrap_cart(data)
            cart_body = payload.get('cart') if isinstance(payload.get('cart'), dict) else payload
            items = cart_body.get('lineItems') or cart_body.get('items') or []
            if not isinstance(items, list):
                return None
            for item in items:
                if not isinstance(item, dict):
                    continue
                sku = str(item.get('variantSku') or item.get('variantId') or item.get('id') or '')
                if sku == variant_sku:
                    return item
            return None

        def extract_quantity(line_item: dict, fallback: int) -> int:
            for key in ('quantity', 'qty', 'count', 'lineItemQty', 'lineItemQuantity'):
                value = line_item.get(key)
                if value is None:
                    continue
                try:
                    return int(value)
                except (ValueError, TypeError):
                    try:
                        return int(float(value))
                    except (ValueError, TypeError):
                        continue
            return fallback

        logger.info(f"尝试获取精确库存: SKU={variant_sku}, 尺寸={variant.size}, 颜色={variant.color_name or colour_id}")

        # 确保购物车为空，避免历史数据干扰
        await call_cart_api('/api/cart.clear', method='POST')

        max_attempts = 4
        last_known_quantity: Optional[int] = None

        try:
            for attempt in range(1, max_attempts + 1):
                add_payload = {
                    'variantSku': variant_sku,
                    'sizeId': size_id,
                    'colourId': colour_id,
                    'quantity': 1
                }
                add_result = await call_cart_api('/api/cart.add', method='POST', payload=add_payload)
                if add_result is None:
                    logger.warning(f"添加购物车失败，无法获取精确库存: SKU={variant_sku}")
                    break

                cart_state = await call_cart_api('/api/cart.get', method='GET', fallback='POST')
                if cart_state is None:
                    logger.warning(f"获取购物车状态失败，无法计算精确库存: SKU={variant_sku}")
                    break

                line_item = find_line_item(cart_state)
                if not line_item:
                    logger.warning(f"购物车中未找到目标变体: SKU={variant_sku}")
                    break

                current_qty = extract_quantity(line_item, attempt)
                last_known_quantity = current_qty
                has_limit = bool(line_item.get('hasReachedStockLimit'))
                insufficient = bool(line_item.get('hasInsufficientStock'))

                logger.debug(f"购物车状态: SKU={variant_sku}, qty={current_qty}, limit={has_limit}, insufficient={insufficient}")

                if has_limit or insufficient:
                    logger.info(f"精确库存确认: SKU={variant_sku}, qty={current_qty}")
                    return current_qty

            if last_known_quantity:
                logger.info(f"未检测到库存上限信号，返回已知数量: SKU={variant_sku}, qty={last_known_quantity}")
            else:
                logger.warning(f"无法获取精确库存，返回未知: SKU={variant_sku}")
            return last_known_quantity
        finally:
            await call_cart_api('/api/cart.clear', method='POST')

    async def _check_inventory_once(self, product_url: str) -> Optional[ProductInventory]:
        """
        单次检查商品库存 - 使用 Playwright 浏览器

        Args:
            product_url: 商品页面URL

        Returns:
            ProductInventory 或 None（失败时）
        """
        from playwright.async_api import async_playwright

        logger.info(f"正在检查库存: {product_url}")

        # 提取SKU
        model_sku = self._extract_sku_from_url(product_url)
        if not model_sku:
            logger.error(f"无法从URL提取SKU: {product_url}")
            return None

        logger.info(f"SKU: {model_sku}")

        browser = None
        playwright_instance = None
        try:
            playwright_instance = await async_playwright().start()

            # 启动浏览器时添加反检测参数
            # 注意：Arc'teryx 网站会检测 headless 模式
            # 在 Docker 中使用 Xvfb 虚拟显示，在本地使用非 headless 模式
            browser_args = [
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-setuid-sandbox',
            ]

            # 检查是否有 DISPLAY 环境变量（Docker + Xvfb 环境）
            import os
            has_display = os.environ.get('DISPLAY') is not None

            if self.is_docker and has_display:
                # Docker 环境 + Xvfb：使用非 headless 模式（虚拟显示）
                logger.info(f"Docker 环境 (DISPLAY={os.environ.get('DISPLAY')})：使用 Xvfb 虚拟显示")
                browser = await playwright_instance.chromium.launch(
                    headless=False,
                    args=browser_args
                )
            elif self.is_docker:
                # Docker 环境无 Xvfb：尝试 headless 模式
                logger.info("Docker 环境：使用 headless 模式")
                browser = await playwright_instance.chromium.launch(
                    headless=True,
                    args=browser_args
                )
            else:
                # 本地环境：使用非 headless 模式，窗口移到屏幕外
                logger.info("本地环境：使用非 headless 模式")
                browser_args.append('--window-position=-10000,-10000')
                browser = await playwright_instance.chromium.launch(
                    headless=False,
                    args=browser_args
                )

            # 创建一个带有美国地区伪装的浏览器上下文
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York',
                # 设置地理位置为美国
                geolocation={'latitude': 40.7128, 'longitude': -74.0060},
                permissions=['geolocation']
            )

            # 移除 webdriver 标记
            await context.add_init_script('''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            ''')

            page = await context.new_page()
            page.set_default_timeout(90000)  # 90秒超时

            # 监听网络请求，拦截库存API响应
            stock_data = {}

            async def handle_response(response):
                nonlocal stock_data
                if 'getVariantStockStatus' in response.url:
                    try:
                        data = await response.json()
                        # 提取 variantStockStatuses 数组并转换为字典
                        statuses = data.get('result', {}).get('data', {}).get('json', {}).get('variantStockStatuses', [])
                        stock_data = {item['variantSku']: {'stockStatus': item['stockStatus']} for item in statuses}
                        logger.info(f"捕获到库存API响应: {len(stock_data)} 个变体")
                    except Exception as e:
                        logger.warning(f"解析库存API响应失败: {e}")

            page.on('response', handle_response)

            logger.info("正在加载页面...")
            # 使用 domcontentloaded 等待策略
            await page.goto(product_url, wait_until='domcontentloaded', timeout=60000)

            # 等待 __NEXT_DATA__ 元素出现
            try:
                await page.wait_for_selector('#__NEXT_DATA__', state='attached', timeout=10000)
                logger.info("检测到 __NEXT_DATA__ 元素")
            except Exception:
                logger.warning("未检测到 __NEXT_DATA__ 元素，继续尝试...")

            # 等待页面基本稳定
            await asyncio.sleep(3)

            # 尝试从页面获取数据
            logger.info("尝试从页面提取产品数据...")
            product_data = await page.evaluate('''() => {
                // 方法1: 从 __NEXT_DATA__ 获取
                const nextData = document.getElementById('__NEXT_DATA__');
                if (nextData) {
                    try {
                        const data = JSON.parse(nextData.textContent);
                        const product = data?.props?.pageProps?.product;
                        if (product) {
                            if (typeof product === 'string') {
                                return JSON.parse(product);
                            }
                            return product;
                        }
                    } catch (e) {
                        console.error('解析 __NEXT_DATA__ 失败:', e);
                    }
                }

                // 方法2: 从 window 对象获取
                if (window.__NUXT__) {
                    return window.__NUXT__?.data?.product || null;
                }

                // 方法3: 尝试从页面结构获取
                const productInfo = {
                    name: document.querySelector('h1')?.textContent?.trim() || '',
                    variants: []
                };

                // 获取尺寸按钮
                const sizeButtons = document.querySelectorAll('[data-testid="size-selector"] button, .size-selector button');
                sizeButtons.forEach(btn => {
                    productInfo.variants.push({
                        size: btn.textContent?.trim(),
                        available: !btn.disabled && !btn.classList.contains('out-of-stock')
                    });
                });

                return productInfo.name ? productInfo : null;
            }''')

            if not product_data and not stock_data:
                logger.warning("无法从页面获取数据，尝试等待更长时间...")
                await asyncio.sleep(5)

                # 再次尝试获取
                product_data = await page.evaluate('''() => {
                    const nextData = document.getElementById('__NEXT_DATA__');
                    if (nextData) {
                        try {
                            const data = JSON.parse(nextData.textContent);
                            const product = data?.props?.pageProps?.product;
                            if (typeof product === 'string') {
                                return JSON.parse(product);
                            }
                            return product;
                        } catch (e) {}
                    }
                    return null;
                }''')

            # 获取当前URL以检查是否被重定向
            current_url = page.url
            logger.info(f"当前页面URL: {current_url}")

            if 'arcteryx.com/cn' in current_url:
                logger.warning("页面被重定向到中国站点，可能需要VPN访问美国站")

            # 构建库存信息
            variants = []
            product_name = ''
            variant_cart_params: Dict[str, Dict[str, str]] = {}

            if product_data:
                product_name = product_data.get('name', '')

                # 构建尺寸映射 - 处理不同的数据结构
                size_options = product_data.get('sizeOptions', {})
                if isinstance(size_options, dict):
                    options_list = size_options.get('options', [])
                elif isinstance(size_options, list):
                    options_list = size_options
                else:
                    options_list = []

                size_map = {}
                for opt in options_list:
                    if isinstance(opt, dict):
                        size_map[opt.get('value', '')] = opt.get('label', '')

                # 构建颜色映射 - 处理不同的数据结构
                colour_options = product_data.get('colourOptions', {})
                if isinstance(colour_options, dict):
                    colour_options_list = colour_options.get('options', [])
                elif isinstance(colour_options, list):
                    colour_options_list = colour_options
                else:
                    colour_options_list = []

                colour_map = {}
                for opt in colour_options_list:
                    if isinstance(opt, dict):
                        colour_map[str(opt.get('value', ''))] = opt.get('label', '')

                # 优先使用捕获的API数据
                if stock_data:
                    for variant_sku, stock_info in stock_data.items():
                        stock_status = stock_info.get('stockStatus', 'OutOfStock')
                        size = 'Unknown'
                        color_id = ''
                        color_name = ''
                        for variant in product_data.get('variants', []):
                            if variant.get('id') == variant_sku:
                                size_id = variant.get('sizeId', '')
                                size = size_map.get(size_id, size_id)
                                # 提取颜色信息
                                color_id = str(variant.get('colourId', ''))
                                colour_alternate_views = variant.get('colourAlternateViews') or []
                                colour_label = ''
                                if colour_alternate_views and isinstance(colour_alternate_views[0], dict):
                                    colour_label = colour_alternate_views[0].get('colourLabel', '')
                                color_name = colour_map.get(color_id, colour_label)
                                break

                        variants.append(VariantStock(
                            variant_sku=variant_sku,
                            size=size,
                            stock_status=stock_status,
                            color_id=color_id,
                            color_name=color_name
                        ))
                        variant_cart_params[variant_sku] = {
                            'size_id': str(size_id),
                            'colour_id': color_id
                        }
                else:
                    # 使用页面数据
                    for variant in product_data.get('variants', []):
                        variant_sku = variant.get('id', '')
                        size_id = variant.get('sizeId', '')
                        size = size_map.get(size_id, size_id)
                        stock_status = variant.get('stockStatus', 'OutOfStock')
                        # 提取颜色信息
                        color_id = str(variant.get('colourId', ''))
                        colour_alternate_views = variant.get('colourAlternateViews') or []
                        colour_label = ''
                        if colour_alternate_views and isinstance(colour_alternate_views[0], dict):
                            colour_label = colour_alternate_views[0].get('colourLabel', '')
                        color_name = colour_map.get(color_id, colour_label)

                        variants.append(VariantStock(
                            variant_sku=variant_sku,
                            size=size,
                            stock_status=stock_status,
                            color_id=color_id,
                            color_name=color_name
                        ))
                        variant_cart_params[variant_sku] = {
                            'size_id': str(size_id),
                            'colour_id': color_id
                        }
            elif stock_data:
                # 只有API数据，没有产品数据
                for variant_sku, stock_info in stock_data.items():
                    variants.append(VariantStock(
                        variant_sku=variant_sku,
                        size=variant_sku[-3:],  # 使用SKU后缀作为临时尺寸标识
                        stock_status=stock_info.get('stockStatus', 'OutOfStock')
                    ))

            if not variants:
                logger.error("无法获取任何库存数据")
                return None

            # 按尺寸排序
            variants.sort(key=lambda v: self.SIZE_ORDER.get(v.size, 99))

            # 对 LowStock 变体补充精确库存
            for variant in variants:
                if variant.stock_status == 'LowStock':
                    params = variant_cart_params.get(variant.variant_sku)
                    quantity = await self.get_exact_quantity(page, variant, params)
                    if quantity is not None:
                        variant.quantity = quantity

            inventory = ProductInventory(
                model_sku=model_sku,
                name=product_name or "Unknown Product",
                url=product_url,
                variants=variants,
                check_time=datetime.now()
            )

            logger.info(f"库存检查完成: {inventory.name}")
            logger.info(f"有库存: {inventory.get_available_sizes()}")
            logger.info(f"无库存: {inventory.get_out_of_stock_sizes()}")

            return inventory

        except Exception as e:
            logger.error(f"检查库存失败: {type(e).__name__}: {e}")
            return None
        finally:
            if browser:
                await browser.close()
            if playwright_instance:
                await playwright_instance.stop()

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

        # 构建旧状态映射，使用 (颜色, 尺寸) 作为 key
        old_status_map = {(v.color_name, v.size): v.stock_status for v in old_inventory.variants}

        # 比较每个变体的库存状态
        for variant in new_inventory.variants:
            key = (variant.color_name, variant.size)
            old_status = old_status_map.get(key, 'Unknown')
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
                    f"库存变化: {variant.color_name} {variant.size} - {old_status} -> {new_status}"
                    f" ({'补货了!' if not was_available and is_available else '售罄了'})"
                )

        return changes


# 创建抓取器单例
inventory_scraper = ArcteryxInventoryScraper()


async def check_product_inventory(product_url: str) -> Optional[ProductInventory]:
    """检查商品库存（模块级函数）"""
    return await inventory_scraper.check_inventory(product_url)
