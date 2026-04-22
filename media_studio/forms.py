#! media_studio/forms.py
from django import forms
from django.utils.translation import gettext_lazy as _


#! 自訂多檔案上傳 Widget 與 Field，解決 Django 安全更新後的限制
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        return result


class ImageCompressForm(forms.Form):
    #! 圖片上傳與壓縮設定表單
    image = forms.ImageField(label=_("選擇圖片"), required=True)

    #! 新增自動去背選項
    remove_bg = forms.BooleanField(
        label=_("自動去背 (AI 移除背景)"),
        required=False,
        initial=False,
        help_text=_("勾選後將使用 AI 智慧去背。建議輸出格式選擇 PNG 或 WebP 以保留透明背景。"),
    )

    scale_percent = forms.IntegerField(
        label=_("縮放比例 (%)"),
        min_value=1,
        max_value=100,
        initial=100,
        help_text=_("100% 代表不改變長寬像素，僅壓縮品質。"),
    )
    quality = forms.IntegerField(
        label=_("壓縮品質 (1-100)"),
        min_value=1,
        max_value=100,
        initial=85,
        help_text=_("數值越低檔案越小，畫質越差。對 PNG 無效。"),
    )
    output_format = forms.ChoiceField(
        label=_("輸出格式"),
        choices=[
            ("JPEG", "JPG (破壞性壓縮)"),
            ("PNG", "PNG (無損，通常檔案較大)"),
            ("WEBP", "WebP (現代高壓縮比格式)"),
        ],
        initial="WEBP",
    )


class VideoStudioForm(forms.Form):
    #! 影片處理工作室表單
    # * 替換為自訂的 MultipleFileField
    videos = MultipleFileField(
        label=_("選擇影片檔"), help_text=_("可一次選擇多個影片進行拼接"), required=True
    )

    start_time = forms.IntegerField(
        label=_("裁切開始時間 (秒)"), initial=0, min_value=0, help_text=_("若不裁切請保持 0")
    )
    duration = forms.IntegerField(
        label=_("裁切持續時間 (秒)"), initial=0, min_value=0, help_text=_("設為 0 代表取至影片結束")
    )
    quality = forms.IntegerField(
        label=_("輸出品質 (0-100)"),
        initial=80,
        min_value=1,
        max_value=100,
        help_text=_("數值越高畫質越好，但檔案越大 (建議 50-80)"),
    )
    resolution_scale = forms.ChoiceField(
        label=_("縮放解析度"),
        choices=[
            ("original", _("原始尺寸")),
            ("1080", "1080P (FHD)"),
            ("720", "720P (HD)"),
            ("480", "480P (SD)"),
        ],
        initial="original",
    )