"""
网站检测器模块
负责检测 Daytona Park 和 Rakuten 商品页面的上线状态和库存信息
"""
from __future__ import annotations

import re
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from loguru import logger


@dataclass
class StockVariant:
    """库存变体信息（尺码/颜色组合）"""
    size: Optional[str] = None
    color: Optional[str] = None
    stock_status: str = "unknown"  # in_stock / low_stock / out_of_stock / unknown
    stock_text: Optional[str] = None  # 原始库存文本


@dataclass
class DetectionResult:
    """检测结果"""
    status: str  # coming_soon / available / unavailable / error
    product_name: Optional[str] = None
    price: Optional[str] = None
    original_price: Optional[str] = None
    scheduled_release: Optional[str] = None  # 预计发售时间
    variants: List[StockVariant] = field(default_factory=list)
    total_in_stock: int = 0
    total_low_stock: int = 0
    total_out_of_stock: int = 0
    error: Optional[str] = None
    raw_html: Optional[str] = None  # 调试用

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'status': self.status,
            'product_name': self.product_name,
            'price': self.price,
            'original_price': self.original_price,
            'scheduled_release': self.scheduled_release,
            'variants': [
                {
                    'size': v.size,
                    'color': v.color,
                    'stock_status': v.stock_status,
                    'stock_text': v.stock_text,
                }
                for v in self.variants
            ],
            'total_in_stock': self.total_in_stock,
            'total_low_stock': self.total_low_stock,
            'total_out_of_stock': self.total_out_of_stock,
            'error': self.error,
        }

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class BaseDetector(ABC):
    """检测器基类"""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
            # 移除 br 编码，避免需要 brotli 库支持
            'Accept-Encoding': 'gzip, deflate',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Ch-Ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"macOS"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        })

    @abstractmethod
    def check(self, url: str) -> DetectionResult:
        """检测页面状态"""
        pass

    @abstractmethod
    def get_website_type(self) -> str:
        """获取网站类型标识"""
        pass

    def _fetch_page(self, url: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
        """获取页面内容，返回 (html, status_code, error)"""
        try:
            response = self.session.get(url, timeout=self.timeout)
            # 检查 HTTP 错误状态码
            if response.status_code >= 400:
                error_msg = f"HTTP {response.status_code}"
                if response.status_code == 403:
                    error_msg = "访问被拒绝(403)"
                elif response.status_code == 404:
                    error_msg = "页面不存在(404)"
                elif response.status_code == 429:
                    error_msg = "请求过于频繁(429)"
                elif response.status_code >= 500:
                    error_msg = f"服务器错误({response.status_code})"
                return None, response.status_code, error_msg
            return response.text, response.status_code, None
        except requests.Timeout:
            return None, None, "请求超时"
        except requests.RequestException as e:
            return None, None, f"请求失败: {str(e)}"


class DaytonaParkDetector(BaseDetector):
    """Daytona Park 网站检测器"""

    # 库存状态CSS类映射
    STOCK_CLASS_MAP = {
        'block-goods-stockstatus-manystock': ('in_stock', '在库あり'),
        'block-goods-stockstatus-lowstock': ('low_stock', '残りわずか'),
        'block-goods-stockstatus-outofstock': ('out_of_stock', '在库なし'),
    }

    def get_website_type(self) -> str:
        return "daytona_park"

    def check(self, url: str) -> DetectionResult:
        """检测 Daytona Park 商品页面"""
        html, status_code, error = self._fetch_page(url)

        if error:
            return DetectionResult(status='error', error=error)

        if not html:
            return DetectionResult(status='error', error='页面内容为空')

        soup = BeautifulSoup(html, 'html.parser')

        # 提取商品名称
        product_name = self._extract_product_name(soup)

        # 提取价格
        price, original_price = self._extract_price(soup)

        # 检测是否为 Coming Soon 状态
        is_coming_soon, scheduled_release = self._check_coming_soon(soup)

        if is_coming_soon:
            return DetectionResult(
                status='coming_soon',
                product_name=product_name,
                price=price,
                original_price=original_price,
                scheduled_release=scheduled_release,
            )

        # 提取库存信息
        variants = self._extract_stock_info(soup)

        # 统计库存
        total_in_stock = sum(1 for v in variants if v.stock_status == 'in_stock')
        total_low_stock = sum(1 for v in variants if v.stock_status == 'low_stock')
        total_out_of_stock = sum(1 for v in variants if v.stock_status == 'out_of_stock')

        # 判断整体状态
        if total_in_stock > 0 or total_low_stock > 0:
            status = 'available'
        elif variants:
            status = 'unavailable'
        else:
            # 没有找到变体信息，检查购买按钮状态
            status = self._check_buy_button_status(soup)

        return DetectionResult(
            status=status,
            product_name=product_name,
            price=price,
            original_price=original_price,
            variants=variants,
            total_in_stock=total_in_stock,
            total_low_stock=total_low_stock,
            total_out_of_stock=total_out_of_stock,
        )

    def _extract_product_name(self, soup: BeautifulSoup) -> Optional[str]:
        """提取商品名称"""
        # 尝试多种选择器
        selectors = [
            'h1.product-name',
            '.product-title',
            'h1[itemprop="name"]',
            '.goods-name',
            'h1',
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)

        # 尝试 og:title
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            return og_title['content'].strip()

        return None

    def _extract_price(self, soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str]]:
        """提取价格，返回 (当前价格, 原价)"""
        price = None
        original_price = None

        # 尝试多种价格选择器
        price_selectors = [
            '.price-box .price',
            '.product-price',
            '[itemprop="price"]',
            '.goods-price',
        ]

        for selector in price_selectors:
            elem = soup.select_one(selector)
            if elem:
                price = elem.get_text(strip=True)
                break

        # 尝试从文本中提取价格
        if not price:
            text = soup.get_text(' ', strip=True)
            # 匹配日元价格格式
            match = re.search(r'[¥￥]\s*([\d,]+)', text)
            if match:
                price = f"¥{match.group(1)}"

        return price, original_price

    def _check_coming_soon(self, soup: BeautifulSoup) -> Tuple[bool, Optional[str]]:
        """检测是否为即将上线状态，返回 (is_coming_soon, scheduled_release)"""
        scheduled_release = None

        # 检测 COMING SOON 按钮
        coming_soon_btn = soup.find('button', disabled=True)
        if coming_soon_btn:
            btn_text = coming_soon_btn.get_text(strip=True).upper()
            if 'COMING SOON' in btn_text:
                # 尝试提取发售时间
                scheduled_release = self._extract_release_time(soup)
                return True, scheduled_release

        # 检测页面中的 COMING SOON 文本
        page_text = soup.get_text(' ', strip=True).upper()
        if 'COMING SOON' in page_text:
            scheduled_release = self._extract_release_time(soup)
            return True, scheduled_release

        return False, None

    def _extract_release_time(self, soup: BeautifulSoup) -> Optional[str]:
        """提取预计发售时间"""
        text = soup.get_text(' ', strip=True)

        # 匹配日期时间格式：12月12日17:00発売 或类似格式
        patterns = [
            r'(\d{1,2}月\d{1,2}日\d{1,2}:\d{2}発売)',
            r'(\d{4}年\d{1,2}月\d{1,2}日)',
            r'(\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2})',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)

        return None

    def _extract_stock_info(self, soup: BeautifulSoup) -> List[StockVariant]:
        """提取库存信息"""
        variants = []

        # 查找所有库存状态元素
        for class_name, (status, text) in self.STOCK_CLASS_MAP.items():
            elements = soup.find_all(class_=class_name)
            for elem in elements:
                # 尝试获取关联的尺码/颜色信息
                parent = elem.find_parent(['tr', 'div', 'li'])
                size = None
                color = None

                if parent:
                    # 尝试从父元素中提取尺码
                    size_elem = parent.find(class_=['size', 'size-name', 'variant-size'])
                    if size_elem:
                        size = size_elem.get_text(strip=True)

                    # 尝试从父元素中提取颜色
                    color_elem = parent.find(class_=['color', 'color-name', 'variant-color'])
                    if color_elem:
                        color = color_elem.get_text(strip=True)

                variants.append(StockVariant(
                    size=size,
                    color=color,
                    stock_status=status,
                    stock_text=text,
                ))

        return variants

    def _check_buy_button_status(self, soup: BeautifulSoup) -> str:
        """通过购买按钮状态判断商品状态"""
        # 查找加入购物车按钮
        add_to_cart = soup.find('button', string=re.compile(r'カートに入れる|ADD TO CART', re.I))
        if add_to_cart:
            if add_to_cart.get('disabled'):
                return 'unavailable'
            return 'available'

        # 查找再入荷通知按钮（缺货时显示）
        restock_notify = soup.find('button', string=re.compile(r'再入荷のお知らせ|NOTIFY', re.I))
        if restock_notify:
            return 'unavailable'

        return 'unavailable'


