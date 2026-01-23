from django.conf import settings
from django.db import models


#! 公告資料模型
class Notice(models.Model):
    title = models.CharField(max_length=200, verbose_name="標題")
    content = models.TextField(verbose_name="內容")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="發布者"
    )  # * 連結到透過 Google 登入的使用者
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新時間")

    class Meta:
        ordering = ["-created_at"]  # * 讓最新公告排在最前面

    def __str__(self):
        return self.title
