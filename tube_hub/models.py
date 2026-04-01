#! Tube Hub 模型定義
from django.db import models
from django.utils.translation import gettext_lazy as _


class TubeResource(models.Model):
    """影音資源庫資料表"""

    CATEGORY_CHOICES = [
        ("course", _("課堂學習")),
        ("ktv", _("練唱歌")),
    ]

    url = models.URLField(verbose_name=_("來源網址"), unique=True)
    title = models.CharField(verbose_name=_("資源標題"), max_length=255)
    category = models.CharField(
        verbose_name=_("資源分類"),
        max_length=10,
        choices=CATEGORY_CHOICES,
        default="course",
    )
    video_file = models.FileField(
        verbose_name=_("影片檔"), upload_to="tube_hub/videos/", blank=True, null=True
    )
    audio_file = models.FileField(
        verbose_name=_("音檔"), upload_to="tube_hub/audios/", blank=True, null=True
    )
    primary_content = models.TextField(
        verbose_name=_("主內容 (原生字幕/歌詞)"), blank=True, null=True
    )
    secondary_content = models.TextField(
        verbose_name=_("副內容 (AI 處理結果)"), blank=True, null=True
    )
    personal_notes = models.TextField(verbose_name=_("個人學習筆記"), blank=True, null=True)
    created_at = models.DateTimeField(verbose_name=_("建立時間"), auto_now_add=True)

    class Meta:
        verbose_name = _("影音資源")
        verbose_name_plural = _("影音資源")

    def __str__(self):
        return self.title
