from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class TubeFolder(models.Model):
    #! 使用者自訂的收藏資料夾或歌單
    FOLDER_TYPE_CHOICES = [
        ("course", _("影片資料夾")),
        ("ktv", _("音樂歌單")),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("擁有者")
    )
    name = models.CharField(max_length=100, verbose_name=_("資料夾名稱"))
    folder_type = models.CharField(
        max_length=10, choices=FOLDER_TYPE_CHOICES, default="course", verbose_name=_("類型")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("建立時間"))

    class Meta:
        verbose_name = _("收藏資料夾")
        verbose_name_plural = _("收藏資料夾")
        unique_together = ("user", "name")

    def __str__(self):
        return self.name


class TubeResource(models.Model):
    #! 影音資源庫資料表
    CATEGORY_CHOICES = [
        ("course", _("影片")),
        ("ktv", _("音樂")),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("擁有者"), null=True
    )
    folder = models.ForeignKey(
        TubeFolder, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("所屬資料夾")
    )
    is_public = models.BooleanField(default=False, verbose_name=_("公開分享給他人"))

    url = models.URLField(verbose_name=_("來源網址"))
    title = models.CharField(verbose_name=_("資源標題"), max_length=255)
    category = models.CharField(
        verbose_name=_("資源分類"), max_length=10, choices=CATEGORY_CHOICES, default="course"
    )
    video_file = models.FileField(
        verbose_name=_("影片檔"), upload_to="tube_hub/videos/", blank=True, null=True
    )
    audio_file = models.FileField(
        verbose_name=_("音檔"), upload_to="tube_hub/audios/", blank=True, null=True
    )
    primary_content = models.TextField(verbose_name=_("主內容"), blank=True, null=True)
    secondary_content = models.TextField(verbose_name=_("副內容"), blank=True, null=True)
    personal_notes = models.TextField(verbose_name=_("個人筆記"), blank=True, null=True)
    created_at = models.DateTimeField(verbose_name=_("建立時間"), auto_now_add=True)

    class Meta:
        verbose_name = _("影音資源")
        verbose_name_plural = _("影音資源")

    def __str__(self):
        return self.title