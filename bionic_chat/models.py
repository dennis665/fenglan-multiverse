from django.db import models
from django.utils.translation import gettext_lazy as _


class ChatHistory(models.Model):
    #! 對話紀錄表
    user_message = models.TextField(
        verbose_name=_("使用者輸入"),
    )  # * 記錄使用者的原始文字

    bot_response = models.TextField(
        verbose_name=_("仿生人回覆"),
    )  # * 記錄 AI 生成的完整回覆

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("建立時間"),
    )  # * 自動記錄訊息產生的時間

    class Meta:
        verbose_name = _("對話紀錄")
        verbose_name_plural = _("對話紀錄")

    def __str__(self):
        return f"[{self.created_at}] User: {self.user_message[:20]}"