class RakutenDetector(BaseDetector):
    """乐天网站检测器"""

    def get_website_type(self) -> str:
        return "rakuten"

    def check(self, url: str) -> DetectionResult:
        """检测乐天商品页面"""
        html, status_code, error = self._fetch_page(url)

        if error:
            return DetectionResult(status='error', error=error)

        if not html:
            return DetectionResult(status='error', error='页面内容为空')

        soup = BeautifulSoup(html, 'html.parser')

        # 检测错误页面
        if self._is_error_page(soup):
            return DetectionResult(status='unavailable', error='商品已下架或不存在')

        # 检测 meta refresh 跳转
        has_refresh, target = self._check_meta_refresh(soup)
        if has_refresh and self._is_error_redirect(target):
            return DetectionResult(status='unavailable', error='页面重定向到错误页')

        # 提取商品信息
        product_name = self._extract_product_name(soup)
        price, original_price = self._extract_price(soup)

        # 检测是否为预售/Coming Soon
        is_coming_soon, scheduled_release = self._check_coming_soon(soup)

        if is_coming_soon:
            return DetectionResult(
                status='coming_soon',
                product_name=product_name,
                price=price,
                original_price=original_price,
                scheduled_release=scheduled_release,
            )

        # 检测库存状态
        variants = self._extract_stock_info(soup)
        total_in_stock = sum(1 for v in variants if v.stock_status == 'in_stock')
        total_low_stock = sum(1 for v in variants if v.stock_status == 'low_stock')
        total_out_of_stock = sum(1 for v in variants if v.stock_status == 'out_of_stock')

        # 判断状态
        if total_in_stock > 0 or total_low_stock > 0:
            status = 'available'
        elif variants:
            status = 'unavailable'
        else:
            # 没有变体信息时，检查页面是否显示可购买
            status = 'available' if self._can_purchase(soup) else 'unavailable'

        return DetectionResult(
            status=status,
            product_name=product_name,
            price=price,
            original_price=original_price,
            variants=variants,
            total_in_stock=total_in_stock,
            total_low_stock=total_low_stock,
            total_out_of_stock=total_out_of_stock,
        )

    def _is_error_page(self, soup: BeautifulSoup) -> bool:
        """检测是否为错误页面"""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
            error_keywords = ['エラー', '404', 'Not Found', 'エラーページ', '見つかりません']
            if any(kw in title for kw in error_keywords):
                return True
        return False

    def _check_meta_refresh(self, soup: BeautifulSoup) -> Tuple[bool, Optional[str]]:
        """检测 meta refresh 标签"""
        meta = soup.find('meta', attrs={'http-equiv': lambda v: v and v.lower() == 'refresh'})
        if not meta:
            return False, None

        content = meta.get('content', '')
        parts = content.split('url=', maxsplit=1)
        target = parts[1].strip() if len(parts) == 2 else None
        return True, target

    def _is_error_redirect(self, target: Optional[str]) -> bool:
        """判断重定向目标是否为错误页"""
        if not target:
            return False
        lowered = target.lower()
        return any(kw in lowered for kw in ['error', 'notfound', '404'])

    def _extract_product_name(self, soup: BeautifulSoup) -> Optional[str]:
        """提取商品名称"""
        # 尝试 og:title
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            return og_title['content'].strip()

        # 尝试页面标题
        if soup.title and soup.title.string:
            return soup.title.string.strip()

        # 尝试 h1
        h1 = soup.find('h1')
        if h1:
            return h1.get_text(strip=True)

        return None

    def _extract_price(self, soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str]]:
        """提取价格"""
        price = None
        original_price = None

        # 尝试 og:price:amount
        og_price = soup.find('meta', property='og:price:amount')
        if og_price and og_price.get('content'):
            price = og_price['content'].strip()

        # 尝试其他价格选择器
        if not price:
            selectors = [
                '[itemprop=price]',
                '[data-price]',
                '.price',
                '.ProductPrice',
            ]
            for selector in selectors:
                elem = soup.select_one(selector)
                if elem:
                    price = elem.get('content') or elem.get_text(strip=True)
                    break

        # 从文本中提取
        if not price:
            text = soup.get_text(' ', strip=True)
            match = re.search(r'[¥￥]\s*([\d,]+)', text)
            if match:
                price = f"¥{match.group(1)}"

        return price, original_price

    def _check_coming_soon(self, soup: BeautifulSoup) -> Tuple[bool, Optional[str]]:
        """检测是否为预售状态"""
        page_text = soup.get_text(' ', strip=True)

        # 常见预售关键词
        presale_keywords = ['予約', '先行予約', '発売予定', 'COMING SOON', '近日発売']

        for keyword in presale_keywords:
            if keyword.upper() in page_text.upper():
                # 尝试提取发售日期
                scheduled = self._extract_release_time(page_text)
                return True, scheduled

        return False, None

    def _extract_release_time(self, text: str) -> Optional[str]:
        """提取发售时间"""
        patterns = [
            r'(\d{4}年\d{1,2}月\d{1,2}日)',
            r'(\d{1,2}月\d{1,2}日)',
            r'発売予定[：:]\s*(.+?)(?:\s|$)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)

        return None

    def _extract_stock_info(self, soup: BeautifulSoup) -> List[StockVariant]:
        """提取库存信息"""
        variants = []

        # 乐天的库存信息通常在选择器或表格中
        # 这里实现基本的提取逻辑

        # 查找缺货标记
        sold_out_elements = soup.find_all(string=re.compile(r'売り切れ|在庫切れ|品切れ|SOLD OUT', re.I))
        for elem in sold_out_elements:
            parent = elem.find_parent(['tr', 'div', 'li', 'option'])
            if parent:
                variants.append(StockVariant(
                    stock_status='out_of_stock',
                    stock_text='売り切れ',
                ))

        # 查找有货标记
        in_stock_elements = soup.find_all(string=re.compile(r'在庫あり|残り\d+点', re.I))
        for elem in in_stock_elements:
            parent = elem.find_parent(['tr', 'div', 'li', 'option'])
            text = elem.strip() if isinstance(elem, str) else elem.get_text(strip=True)

            # 判断是充足还是紧张
            if '残り' in text and re.search(r'残り[1-3]点', text):
                status = 'low_stock'
            else:
                status = 'in_stock'

            variants.append(StockVariant(
                stock_status=status,
                stock_text=text,
            ))

        return variants

    def _can_purchase(self, soup: BeautifulSoup) -> bool:
        """检测是否可以购买"""
        # 查找加入购物车按钮
        cart_buttons = soup.find_all(['button', 'input', 'a'],
                                     string=re.compile(r'カートに入れる|買い物かご|購入', re.I))

        for btn in cart_buttons:
            # 检查按钮是否被禁用
            if btn.name == 'button' and btn.get('disabled'):
                continue
            if btn.get('class') and 'disabled' in ' '.join(btn.get('class', [])):
                continue
            return True

        return False


def detect_website_type(url: str) -> Optional[str]:
    """根据URL识别网站类型"""
    parsed = urlparse(url)
    hostname = parsed.netloc.lower()

    if 'daytona-park.com' in hostname:
        return 'daytona_park'
    elif 'rakuten.co.jp' in hostname or 'rakuten.com' in hostname:
        return 'rakuten'

    return None


def get_detector(website_type: str) -> Optional[BaseDetector]:
    """获取对应的检测器实例"""
    detectors = {
        'daytona_park': DaytonaParkDetector,
        'rakuten': RakutenDetector,
    }

    detector_class = detectors.get(website_type)
    if detector_class:
        return detector_class()
    return None
