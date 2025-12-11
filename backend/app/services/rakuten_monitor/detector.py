"""乐天页面检测器，实现可用性判断。"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Tuple

import requests
from bs4 import BeautifulSoup


@dataclass
class DetectionResult:
    """封装检测结果，包含状态与商品信息。"""

    status: str
    info: Dict[str, Any]


class RakutenPageDetector:
    """基于 requests 与 BeautifulSoup 的页面检测器。"""

    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                )
            }
        )

    def check(self, url: str) -> DetectionResult:
        """检测页面可用性并返回状态。"""
        info: Dict[str, Any] = {"url": url}
        try:
            response = self.session.get(url, timeout=self.timeout)
            info["status_code"] = response.status_code
            html = response.text if "text" in response.headers.get("Content-Type", "text") else ""
        except requests.RequestException as exc:
            logging.error("请求页面失败: %s", exc)
            info["error"] = str(exc)
            return DetectionResult(status="unavailable", info=info)

        soup = BeautifulSoup(html, "html.parser") if html else None
        has_error_title = self._has_error_title(soup)
        has_meta_refresh, meta_target = self._has_meta_refresh(soup)
        info["has_meta_refresh"] = has_meta_refresh
        if meta_target:
            info["meta_refresh_target"] = meta_target

        if response.status_code == 404:
            status = "unavailable"
        else:
            status = "available"
            if has_error_title:
                status = "unavailable"
            if has_meta_refresh and self._looks_like_error(meta_target):
                status = "unavailable"

        if status == "available" and soup:
            info.update(self._extract_product_info(soup))
        else:
            info.setdefault("product_name", None)
            info.setdefault("price", None)

        return DetectionResult(status=status, info=info)

    @staticmethod
    def _has_error_title(soup: BeautifulSoup | None) -> bool:
        """检查标题是否包含错误提示。"""
        if not soup or not soup.title or not soup.title.string:
            return False
        title = soup.title.string.strip()
        return any(keyword in title for keyword in ("エラー", "404", "Not Found", "エラーページ"))

    @staticmethod
    def _has_meta_refresh(soup: BeautifulSoup | None) -> Tuple[bool, str | None]:
        """检测 meta refresh 标签并返回跳转地址。"""
        if not soup:
            return False, None
        meta = soup.find("meta", attrs={"http-equiv": lambda value: value and value.lower() == "refresh"})
        if not meta:
            return False, None
        content = meta.get("content", "")
        parts = content.split("url=", maxsplit=1)
        target = parts[1].strip() if len(parts) == 2 else None
        return True, target

    @staticmethod
    def _looks_like_error(target: str | None) -> bool:
        """根据跳转目标关键字判断是否为错误页面。"""
        if not target:
            return False
        lowered = target.lower()
        return any(keyword in lowered for keyword in ("error", "notfound", "404"))

    @staticmethod
    def _extract_product_info(soup: BeautifulSoup) -> Dict[str, Any]:
        """从页面中提取商品名称与价格等核心信息。"""
        name = None
        price = None

        og_title = soup.find("meta", attrs={"property": "og:title"})
        if og_title and og_title.get("content"):
            name = og_title["content"].strip()
        if not name and soup.title and soup.title.string:
            name = soup.title.string.strip()

        price_node = soup.find("meta", attrs={"property": "og:price:amount"})
        if price_node and price_node.get("content"):
            price = price_node["content"].strip()

        if not price:
            selector_candidates = [
                "[itemprop=price]",
                "[data-price]",
                ".price",
                ".ProductPrice",
            ]
            for selector in selector_candidates:
                node = soup.select_one(selector)
                if node:
                    text = node.get("content") or node.get_text()
                    price = text.strip()
                    break

        if not price:
            text = soup.get_text(" ", strip=True)
            match = re.search(r"[¥￥]\s*([0-9,.]+)", text)
            if match:
                price = f"¥{match.group(1)}"

        return {"product_name": name, "price": price}


__all__ = ["RakutenPageDetector", "DetectionResult"]
