"""
库存监控服务
监控指定商品的库存变化并发送通知
"""
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from ..config import get_config
from .inventory_scraper import (
    inventory_scraper,
    ProductInventory,
    InventoryChange,
    check_product_inventory
)
from .scheels_scraper import scheels_scraper, check_scheels_inventory
from .notifier import email_notifier


class InventoryMonitorService:
    """库存监控服务"""

    # 上架确认所需的连续检测次数
    LAUNCH_CONFIRM_COUNT = 2

    def __init__(self):
        self.config = get_config()
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.is_running = False
        self.last_check_time: Optional[datetime] = None

        # 监控的商品列表
        self.monitored_products: List[dict] = []

        # 上次检查的库存状态（product_url -> ProductInventory）
        self.last_inventory: Dict[str, ProductInventory] = {}

        # 上架确认计数器（url -> 连续检测到上架的次数）
        self.launch_confirm_counter: Dict[str, int] = {}

        # 已发送上架通知的商品（避免重复发送）
        self.launch_notified: set = set()

        # 状态文件路径
        self.state_file = Path(__file__).parent.parent.parent.parent / 'data' / 'inventory_state.json'

        # 加载上次的状态
        self._load_state()

    def _load_state(self):
        """从文件加载上次的库存状态"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.monitored_products = data.get('monitored_products', [])
                    logger.info(f"加载了 {len(self.monitored_products)} 个监控商品")
        except Exception as e:
            logger.warning(f"加载状态文件失败: {e}")

    def _save_state(self):
        """保存状态到文件"""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            # 将库存状态转换为可序列化格式
            inventory_data = {}
            for url, inv in self.last_inventory.items():
                inventory_data[url] = inv.to_dict()

            data = {
                'monitored_products': self.monitored_products,
                'last_inventory': inventory_data,
                'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None
            }

            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug("状态已保存")
        except Exception as e:
            logger.error(f"保存状态文件失败: {e}")

    def add_product(
        self,
        url: str,
        name: str = "",
        target_sizes: Optional[List[str]] = None,
        target_colors: Optional[List[str]] = None
    ):
        """
        添加监控商品

        Args:
            url: 商品URL
            name: 商品名称（可选）
            target_sizes: 要监控的尺寸列表（如 ['S', 'M']），为空则监控所有尺寸
            target_colors: 要监控的颜色列表（如 ['Black', 'Void']），为空则监控所有颜色
        """
        # 检查是否已存在
        for product in self.monitored_products:
            if product['url'] == url:
                # 更新配置
                product['name'] = name or product.get('name', '')
                product['target_sizes'] = target_sizes or product.get('target_sizes', [])
                product['target_colors'] = target_colors or product.get('target_colors', [])
                logger.info(f"更新监控商品: {url}")
                self._save_state()
                return

        # 添加新商品
        self.monitored_products.append({
            'url': url,
            'name': name,
            'target_sizes': target_sizes or [],  # 空列表表示监控所有尺寸
            'target_colors': target_colors or []  # 空列表表示监控所有颜色
        })
        logger.info(f"添加监控商品: {url}, 目标尺寸: {target_sizes or '全部'}, 目标颜色: {target_colors or '全部'}")
        self._save_state()

    def remove_product(self, url: str):
        """移除监控商品"""
        self.monitored_products = [p for p in self.monitored_products if p['url'] != url]
        if url in self.last_inventory:
            del self.last_inventory[url]
        logger.info(f"移除监控商品: {url}")
        self._save_state()

    async def refresh_product_inventory(self, url: str) -> Optional[ProductInventory]:
        """
        立即抓取单个商品的库存信息

        用于用户新建监控后快速获取商品名称、变体等数据，避免界面长期显示“未知”。
        """
        try:
            logger.info(f"开始执行单个商品的即时库存抓取: {url}")

            if 'scheels.com' in url:
                new_inventory = await scheels_scraper.check_inventory(url, max_retries=1)
            else:
                new_inventory = await check_product_inventory(url)

            if new_inventory is None:
                logger.warning(f"即时库存抓取失败: {url}")
                return None

            self.last_inventory[url] = new_inventory
            self.last_check_time = datetime.now()
            self._save_state()
            logger.info(f"即时库存抓取成功，已更新缓存: {new_inventory.name}")
            return new_inventory
        except Exception as e:
            logger.error(f"单个商品即时库存抓取异常: {url} - {e}")
            return None

    async def check_all_products(self) -> dict:
        """检查所有监控商品的库存"""
        logger.info("=" * 50)
        logger.info("开始检查所有商品库存")

        results = {
            'success': True,
            'products_checked': 0,
            'changes_detected': 0,
            'notifications_sent': 0,
            'errors': []
        }

        for product_config in self.monitored_products:
            url = product_config['url']
            target_sizes = product_config.get('target_sizes', [])
            target_colors = product_config.get('target_colors', [])

            try:
                # 根据 URL 选择对应的爬虫
                if 'scheels.com' in url:
                    new_inventory = await check_scheels_inventory(url)
                    scraper = scheels_scraper
                else:
                    new_inventory = await check_product_inventory(url)
                    scraper = inventory_scraper

                if new_inventory is None:
                    results['errors'].append(f"检查失败: {url}")
                    continue

                results['products_checked'] += 1

                # 获取旧库存状态
                old_inventory = self.last_inventory.get(url)

                # 检测状态变化（coming_soon -> available）- 使用连续确认机制
                if new_inventory.is_coming_soon():
                    # 仍然是 Coming Soon，重置确认计数器
                    self.launch_confirm_counter[url] = 0
                    logger.info(f"商品仍为 Coming Soon: {new_inventory.name}")
                elif new_inventory.is_available():
                    # 检查是否需要发送上架通知
                    if url not in self.launch_notified:
                        # 检查旧状态是否为 Coming Soon
                        was_coming_soon = old_inventory and old_inventory.is_coming_soon()

                        if was_coming_soon or url in self.launch_confirm_counter:
                            # 增加确认计数
                            self.launch_confirm_counter[url] = self.launch_confirm_counter.get(url, 0) + 1
                            confirm_count = self.launch_confirm_counter[url]

                            logger.info(f"商品上架确认中: {new_inventory.name} ({confirm_count}/{self.LAUNCH_CONFIRM_COUNT})")

                            # 检查是否达到确认次数
                            if confirm_count >= self.LAUNCH_CONFIRM_COUNT:
                                # 额外验证：确保有库存或者不再显示 Coming Soon 标记
                                has_stock = len(new_inventory.get_available_sizes()) > 0

                                if has_stock:
                                    logger.info(f"商品上架已确认: {new_inventory.name}，有库存尺寸: {new_inventory.get_available_sizes()}")
                                    notification_sent = self._send_launch_notification(new_inventory)
                                    if notification_sent:
                                        results['notifications_sent'] += 1
                                        results['changes_detected'] += 1
                                        self.launch_notified.add(url)
                                        del self.launch_confirm_counter[url]
                                else:
                                    logger.warning(f"商品标记为上架但无任何库存，暂不发送通知: {new_inventory.name}")
                                    # 重置计数器，等待有库存时再确认
                                    self.launch_confirm_counter[url] = 0

                    # 正常商品，比较库存变化
                    changes = scraper.compare_inventory(old_inventory, new_inventory)

                    # 记录所有变化（调试用）
                    if changes:
                        logger.debug(f"检测到 {len(changes)} 个库存变化（过滤前）: "
                                    f"{[(c.size, c.old_status, c.new_status) for c in changes]}")

                    # 过滤目标尺寸的变化
                    if target_sizes:
                        original_count = len(changes)
                        changes = [c for c in changes if c.size in target_sizes]
                        if original_count > 0:
                            logger.info(f"目标尺寸过滤: {original_count} -> {len(changes)} 个变化 "
                                       f"(目标尺寸: {target_sizes})")

                    # 过滤目标颜色的变化
                    if target_colors:
                        original_count = len(changes)
                        changes = [c for c in changes if c.color_name in target_colors]
                        if original_count > 0:
                            logger.info(f"目标颜色过滤: {original_count} -> {len(changes)} 个变化 "
                                       f"(目标颜色: {target_colors})")

                    if changes:
                        results['changes_detected'] += len(changes)
                        logger.info(f"有效库存变化: {[(c.size, c.old_status + '->' + c.new_status, '补货' if c.became_available else '售罄') for c in changes]}")

                        # 检查是否有补货
                        restocked_sizes = [c.size for c in changes if c.became_available]

                        if restocked_sizes:
                            # 发送补货通知
                            logger.info(f"检测到补货: {new_inventory.name} - {restocked_sizes}")
                            notification_sent = self._send_restock_notification(
                                new_inventory,
                                restocked_sizes
                            )
                            if notification_sent:
                                results['notifications_sent'] += 1
                        else:
                            logger.info(f"库存变化为售罄，不发送通知")

                # 更新状态
                self.last_inventory[url] = new_inventory

            except Exception as e:
                logger.error(f"检查商品库存出错: {url} - {e}")
                results['errors'].append(f"{url}: {str(e)}")

            # 请求间隔，避免被封
            await asyncio.sleep(3)

        self.last_check_time = datetime.now()
        self._save_state()

        logger.info(f"库存检查完成: 检查了 {results['products_checked']} 个商品, "
                   f"检测到 {results['changes_detected']} 个变化, "
                   f"发送了 {results['notifications_sent']} 个通知")
        logger.info("=" * 50)

        return results

    def _send_restock_notification(
        self,
        inventory: ProductInventory,
        restocked_sizes: List[str]
    ) -> bool:
        """发送补货通知邮件"""
        if not self.config.email.enabled:
            logger.info("邮件通知已禁用")
            return False

        subject = f"【补货通知】{inventory.name} {', '.join(restocked_sizes)} 有货了!"

        html_content = self._build_restock_email(inventory, restocked_sizes)

        return email_notifier.send_email(subject, html_content)

    def _send_launch_notification(self, inventory: ProductInventory) -> bool:
        """发送商品上架通知邮件"""
        if not self.config.email.enabled:
            logger.info("邮件通知已禁用")
            return False

        subject = f"【上架通知】{inventory.name} 已正式上架!"

        html_content = self._build_launch_email(inventory)

        return email_notifier.send_email(subject, html_content)

    def _build_launch_email(self, inventory: ProductInventory) -> str:
        """构建商品上架通知邮件内容"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 构建所有尺寸的库存状态表格
        size_rows = []
        for variant in inventory.variants:
            status_color = '#27ae60' if variant.is_available() else '#e74c3c'
            status_text = '有货' if variant.is_available() else '无货'

            size_rows.append(f'''
            <tr>
                <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: center;">
                    <strong>{variant.size}</strong>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: center;">
                    <span style="color: {status_color}; font-weight: bold;">{status_text}</span>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: center; color: #555;">
                    {variant.quantity_display()}
                </td>
            </tr>
            ''')

        # 如果没有尺寸数据，显示提示信息
        size_table_html = ''
        if size_rows:
            size_table_html = f'''
            <div style="margin: 20px 0;">
                <h3 style="background: #3498db; color: white; padding: 10px 15px; margin: 0; border-radius: 5px 5px 0 0;">
                    📊 库存状态
                </h3>
                <table style="width: 100%; border-collapse: collapse; background: #f8f9fa; border-radius: 0 0 5px 5px;">
                    <tr style="background: #ecf0f1;">
                        <th style="padding: 12px; text-align: center;">尺寸</th>
                        <th style="padding: 12px; text-align: center;">状态</th>
                        <th style="padding: 12px; text-align: center;">剩余数量</th>
                    </tr>
                    {''.join(size_rows)}
                </table>
            </div>
            '''
        else:
            size_table_html = '''
            <div style="margin: 20px 0; background: #fff3cd; padding: 15px; border-radius: 5px; text-align: center;">
                <p style="margin: 0; color: #856404;">商品刚刚上架，库存信息正在更新中...</p>
            </div>
            '''

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
                <h1 style="color: white; margin: 0; font-size: 24px;">🎉 商品已上架</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">您关注的商品已正式开售!</p>
            </div>

            <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                <h2 style="margin: 0 0 15px 0; color: #333;">{inventory.name}</h2>
                <table style="width: 100%;">
                    <tr>
                        <td style="padding: 8px 0;">
                            <span style="color: #666;">⏰ 检测时间</span><br>
                            <strong>{now}</strong>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;">
                            <span style="color: #666;">📦 商品状态</span><br>
                            <strong style="color: #27ae60; font-size: 18px;">已上架 (之前为 Coming Soon)</strong>
                        </td>
                    </tr>
                </table>
            </div>

            {size_table_html}

            <div style="text-align: center; margin-top: 30px; padding: 20px; background: #f8f9fa; border-radius: 10px;">
                <a href="{inventory.url}" style="display: inline-block; background: #e74c3c; color: white; padding: 15px 40px; border-radius: 5px; text-decoration: none; font-weight: bold; font-size: 16px;">
                    🛒 立即购买
                </a>
                <p style="color: #999; margin-top: 15px; font-size: 12px;">
                    新品上架，热门尺寸可能很快售罄，请尽快下单!
                </p>
            </div>

            <div style="text-align: center; margin-top: 20px;">
                <p style="color: #999; font-size: 12px;">
                    此邮件由 Arc'teryx 库存监控系统自动发送
                </p>
            </div>
        </body>
        </html>
        """

        return html

    def _build_restock_email(
        self,
        inventory: ProductInventory,
        restocked_sizes: List[str]
    ) -> str:
        """构建补货通知邮件内容"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 构建所有尺寸的库存状态表格
        size_rows = []
        for variant in inventory.variants:
            status_color = '#27ae60' if variant.is_available() else '#e74c3c'
            status_text = '有货' if variant.is_available() else '无货'
            highlight = 'background: #d5f5e3;' if variant.size in restocked_sizes else ''

            size_rows.append(f'''
            <tr style="{highlight}">
                <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: center;">
                    <strong>{variant.size}</strong>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: center;">
                    <span style="color: {status_color}; font-weight: bold;">{status_text}</span>
                    {' 🎉' if variant.size in restocked_sizes else ''}
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: center; color: #555;">
                    {variant.quantity_display()}
                </td>
            </tr>
            ''')

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
                <h1 style="color: white; margin: 0; font-size: 24px;">🎉 补货通知</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">您关注的商品有货了!</p>
            </div>

            <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                <h2 style="margin: 0 0 15px 0; color: #333;">{inventory.name}</h2>
                <table style="width: 100%;">
                    <tr>
                        <td style="padding: 8px 0;">
                            <span style="color: #666;">⏰ 检测时间</span><br>
                            <strong>{now}</strong>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;">
                            <span style="color: #666;">✨ 补货尺寸</span><br>
                            <strong style="color: #27ae60; font-size: 18px;">{', '.join(restocked_sizes)}</strong>
                        </td>
                    </tr>
                </table>
            </div>

            <div style="margin: 20px 0;">
                <h3 style="background: #3498db; color: white; padding: 10px 15px; margin: 0; border-radius: 5px 5px 0 0;">
                    📊 所有尺寸库存状态
                </h3>
                <table style="width: 100%; border-collapse: collapse; background: #f8f9fa; border-radius: 0 0 5px 5px;">
                    <tr style="background: #ecf0f1;">
                        <th style="padding: 12px; text-align: center;">尺寸</th>
                        <th style="padding: 12px; text-align: center;">状态</th>
                        <th style="padding: 12px; text-align: center;">剩余数量</th>
                    </tr>
                    {''.join(size_rows)}
                </table>
            </div>

            <div style="text-align: center; margin-top: 30px; padding: 20px; background: #f8f9fa; border-radius: 10px;">
                <a href="{inventory.url}" style="display: inline-block; background: #e74c3c; color: white; padding: 15px 40px; border-radius: 5px; text-decoration: none; font-weight: bold; font-size: 16px;">
                    🛒 立即购买
                </a>
                <p style="color: #999; margin-top: 15px; font-size: 12px;">
                    热门尺寸库存紧张，请尽快下单!
                </p>
            </div>

            <div style="text-align: center; margin-top: 20px;">
                <p style="color: #999; font-size: 12px;">
                    此邮件由 Arc'teryx 库存监控系统自动发送
                </p>
            </div>
        </body>
        </html>
        """

        return html

    def start_scheduler(self, interval_minutes: int = 5):
        """启动定时调度器"""
        if self.scheduler is not None:
            logger.warning("库存监控调度器已在运行")
            return

        import pytz
        self.scheduler = AsyncIOScheduler(timezone=pytz.UTC)
        self.scheduler.add_job(
            self.check_all_products,
            trigger=IntervalTrigger(minutes=interval_minutes, timezone=pytz.UTC),
            id='inventory_monitor_job',
            name='库存监控任务',
            replace_existing=True
        )

        self.scheduler.start()
        self.is_running = True

        logger.info(f"库存监控调度器已启动，检测间隔: {interval_minutes} 分钟")

    def stop_scheduler(self):
        """停止定时调度器"""
        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler = None
            self.is_running = False
            logger.info("库存监控调度器已停止")

    def get_status(self) -> dict:
        """获取监控状态"""
        return {
            "is_running": self.is_running,
            "last_check_time": self.last_check_time.isoformat() if self.last_check_time else None,
            "monitored_products": len(self.monitored_products),
            "products": [
                {
                    "url": p['url'],
                    "name": p.get('name', ''),
                    "target_sizes": p.get('target_sizes', []),
                    "target_colors": p.get('target_colors', []),
                    "last_available": self.last_inventory.get(p['url'], ProductInventory(
                        model_sku='', name='', url='', variants=[], check_time=datetime.now()
                    )).get_available_sizes() if p['url'] in self.last_inventory else []
                }
                for p in self.monitored_products
            ]
        }


# 创建服务单例
inventory_monitor_service = InventoryMonitorService()


async def run_inventory_monitor_once():
    """执行一次库存检查"""
    return await inventory_monitor_service.check_all_products()


async def run_inventory_monitor_daemon(interval_minutes: int = 5):
    """守护进程模式运行库存监控"""
    logger.info("启动库存监控守护进程...")

    # 先执行一次
    await inventory_monitor_service.check_all_products()

    # 启动定时任务
    inventory_monitor_service.start_scheduler(interval_minutes)

    # 保持运行
    try:
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止...")
        inventory_monitor_service.stop_scheduler()
