from django.db import models
from django.utils.translation import gettext_lazy as _


class BaseModel(models.Model):
    """所有模型通用的基礎欄位"""

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("建立時間"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("更新時間"))

    class Meta:
        abstract = True  #! 代表這是一個抽象類別，不會在資料庫產生表格


class FeatureStatus(models.Model):
    FEATURE_CHOICES = [
        ("lucky_draw", _("幸運大轉盤")),
        ("ticket_pull", _("發文簿系統")),
        ("profile_edit", _("個人化大頭貼")),
        ("ai_chat", _("AI 智能客服")),
        ("announcement", _("公告系統")),
        ("admin_panel", _("管理後台")),
        ("tigf", _("安定系統")),
    ]

    name = models.CharField(max_length=50, choices=FEATURE_CHOICES, unique=True, verbose_name=_("功能名稱"))
    is_active = models.BooleanField(default=True, verbose_name=_("全局啟用狀態"))

    #! 權限細分
    guest_access = models.BooleanField(default=False, verbose_name=_("訪客可用"))
    user_access = models.BooleanField(default=False, verbose_name=_("一般用戶可用"))
    staff_access = models.BooleanField(default=False, verbose_name=_("工作人員可用"))
    superuser_access = models.BooleanField(default=True, verbose_name=_("管理員可用"))

    description = models.TextField(blank=True, verbose_name=_("功能簡介"))
    sort_order = models.PositiveIntegerField(default=0, verbose_name=_("顯示順序"))

    class Meta:
        verbose_name = _("功能權限管理")
        verbose_name_plural = _("功能權限管理")
        ordering = ["sort_order", "id"]

    def __str__(self):
        status = "🟢" if self.is_active else "🔴"
        #! get_name_display() 會自動回傳翻譯後的選項
        return f"{status} {self.get_name_display()}"  # pyright: ignore[reportAttributeAccessIssue]