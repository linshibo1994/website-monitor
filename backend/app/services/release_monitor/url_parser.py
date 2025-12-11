"""
上线监控URL解析器
支持解析 Daytona Park 和 Rakuten 商品URL
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Dict, Any
from urllib.parse import urlparse, parse_qs

from loguru import logger


@dataclass
class ReleaseParseResult:
    """URL解析结果"""
    success: bool
    website_type: Optional[str] = None
    website_name: Optional[str] = None
    product_id: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'success': self.success,
            'website_type': self.website_type,
            'website_name': self.website_name,
            'product_id': self.product_id,
            'url': self.url,
            'error': self.error,
        }


class ReleaseURLParser:
    """上线监控URL解析器"""

    # 支持的网站配置
    WEBSITE_CONFIG = {
        'daytona_park': {
            'name': 'Daytona Park',
            'domains': ['daytona-park.com', 'www.daytona-park.com'],
            'url_patterns': [
                r'/item/(\d+)',  # /item/1064044900562
            ],
        },
        'rakuten': {
            'name': 'Rakuten',
            'domains': ['rakuten.co.jp', 'item.rakuten.co.jp', 'www.rakuten.co.jp'],
            'url_patterns': [
                r'/([^/]+)/([^/]+)/?$',  # /shop-name/item-id
                r'/product/(\d+)',  # /product/123456
            ],
        },
    }

    def parse(self, input_str: str) -> ReleaseParseResult:
        """
        解析用户输入
        支持完整URL
        """
        input_str = input_str.strip()

        if not input_str:
            return ReleaseParseResult(success=False, error="输入不能为空")

        # 检查是否为URL
        if not input_str.startswith('http://') and not input_str.startswith('https://'):
            return ReleaseParseResult(
                success=False,
                error="请输入完整的商品URL（以 http:// 或 https:// 开头）"
            )

        return self._parse_url(input_str)

    def _parse_url(self, url: str) -> ReleaseParseResult:
        """解析URL"""
        try:
            parsed = urlparse(url)
            hostname = parsed.netloc.lower()

            # 遍历支持的网站
            for website_type, config in self.WEBSITE_CONFIG.items():
                # 检查域名是否匹配
                domain_matched = False
                for domain in config['domains']:
                    if hostname == domain or hostname.endswith('.' + domain):
                        domain_matched = True
                        break

                if not domain_matched:
                    continue

                # 尝试从URL路径中提取商品ID
                product_id = self._extract_product_id(parsed.path, config['url_patterns'])

                # 如果路径中没有找到，尝试从查询参数中获取
                if not product_id:
                    query_params = parse_qs(parsed.query)
                    # 常见的ID参数名
                    id_params = ['id', 'item_id', 'product_id', 'itemid', 'pid']
                    for param in id_params:
                        if param in query_params:
                            product_id = query_params[param][0]
                            break

                return ReleaseParseResult(
                    success=True,
                    website_type=website_type,
                    website_name=config['name'],
                    product_id=product_id,
                    url=url,
                )

            # 未找到匹配的网站
            supported = ', '.join([c['name'] for c in self.WEBSITE_CONFIG.values()])
            return ReleaseParseResult(
                success=False,
                error=f"不支持的网站。当前支持: {supported}"
            )

        except Exception as e:
            logger.error(f"URL解析异常: {e}")
            return ReleaseParseResult(
                success=False,
                error=f"URL解析失败: {str(e)}"
            )

    def _extract_product_id(self, path: str, patterns: list) -> Optional[str]:
        """从URL路径中提取商品ID"""
        for pattern in patterns:
            match = re.search(pattern, path)
            if match:
                # 返回第一个捕获组
                return match.group(1)
        return None

    def get_supported_websites(self) -> list:
        """获取支持的网站列表"""
        return [
            {
                'type': wtype,
                'name': config['name'],
                'domains': config['domains'],
            }
            for wtype, config in self.WEBSITE_CONFIG.items()
        ]


# 创建全局解析器实例
release_url_parser = ReleaseURLParser()


def parse_release_url(url: str) -> ReleaseParseResult:
    """解析上线监控URL（模块级函数）"""
    return release_url_parser.parse(url)


def get_supported_release_websites() -> list:
    """获取支持的网站列表（模块级函数）"""
    return release_url_parser.get_supported_websites()
