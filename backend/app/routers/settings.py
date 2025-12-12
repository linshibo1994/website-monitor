"""
设置相关 API 路由
"""
from fastapi import APIRouter, HTTPException

from ..config import config_manager, get_config
from ..services.notifier import email_notifier
from ..schemas.schemas import (
    SettingsResponse,
    SettingsUpdateRequest,
    MonitorConfigSchema,
    EmailConfigSchema,
    WeChatConfigSchema,
    QQConfigSchema,
    NotificationConfigSchema,
    MessageResponse
)

router = APIRouter()


@router.get("", response_model=SettingsResponse)
async def get_settings():
    """获取当前设置"""
    config = get_config()

    return SettingsResponse(
        monitor=MonitorConfigSchema(
            url=config.monitor.url,
            interval_minutes=config.monitor.interval_minutes,
            timeout_seconds=config.monitor.timeout_seconds,
            retry_times=config.monitor.retry_times,
            headless=config.monitor.headless
        ),
        email=EmailConfigSchema(
            enabled=config.email.enabled,
            smtp_server=config.email.smtp_server,
            smtp_port=config.email.smtp_port,
            sender=config.email.sender,
            password="******" if config.email.password else "",  # 隐藏密码
            receiver=config.email.receiver
        ),
        wechat=WeChatConfigSchema(
            enabled=config.wechat.enabled,
            sendkey="******" if config.wechat.sendkey else "",  # 隐藏 sendkey
        ),
        qq=QQConfigSchema(
            enabled=config.qq.enabled,
            key="******" if config.qq.key else "",  # 隐藏 key
            qq=config.qq.qq,
        ),
        notification=NotificationConfigSchema(
            notify_on_added=config.notification.notify_on_added,
            notify_on_removed=config.notification.notify_on_removed,
            notify_on_error=config.notification.notify_on_error
        )
    )


@router.put("", response_model=MessageResponse)
async def update_settings(request: SettingsUpdateRequest):
    """更新设置"""
    try:
        if request.monitor:
            config_manager.update_monitor_config(
                url=request.monitor.url,
                interval_minutes=request.monitor.interval_minutes,
                timeout_seconds=request.monitor.timeout_seconds,
                retry_times=request.monitor.retry_times,
                headless=request.monitor.headless
            )

        if request.email:
            # 如果密码是隐藏的占位符，不更新
            password = request.email.password
            if password == "******":
                password = get_config().email.password

            config_manager.update_email_config(
                enabled=request.email.enabled,
                smtp_server=request.email.smtp_server,
                smtp_port=request.email.smtp_port,
                sender=request.email.sender,
                password=password,
                receiver=request.email.receiver
            )

        if request.notification:
            config_manager.update_notification_config(
                notify_on_added=request.notification.notify_on_added,
                notify_on_removed=request.notification.notify_on_removed,
                notify_on_error=request.notification.notify_on_error
            )

        if request.wechat:
            sendkey = request.wechat.sendkey
            if sendkey == "******":
                sendkey = get_config().wechat.sendkey
            config_manager.update_wechat_config(
                enabled=request.wechat.enabled,
                sendkey=sendkey,
            )

        if request.qq:
            key = request.qq.key
            if key == "******":
                key = get_config().qq.key
            config_manager.update_qq_config(
                enabled=request.qq.enabled,
                key=key,
                qq=request.qq.qq,
            )

        # 保存到文件
        config_manager.save_config()

        return MessageResponse(success=True, message="设置已保存")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存设置失败: {str(e)}")


@router.post("/test-email", response_model=MessageResponse)
async def send_test_email():
    """发送测试邮件"""
    try:
        success = email_notifier.send_test_email()
        if success:
            return MessageResponse(success=True, message="测试邮件发送成功")
        else:
            return MessageResponse(success=False, message="测试邮件发送失败，请检查配置")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送失败: {str(e)}")


@router.post("/test-wechat", response_model=MessageResponse)
async def send_test_wechat():
    """发送测试微信通知"""
    try:
        success = email_notifier.send_test_wechat()
        if success:
            return MessageResponse(success=True, message="测试微信通知发送成功")
        else:
            return MessageResponse(success=False, message="测试微信通知发送失败，请检查配置")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送失败: {str(e)}")


@router.post("/test-qq", response_model=MessageResponse)
async def send_test_qq():
    """发送测试 QQ 通知"""
    try:
        success = email_notifier.send_test_qq()
        if success:
            return MessageResponse(success=True, message="测试QQ通知发送成功")
        else:
            return MessageResponse(success=False, message="测试QQ通知发送失败，请检查配置")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送失败: {str(e)}")


@router.post("/reload", response_model=MessageResponse)
async def reload_config():
    """重新加载配置"""
    try:
        config_manager.reload()
        return MessageResponse(success=True, message="配置已重新加载")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重新加载失败: {str(e)}")
