from django.db import models
from django.utils.translation import gettext_lazy as _


class AIModel(models.Model):
    #! AI 模型檔案管理
    version_name = models.CharField(
        max_length=100,
        verbose_name=_("模型版本名稱"),  # * 用於讓使用者在網頁上識別不同 pth 檔
    )
    model_file = models.FileField(
        upload_to="models/shih_hsiang/", verbose_name=_("模型檔案 (.pth)")
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name=_("上傳時間"))

    class Meta:
        verbose_name = _("AI 模型")
        verbose_name_plural = _("AI 模型管理")

    def __str__(self):
        return self.version_name


class ImageRecord(models.Model):
    #! 圖片辨識紀錄管理
    original_image = models.ImageField(upload_to="images/original/", verbose_name=_("原始圖片"))
    result_image = models.ImageField(
        upload_to="images/result/", null=True, blank=True, verbose_name=_("辨識結果圖片")
    )
    result_text = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("辨識文字結果"),  # * 儲存原先輸出的 txt 內容
    )
    has_object = models.BooleanField(default=False, verbose_name=_("是否有辨識到物體"))
    conf_threshold = models.FloatField(default=0.5, verbose_name=_("使用信心閥值"))
    user_note = models.TextField(null=True, blank=True, verbose_name=_("使用者註記"))
    used_model = models.ForeignKey(
        AIModel, on_delete=models.SET_NULL, null=True, verbose_name=_("使用模型")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("建立時間"))

    class Meta:
        verbose_name = _("圖片辨識紀錄")
        verbose_name_plural = _("圖片辨識紀錄管理")
