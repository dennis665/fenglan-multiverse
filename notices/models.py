from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import BaseModel  # * 確保這裡的路徑正確


class Announcement(BaseModel):
    title = models.CharField(max_length=200, verbose_name="標題")
    content = models.TextField(verbose_name="內容")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="發布者")
    is_active = models.BooleanField(default=True, verbose_name="是否啟用")
    is_pinned = models.BooleanField(default=False, verbose_name="是否置頂")  # * 新增置頂功能

    class Meta:
        verbose_name = "公告"
        verbose_name_plural = "公告管理"
        ordering = ["-is_pinned", "-created_at"]  # * 先看置頂，再看時間

    def __str__(self):
        return self.title

class ExternalTool(models.Model):
    title = models.CharField(max_length=50, verbose_name="工具名稱")
    url = models.URLField(verbose_name="網址")
    icon_class = models.CharField(max_length=50, default="fas fa-external-link-alt", verbose_name="FontAwesome 圖示碼")
    order = models.IntegerField(default=0, verbose_name="排序")
    is_active = models.BooleanField(default=True, verbose_name="是否啟用")

    class Meta:
        verbose_name = "外部工具"
        verbose_name_plural = "外部工具管理"
        ordering = ["order"]

    def __str__(self):
        return self.title


class AISystemSetting(models.Model):
    #! 存放 AI 的基本行為規範與排版要求
    instruction_text = models.TextField(verbose_name="系統基本指令")
    #! 存放網站功能的描述
    website_info = models.TextField(verbose_name="網站功能資訊", blank=True)
    is_active = models.BooleanField(default=True, verbose_name="是否啟用")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AI 客服設定"
        verbose_name_plural = "AI 客服設定"

    def __str__(self):
        return f"AI 設定 (更新時間: {self.updated_at.strftime('%Y-%m-%d %H:%M')})"

class SiteVisit(models.Model):
    # 總瀏覽人數
    total_visits = models.PositiveIntegerField(default=0, verbose_name="總瀏覽量")

    # 單日統計：紀錄日期與當天次數
    date = models.DateField(default=timezone.now, unique=True, verbose_name="統計日期")
    daily_count = models.PositiveIntegerField(default=0, verbose_name="當日瀏覽量")

    class Meta:
        verbose_name = "網站瀏覽統計"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.date} 統計"


class TicketRecord(models.Model):
    date = models.DateField(auto_now_add=True, verbose_name="日期")
    serial_number = models.CharField(max_length=11, unique=True, verbose_name="發文字號")
    matter = models.CharField(max_length=20, verbose_name="事由")
    applicant = models.CharField(max_length=10, verbose_name="取號人")

    class Meta:
        ordering = ["-date"]
        verbose_name = "發文簿紀錄"

    def __str__(self):
        return f"{self.serial_number} - {self.applicant}"
