#! media_studio/forms.py
from django import forms
from django.utils.translation import gettext_lazy as _


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
