"""
智能URL解析服务
支持从完整URL、商品Key自动识别站点和构建URL
"""
import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from urllib.parse import urlparse
from loguru import logger

from ..config import get_config, SiteConfig


@dataclass
class ParseResult:
    """解析结果"""
    success: bool  # 是否解析成功
    site_id: Optional[str] = None  # 站点ID
    site_name: Optional[str] = None  # 站点名称
    key: Optional[str] = None  # 商品Key
    category: Optional[str] = None  # 分类
    url: Optional[str] = None  # 完整URL
    input_type: Optional[str] = None  # 输入类型: url / key / unknown
    error: Optional[str] = None  # 错误信息
    categories: Optional[List[Dict[str, str]]] = None  # 可选分类列表

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'success': self.success,
            'site_id': self.site_id,
            'site_name': self.site_name,
            'key': self.key,
            'category': self.category,
            'url': self.url,
            'input_type': self.input_type,
            'error': self.error,
            'categories': self.categories,
        }


class URLParser:
    """智能URL解析器（无状态，每次操作获取最新配置）"""

    @property
    def _config(self):
        """每次访问时获取最新配置，支持热加载"""
        return get_config()

    def get_sites(self) -> List[Dict[str, Any]]:
        """获取所有站点配置"""
        return [site.to_dict() for site in self._config.sites.values()]

    def get_site(self, site_id: str) -> Optional[SiteConfig]:
        """获取指定站点配置"""
        return self._config.sites.get(site_id)

    def parse(self, input_str: str) -> ParseResult:
        """
        智能解析用户输入

        支持：
        1. 完整URL（自动识别站点）
        2. 商品Key（遍历所有站点配置进行匹配）
        """
        input_str = input_str.strip()

        if not input_str:
            return ParseResult(success=False, error="输入不能为空")

        # 1. 检查是否为完整URL
        if input_str.startswith('http://') or input_str.startswith('https://'):
            return self._parse_url(input_str)

        # 2. 尝试匹配所有站点的Key格式（遍历配置而非硬编码）
        return self._parse_key_auto(input_str)

    def _parse_url(self, url: str) -> ParseResult:
        """解析完整URL（使用urlparse提取真实域名）"""
        try:
            parsed_url = urlparse(url)
            hostname = parsed_url.netloc.lower()

            # 遍历所有站点，使用域名后缀匹配（更安全）
            for site_id, site in self._config.sites.items():
                # 使用 endswith 确保是真实域名，而非 URL 中的子串
                if hostname.endswith(site.domain) or hostname == site.domain:
                    # 找到匹配的站点，尝试解析
                    parsed = site.parse_url(url)
                    if parsed:
                        # 构建完整URL（标准化）
                        full_url = site.build_url(parsed['key'], parsed['category'])

                        # 检查构建的URL是否有效
                        if not full_url:
                            return ParseResult(
                                success=False,
                                site_id=site_id,
                                site_name=site.name,
                                input_type='url',
                                error=f"无法构建商品URL，请检查站点配置"
                            )

                        # 获取可选分类
                        categories = [{'value': c.value, 'label': c.label} for c in site.categories]

                        return ParseResult(
                            success=True,
                            site_id=site_id,
                            site_name=site.name,
                            key=parsed['key'],
                            category=parsed['category'],
                            url=full_url,
                            input_type='url',
                            categories=categories if categories else None
                        )
                    # 域名匹配但解析失败，继续尝试其他站点（可能有多个站点使用相似域名）

            # 未找到匹配的站点
            supported_sites = ', '.join([s.name for s in self._config.sites.values()])
            return ParseResult(
                success=False,
                input_type='url',
                error=f"不支持的站点或无法解析URL。当前支持: {supported_sites}"
            )

        except Exception as e:
            logger.error(f"URL解析异常: {e}")
            return ParseResult(
                success=False,
                input_type='url',
                error=f"URL解析失败: {str(e)}"
            )

    def _parse_key_auto(self, key: str) -> ParseResult:
        """自动识别Key所属站点（遍历所有站点配置）"""
        matched_sites = []

        # 遍历所有站点，使用 validate_key 检查匹配
        for site_id, site in self._config.sites.items():
            if site.validate_key(key):
                matched_sites.append((site_id, site))

        # 没有匹配的站点
        if not matched_sites:
            # 生成所有站点的Key示例
            examples = []
            for site in self._config.sites.values():
                if site.key_example:
                    examples.append(f"{site.name}: {site.key_example}")

            return ParseResult(
                success=False,
                input_type='unknown',
                error=f"无法识别的输入格式。请输入完整URL或商品Key。\n支持的Key格式:\n" +
                      "\n".join(examples) if examples else "无法识别的输入格式"
            )

        # 只有一个匹配，直接使用
        if len(matched_sites) == 1:
            site_id, site = matched_sites[0]
            return self._build_key_result(key, site_id, site)

        # 多个站点匹配同一个Key格式，返回第一个但记录警告
        logger.warning(f"Key '{key}' 匹配多个站点: {[s[0] for s in matched_sites]}，使用第一个")
        site_id, site = matched_sites[0]
        return self._build_key_result(key, site_id, site)

    def _build_key_result(self, key: str, site_id: str, site: SiteConfig) -> ParseResult:
        """构建Key解析结果"""
        # 构建完整URL
        url = site.build_url(key)

        # 检查构建的URL是否有效
        if not url:
            return ParseResult(
                success=False,
                site_id=site_id,
                site_name=site.name,
                key=key,
                input_type='key',
                error=f"无法构建商品URL，请检查站点配置"
            )

        # 获取可选分类
        categories = [{'value': c.value, 'label': c.label} for c in site.categories]

        return ParseResult(
            success=True,
            site_id=site_id,
            site_name=site.name,
            key=key,
            category=site.default_category,
            url=url,
            input_type='key',
            categories=categories if categories else None
        )

    def _parse_key(self, key: str, site_id: str) -> ParseResult:
        """解析指定站点的商品Key"""
        site = self._config.sites.get(site_id)
        if not site:
            return ParseResult(success=False, error=f"未知站点: {site_id}")

        # 验证Key格式
        if not site.validate_key(key):
            return ParseResult(
                success=False,
                site_id=site_id,
                site_name=site.name,
                key=key,
                input_type='key',
                error=f"Key格式不正确。\n示例: {site.key_example}"
            )

        return self._build_key_result(key, site_id, site)

    def build_url(self, site_id: str, key: str, category: str = None) -> Optional[str]:
        """根据站点和Key构建完整URL"""
        site = self._config.sites.get(site_id)
        if not site:
            return None
        url = site.build_url(key, category)
        # 返回非空URL
        return url if url else None

    def validate_key(self, site_id: str, key: str) -> bool:
        """验证Key格式"""
        site = self._config.sites.get(site_id)
        if not site:
            return False
        return site.validate_key(key)


# 创建全局解析器实例（无状态，支持配置热加载）
url_parser = URLParser()


def parse_product_input(input_str: str) -> ParseResult:
    """解析商品输入（模块级函数）"""
    return url_parser.parse(input_str)


def get_supported_sites() -> List[Dict[str, Any]]:
    """获取支持的站点列表（模块级函数）"""
    return url_parser.get_sites()


def build_product_url(site_id: str, key: str, category: str = None) -> Optional[str]:
    """构建商品URL（模块级函数）"""
    return url_parser.build_url(site_id, key, category)
