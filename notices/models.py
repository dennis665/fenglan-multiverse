from django.conf import settings
from django.db import models

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
