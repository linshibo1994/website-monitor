"""
网页抓取模块 - 三重检测机制
负责从 SCHEELS 网站抓取 Arc'teryx 商品数据
"""
import re
import asyncio
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass
from datetime import datetime
from playwright.async_api import async_playwright, Page, Browser, TimeoutError as PlaywrightTimeout
from loguru import logger

from ..config import get_config


# 历史记录：用于数据合理性检查
_last_successful_count: int = 0


@dataclass
class ProductInfo:
    """商品信息数据类"""
    product_id: str           # 商品ID
    name: str                 # 商品名称
    price: Optional[float]    # 当前价格
    original_price: Optional[float]  # 原价
    is_on_sale: bool          # 是否促销
    url: str                  # 商品链接


@dataclass
class ScrapeResult:
    """抓取结果数据类"""
    success: bool                     # 是否成功
    total_count: int                  # 商品总数
    products: List[ProductInfo]       # 商品列表
    detection_method: str             # 检测方法
    error_message: Optional[str]      # 错误信息
    duration_seconds: float           # 耗时


class ScheelsScraper:
    """SCHEELS 网站抓取器"""

    # 最大重试次数
    MAX_RETRIES = 3
    # 数据异常阈值：如果获取数量低于上次的这个比例，认为数据异常
    ANOMALY_THRESHOLD = 0.7

    def __init__(self):
        self.config = get_config()
        self.browser: Optional[Browser] = None
        self.base_url = "https://www.scheels.com"

    async def _init_browser(self) -> Browser:
        """初始化浏览器"""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=self.config.monitor.headless
        )
        return browser

    async def _create_page(self, browser: Browser) -> Page:
        """创建页面并设置"""
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        # 设置超时
        page.set_default_timeout(self.config.monitor.timeout_seconds * 1000)
        return page

    async def scrape(self) -> ScrapeResult:
        """
        执行抓取（带重试机制）
        """
        global _last_successful_count
        start_time = datetime.now()

        for attempt in range(1, self.MAX_RETRIES + 1):
            logger.info(f"开始第 {attempt}/{self.MAX_RETRIES} 次抓取尝试")

            result = await self._do_scrape()

            if not result.success:
                logger.warning(f"第 {attempt} 次抓取失败: {result.error_message}")
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(5)  # 等待后重试
                continue

            # 数据合理性检查
            if self._is_data_anomaly(result.total_count):
                logger.warning(
                    f"第 {attempt} 次抓取数据异常: 获取={result.total_count}, "
                    f"上次成功={_last_successful_count}, 阈值={self.ANOMALY_THRESHOLD}"
                )
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(5)  # 等待后重试
                continue

            # 抓取成功且数据合理
            _last_successful_count = result.total_count
            logger.info(f"抓取成功: 总数={result.total_count}, 尝试次数={attempt}")

            # 更新耗时（包含重试时间）
            result.duration_seconds = (datetime.now() - start_time).total_seconds()
            return result

        # 所有重试都失败
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(f"抓取失败: 已重试 {self.MAX_RETRIES} 次")

        return ScrapeResult(
            success=False,
            total_count=0,
            products=[],
            detection_method="all_retries_failed",
            error_message=f"抓取失败: 已重试 {self.MAX_RETRIES} 次",
            duration_seconds=duration
        )

    def _is_data_anomaly(self, count: int) -> bool:
        """
        检查数据是否异常
        - 如果没有历史记录，count > 0 就认为正常
        - 如果有历史记录，count 需要 >= 上次数量 * 阈值
        """
        global _last_successful_count

        if count == 0:
            return True  # 0 总是异常的

        if _last_successful_count == 0:
            return False  # 没有历史记录，只要 > 0 就认为正常

        # 检查是否低于阈值
        threshold = _last_successful_count * self.ANOMALY_THRESHOLD
        if count < threshold:
            return True

        return False

    async def _do_scrape(self) -> ScrapeResult:
        """
        执行单次抓取（三重检测机制）
        """
        start_time = datetime.now()
        browser = None

        try:
            browser = await self._init_browser()
            page = await self._create_page(browser)

            # 访问目标页面
            logger.info(f"正在访问: {self.config.monitor.url}")
            await page.goto(self.config.monitor.url, wait_until='networkidle')

            # 等待页面加载（增加等待时间）
            await asyncio.sleep(3)

            # 方法1：尝试从 "Showing X of Y" 获取总数
            total_count, method = await self._get_total_count_primary(page)

            if total_count == 0:
                # 方法2：备选方法 - 通过加载全部商品计数
                logger.warning("主方法获取总数失败，尝试备选方法")
                total_count, method = await self._get_total_count_fallback(page)

            # 记录页面显示的总数
            expected_total = total_count
            logger.info(f"页面显示总数: {expected_total}")

            # 方法3：获取所有商品详情（精确方法），传入期望总数
            products = await self._get_all_products(page, expected_total)

            # 使用实际获取的商品数量作为最终结果
            actual_count = len(products)

            if actual_count != expected_total:
                logger.warning(f"商品数量不一致: 页面显示={expected_total}, 实际获取={actual_count}")
                # 以实际获取的商品数量为准（更准确）
                if actual_count > 0:
                    total_count = actual_count
                    method = "product_list_actual"

            duration = (datetime.now() - start_time).total_seconds()

            logger.info(f"单次抓取完成: 总数={total_count}, 商品详情={len(products)}条, 耗时={duration:.2f}秒")

            return ScrapeResult(
                success=True,
                total_count=total_count,
                products=products,
                detection_method=method,
                error_message=None,
                duration_seconds=duration
            )

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            error_msg = f"抓取失败: {str(e)}"
            logger.error(error_msg)

            return ScrapeResult(
                success=False,
                total_count=0,
                products=[],
                detection_method="failed",
                error_message=error_msg,
                duration_seconds=duration
            )

        finally:
            if browser:
                await browser.close()

    async def _get_total_count_primary(self, page: Page) -> Tuple[int, str]:
        """
        主方法：从 "Showing X of Y" 文本获取总数
        """
        try:
            # 等待包含 "Showing" 的元素出现
            selectors = [
                'text=/Showing \\d+ of \\d+/',
                '[class*="showing"]',
                'h2:has-text("Showing")',
                'p:has-text("Showing")',
            ]

            for selector in selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=5000)
                    if element:
                        text = await element.text_content()
                        if text:
                            # 匹配 "Showing X of Y" 格式
                            match = re.search(r'Showing\s+(\d+)\s+of\s+(\d+)', text)
                            if match:
                                total = int(match.group(2))
                                logger.info(f"主方法成功: Showing {match.group(1)} of {total}")
                                return total, "primary_showing_text"
                except:
                    continue

            # 尝试直接获取页面文本
            page_text = await page.content()
            match = re.search(r'Showing\s+(\d+)\s+of\s+(\d+)', page_text)
            if match:
                total = int(match.group(2))
                logger.info(f"主方法成功(页面文本): Showing {match.group(1)} of {total}")
                return total, "primary_page_content"

            return 0, "primary_failed"

        except Exception as e:
            logger.warning(f"主方法获取总数失败: {e}")
            return 0, "primary_failed"

    async def _get_total_count_fallback(self, page: Page) -> Tuple[int, str]:
        """
        备选方法：点击 Load More 加载全部后统计卡片数量
        """
        try:
            # 循环点击 Load More 按钮直到消失
            load_more_clicks = 0
            max_clicks = 20  # 防止无限循环

            while load_more_clicks < max_clicks:
                try:
                    load_more_btn = await page.wait_for_selector(
                        'button:has-text("Load More")',
                        timeout=3000
                    )
                    if load_more_btn and await load_more_btn.is_visible():
                        await load_more_btn.click()
                        load_more_clicks += 1
                        logger.debug(f"点击 Load More 按钮: 第{load_more_clicks}次")
                        await asyncio.sleep(1.5)  # 等待加载
                    else:
                        break
                except PlaywrightTimeout:
                    # 按钮不存在或已消失，说明加载完成
                    break
                except Exception as e:
                    logger.warning(f"点击 Load More 出错: {e}")
                    break

            # 统计商品卡片数量
            cards = await page.query_selector_all('article')
            count = len(cards)

            if count > 0:
                logger.info(f"备选方法成功: 统计到 {count} 个商品卡片")
                return count, "fallback_card_count"

            # 尝试其他选择器
            alt_selectors = [
                '[data-testid="product-card"]',
                '.product-card',
                '[class*="ProductCard"]',
                'li article',
            ]

            for selector in alt_selectors:
                cards = await page.query_selector_all(selector)
                if cards:
                    count = len(cards)
                    logger.info(f"备选方法成功({selector}): 统计到 {count} 个商品卡片")
                    return count, f"fallback_{selector}"

            return 0, "fallback_failed"

        except Exception as e:
            logger.warning(f"备选方法获取总数失败: {e}")
            return 0, "fallback_failed"

    async def _get_all_products(self, page: Page, expected_total: int = 0) -> List[ProductInfo]:
        """
        获取所有商品详情（精确方法）

        Args:
            page: Playwright 页面对象
            expected_total: 期望的商品总数
        """
        products = []

        try:
            # 先确保所有商品都已加载
            await self._load_all_products(page, expected_total)

            # 获取所有商品卡片
            cards = await page.query_selector_all('article')

            if not cards:
                # 尝试其他选择器
                cards = await page.query_selector_all('[data-testid="product-card"]')

            logger.info(f"找到 {len(cards)} 个商品卡片，开始提取详情")

            for card in cards:
                try:
                    product = await self._extract_product_info(card)
                    if product:
                        products.append(product)
                except Exception as e:
                    logger.debug(f"提取商品信息失败: {e}")
                    continue

            logger.info(f"成功提取 {len(products)} 个商品详情")

        except Exception as e:
            logger.error(f"获取商品详情失败: {e}")

        return products

    async def _load_all_products(self, page: Page, expected_total: int = 0):
        """
        加载所有商品（持续点击 Load More 直到加载完成）

        Args:
            page: Playwright 页面对象
            expected_total: 期望的商品总数（用于验证是否加载完成）
        """
        max_clicks = 20  # 最大点击次数
        clicks = 0
        last_count = 0
        no_change_count = 0  # 连续无变化计数

        logger.info(f"开始加载全部商品，期望总数: {expected_total}")

        # 先等待初始商品加载
        await asyncio.sleep(2)

        while clicks < max_clicks:
            # 获取当前商品数量
            current_cards = await page.query_selector_all('article')
            current_count = len(current_cards)

            logger.info(f"当前已加载商品数: {current_count}/{expected_total}")

            # 如果已达到期望总数，停止加载
            if expected_total > 0 and current_count >= expected_total:
                logger.info(f"已加载全部商品: {current_count}/{expected_total}")
                break

            # 检查是否有变化
            if current_count == last_count:
                no_change_count += 1
                if no_change_count >= 5:  # 连续5次无变化才停止
                    logger.info(f"连续5次无新增商品，停止加载 (当前: {current_count})")
                    break
            else:
                no_change_count = 0
                last_count = current_count

            # 滚动到页面底部
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await asyncio.sleep(2)

            # 使用 JavaScript 查找并点击 Load More 按钮（更可靠）
            try:
                # 先检查按钮是否存在并可见
                button_info = await page.evaluate('''() => {
                    const buttons = document.querySelectorAll('button');
                    for (const btn of buttons) {
                        if (btn.textContent && btn.textContent.includes('Load More')) {
                            const rect = btn.getBoundingClientRect();
                            const isVisible = rect.top >= 0 && rect.bottom <= window.innerHeight;
                            return {
                                exists: true,
                                visible: isVisible,
                                text: btn.textContent.trim()
                            };
                        }
                    }
                    return { exists: false, visible: false, text: '' };
                }''')

                if button_info['exists']:
                    # 滚动到按钮位置并点击
                    clicked = await page.evaluate('''() => {
                        const buttons = document.querySelectorAll('button');
                        for (const btn of buttons) {
                            if (btn.textContent && btn.textContent.includes('Load More')) {
                                btn.scrollIntoView({behavior: 'instant', block: 'center'});
                                return true;
                            }
                        }
                        return false;
                    }''')

                    if clicked:
                        await asyncio.sleep(0.5)  # 等待滚动完成

                        # 执行点击
                        await page.evaluate('''() => {
                            const buttons = document.querySelectorAll('button');
                            for (const btn of buttons) {
                                if (btn.textContent && btn.textContent.includes('Load More')) {
                                    btn.click();
                                    return true;
                                }
                            }
                            return false;
                        }''')

                        clicks += 1
                        logger.info(f"点击 Load More 按钮: 第{clicks}次")

                        # 等待新内容加载（增加等待时间）
                        await asyncio.sleep(4)
                else:
                    # 没有找到按钮，可能已加载完成
                    logger.debug("未找到 Load More 按钮")
                    no_change_count += 1
                    await asyncio.sleep(2)

            except Exception as e:
                logger.warning(f"点击 Load More 出错: {e}")
                no_change_count += 1
                await asyncio.sleep(2)

        # 最终统计
        final_cards = await page.query_selector_all('article')
        logger.info(f"加载完成: 点击了 {clicks} 次 Load More, 最终商品数: {len(final_cards)}")

    async def _extract_product_info(self, card) -> Optional[ProductInfo]:
        """从商品卡片提取商品信息"""
        try:
            # 提取商品链接和ID
            link_element = await card.query_selector('a[href*="/p/"]')
            if not link_element:
                return None

            href = await link_element.get_attribute('href')
            if not href:
                return None

            # 从 URL 提取商品ID
            match = re.search(r'/p/(\d+)', href)
            if not match:
                return None

            product_id = match.group(1)
            url = f"{self.base_url}{href}" if href.startswith('/') else href

            # 提取商品名称
            name = ""
            name_selectors = ['h2', 'h3', '[class*="name"]', '[class*="title"]']
            for selector in name_selectors:
                name_element = await card.query_selector(selector)
                if name_element:
                    name = await name_element.text_content()
                    if name:
                        name = name.strip()
                        break

            if not name:
                # 尝试从链接的 aria-label 或 title 获取
                name = await link_element.get_attribute('aria-label') or ""
                if not name:
                    name = await link_element.get_attribute('title') or f"Product {product_id}"

            # 提取价格
            price = None
            original_price = None
            is_on_sale = False

            # 查找价格元素
            price_text = await card.text_content() or ""

            # 匹配价格格式 $XXX.XX
            prices = re.findall(r'\$(\d+(?:\.\d{2})?)', price_text)

            if prices:
                # 如果有多个价格，可能是原价和促销价
                prices = [float(p) for p in prices]
                prices = sorted(set(prices))  # 去重并排序

                if len(prices) >= 2:
                    price = min(prices)  # 最低价为当前价
                    original_price = max(prices)  # 最高价为原价
                    is_on_sale = True
                else:
                    price = prices[0]

            # 检查是否有促销标记
            sale_indicators = ['Sale', 'New Low Price', '% Off']
            for indicator in sale_indicators:
                if indicator.lower() in price_text.lower():
                    is_on_sale = True
                    break

            return ProductInfo(
                product_id=product_id,
                name=name,
                price=price,
                original_price=original_price,
                is_on_sale=is_on_sale,
                url=url
            )

        except Exception as e:
            logger.debug(f"提取商品信息出错: {e}")
            return None

    async def quick_check(self) -> Tuple[int, str]:
        """
        快速检查：只获取商品总数，不获取详情
        用于频繁检测场景
        """
        browser = None
        try:
            browser = await self._init_browser()
            page = await self._create_page(browser)

            await page.goto(self.config.monitor.url, wait_until='networkidle')
            await asyncio.sleep(2)

            # 只使用主方法获取总数
            total_count, method = await self._get_total_count_primary(page)

            if total_count == 0:
                total_count, method = await self._get_total_count_fallback(page)

            return total_count, method

        except Exception as e:
            logger.error(f"快速检查失败: {e}")
            return 0, "error"

        finally:
            if browser:
                await browser.close()


# 创建抓取器单例
scraper = ScheelsScraper()


def init_last_successful_count(count: int):
    """
    初始化历史成功计数（从数据库加载）
    应该在服务启动时调用
    """
    global _last_successful_count
    if count > 0:
        _last_successful_count = count
        logger.info(f"初始化历史成功计数: {count}")


async def scrape_products() -> ScrapeResult:
    """抓取商品（模块级函数）"""
    return await scraper.scrape()


async def quick_check_count() -> Tuple[int, str]:
    """快速检查商品数量（模块级函数）"""
    return await scraper.quick_check()
