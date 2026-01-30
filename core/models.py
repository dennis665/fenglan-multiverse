from django.db import models


class BaseModel(models.Model):
    """所有模型通用的基礎欄位"""

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新時間")

    class Meta:
        abstract = True  #! 代表這是一個抽象類別，不會在資料庫產生表格


class FeatureStatus(models.Model):
    FEATURE_CHOICES = [
        ("lucky_draw", "幸運大轉盤"),
        ("ticket_pull", "發文簿系統"),
        ("profile_edit", "個人化大頭貼"),
        ("ai_chat", "AI 智能客服"),
        ("announcement", "公告系統"),
        ("admin_panel", "管理後台"),
    ]

    name = models.CharField(max_length=50, choices=FEATURE_CHOICES, unique=True, verbose_name="功能名稱")
    is_active = models.BooleanField(default=True, verbose_name="全局啟用狀態")

    #! 權限細分
    guest_access = models.BooleanField(default=False, verbose_name="訪客可用")
    user_access = models.BooleanField(default=False, verbose_name="一般用戶可用")
    staff_access = models.BooleanField(default=False, verbose_name="工作人員可用")
    superuser_access = models.BooleanField(default=True, verbose_name="管理員可用")

    description = models.TextField(blank=True, verbose_name="功能簡介")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="顯示順序")

    class Meta:
        verbose_name = "功能權限管理"
        verbose_name_plural = "功能權限管理"
        ordering = ["sort_order", "id"]

    def __str__(self):
        status = "🟢" if self.is_active else "🔴"
        return f"{status} {self.get_name_display()}"  # pyright: ignore[reportAttributeAccessIssue]