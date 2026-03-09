from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel


class Announcement(BaseModel):
    title = models.CharField(max_length=200, verbose_name=_("標題"))
    content = models.TextField(verbose_name=_("內容"))
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("發布者"))
    is_active = models.BooleanField(default=True, verbose_name=_("是否啟用"))
    is_pinned = models.BooleanField(default=False, verbose_name=_("是否置頂"))  # * 新增置頂功能

    class Meta:
        verbose_name = _("公告")
        verbose_name_plural = _("公告管理")
        ordering = ["-is_pinned", "-created_at"]  # * 先看置頂，再看時間

    def __str__(self):
        return self.title


class ExternalTool(models.Model):
    title = models.CharField(max_length=50, verbose_name=_("工具名稱"))
    url = models.URLField(verbose_name=_("網址"))
    icon_class = models.CharField(
        max_length=50, default="fas fa-external-link-alt", verbose_name=_("FontAwesome 圖示碼")
    )
    order = models.IntegerField(default=0, verbose_name=_("排序"))
    is_active = models.BooleanField(default=True, verbose_name=_("是否啟用"))

    class Meta:
        verbose_name = _("外部工具")
        verbose_name_plural = _("外部工具管理")
        ordering = ["order"]

    def __str__(self):
        return self.title


class AISystemSetting(models.Model):
    ROLE_CHOICES = [
        ("GUEST", _("未登入訪客")),
        ("USER", _("一般使用者")),
        ("STAFF", _("工作人員")),
        ("SUPERUSER", _("超級管理員")),
        ("EMPLOYEE", _("專屬公司職員")),  # * 可以附加以上任何
    ]

    role_level = models.CharField(max_length=20, choices=ROLE_CHOICES, default="GUEST", verbose_name=_("適用權限"))
    instruction_text = models.TextField(verbose_name=_("系統基本指令"))
    website_info = models.TextField(verbose_name=_("網站功能資訊"), blank=True)
    internal_policy = models.TextField(verbose_name=_("內部政策"), blank=True)
    is_active = models.BooleanField(default=False, verbose_name=_("是否啟用"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("更新時間"))

    class Meta:
        verbose_name = _("AI 客服設定")
        verbose_name_plural = _("AI 客服設定")

    #! 核心邏輯：確保同一權限等級只有一筆 is_active=True
    def save(self, *args, **kwargs):
        if self.is_active:
            with transaction.atomic():
                #! 將「同等級」且「目前啟用中」的其他設定全部設為 False
                AISystemSetting.objects.filter(role_level=self.role_level, is_active=True).exclude(pk=self.pk).update(
                    is_active=False
                )
        super().save(*args, **kwargs)

    def __str__(self):
        #! 使用 _() 包裹狀態文字以支援翻譯
        active_status = _("✅啟用中") if self.is_active else _("❌停用")
        updated_text = _("更新於")
        return f"[{self.get_role_level_display()}] {active_status} ({updated_text}: {self.updated_at.strftime('%m-%d %H:%M')})"  # pyright: ignore[reportAttributeAccessIssue]


class SiteVisit(models.Model):
    total_visits = models.PositiveIntegerField(default=0, verbose_name=_("總瀏覽量"))
    date = models.DateField(default=timezone.now, unique=True, verbose_name=_("統計日期"))
    daily_count = models.PositiveIntegerField(default=0, verbose_name=_("當日瀏覽量"))

    class Meta:
        verbose_name = _("網站瀏覽統計")
        verbose_name_plural = _("網站瀏覽統計")

    def __str__(self):
        stat_text = _("統計")
        return f"{self.date} {stat_text}"


class TicketRecord(models.Model):
    date = models.DateField(auto_now_add=True, verbose_name=_("日期"))
    serial_number = models.CharField(max_length=11, unique=True, verbose_name=_("發文字號"))
    matter = models.CharField(max_length=20, verbose_name=_("事由"))
    applicant = models.CharField(max_length=10, verbose_name=_("取號人"))

    class Meta:
        ordering = ["-date"]
        verbose_name = _("發文簿紀錄")
        verbose_name_plural = _("發文簿紀錄")

    def __str__(self):
        return f"{self.serial_number} - {self.applicant}"