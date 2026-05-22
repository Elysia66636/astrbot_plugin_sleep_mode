from datetime import datetime
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.event.filter import EventMessageType
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import At

# 注册插件：插件ID、作者、描述、版本
@register("astrbot_plugin_sleep_mode", "次次保底真菌 & 天喵", "群聊定时休眠插件", "1.0.0")
class SleepModePlugin(Star):
    """群聊定时休眠插件：在指定时间段内，仅响应 @机器人 的消息，其他消息自动拦截并回复提示。"""

    def __init__(self, context: Context, config=None):
        """初始化插件，保存配置并输出日志。"""
        super().__init__(context)
        self.config = config          # 插件配置，包含时间范围、目标群组、回复文本
        logger.info(f"[SleepMode] 初始化 config={self.config}")

    @staticmethod
    def _in_sleep(start_str: str, end_str: str) -> bool:
        """
        判断当前时间是否处于休眠时间段内。
        支持跨午夜的时间段（例如 23:00 ~ 06:00）。
        start_str: 开始时间，格式 HH:MM
        end_str:   结束时间，格式 HH:MM
        返回 True 表示当前在休眠期内。
        """
        try:
            now = datetime.now().time()                     # 当前时间
            s = datetime.strptime(start_str.strip(), "%H:%M").time()   # 开始时间
            e = datetime.strptime(end_str.strip(), "%H:%M").time()     # 结束时间
            if s <= e:
                # 常规时间段（不跨午夜）
                return s <= now <= e
            # 跨午夜：当前时间 >= 开始 或 当前时间 <= 结束
            return now >= s or now <= e
        except (ValueError, AttributeError):
            # 时间格式错误时返回 False（不启用休眠）
            return False

    # 监听群聊消息，设置高优先级（1001）以拦截后续处理
    @filter.event_message_type(filter.EventMessageType.ALL, priority=1001)
    async def intercept(self, event: AstrMessageEvent):
        """
        拦截群消息并判断是否在休眠期。
        如果在休眠期且消息未被 @机器人，则拦截消息并回复预设文本；
        如果被 @，则允许通过并回复提示，同时停止事件传播。
        """
        raw_gid = getattr(event.message_obj, "group_id", "")   # 获取群号
        logger.info(f"[SleepMode] 收到群消息 gid={raw_gid}, config={self.config is not None}")

        # 未配置则放行
        if not self.config:
            return

        # 只处理配置中指定的群组
        groups = [str(g) for g in self.config.get("target_groups", [])]
        gid = str(raw_gid)
        if gid not in groups:
            return

        # 检查是否处于休眠时间段
        if not self._in_sleep(
            self.config.get("start_time", "00:00"),
            self.config.get("end_time", "07:00")
        ):
            return

        # 判断是否 @ 了机器人（优先使用框架提供的标记，再手动遍历消息元素）
        is_at = event.is_at_or_wake_command
        if not is_at:
            for c in event.get_messages():
                if isinstance(c, At):
                    is_at = True
                    break

        # 如果被 @，回复提示文本并拦截后续处理（不继续传递事件）
        if is_at:
            bot_self_id = getattr(event.message_obj, 'self_id', None)
            if bot_self_id:
                for component in event.get_messages():
                    if isinstance(component, At) and str(component.qq) == str(bot_self_id):
                        event.set_result(event.plain_result(
                            self.config.get("reply_text", "s属性大爆发，sleeping！")
                        ))
        # 无论是否被 @，都终止事件传播（普通消息直接丢弃，@消息回复后也停止）
        event.stop_event()