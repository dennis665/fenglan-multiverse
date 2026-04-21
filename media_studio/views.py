#! media_studio/views.py
import base64
import os
from io import BytesIO

from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from PIL import Image
from rembg import remove

from .forms import ImageCompressForm


#! 格式化檔案大小
def format_size(size_in_bytes):
    if size_in_bytes < 1024 * 1024:
        return f"{size_in_bytes / 1024:.2f} KB"
    return f"{size_in_bytes / (1024 * 1024):.2f} MB"


def image_compressor_view(request):
    #! 處理圖片壓縮、去背與預覽
    context = {
        "title": _("圖片處理與去背工具"),
        "form": None,
    }

    if request.method == "POST":
        form = ImageCompressForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.cleaned_data["image"]
            remove_bg = form.cleaned_data["remove_bg"]
            scale_percent = form.cleaned_data["scale_percent"]
            quality = form.cleaned_data["quality"]
            output_format = form.cleaned_data["output_format"]

            original_size = uploaded_file.size
            img = Image.open(uploaded_file)

            #! 取得原始長寬像素
            original_width, original_height = img.size

            #! 執行 AI 自動去背
            if remove_bg:
                img = remove(img)

            #! 處理 RGBA 轉 RGB 問題
            if output_format == "JPEG" and img.mode in ("RGBA", "P"):  # pyright: ignore[reportAttributeAccessIssue]
                background = Image.new("RGB", img.size, (255, 255, 255))  # pyright: ignore[reportArgumentType, reportAttributeAccessIssue]
                if img.mode == "RGBA":  # pyright: ignore[reportAttributeAccessIssue]
                    background.paste(img, mask=img.split()[3])  # pyright: ignore[reportAttributeAccessIssue, reportArgumentType]
                else:
                    background.paste(img)  # pyright: ignore[reportArgumentType]
                img = background

            #! 計算新的長寬尺寸並縮放
            new_width, new_height = original_width, original_height
            if scale_percent < 100:
                new_width = int(original_width * (scale_percent / 100.0))
                new_height = int(original_height * (scale_percent / 100.0))
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)  # pyright: ignore[reportAttributeAccessIssue, reportArgumentType]

            #! 準備記憶體緩衝區並存檔
            buffer = BytesIO()
            if output_format == "PNG":
                img.save(buffer, format="PNG", optimize=True)  # pyright: ignore[reportAttributeAccessIssue, reportOptionalMemberAccess]
                content_type = "image/png"
                ext = ".png"
            elif output_format == "WEBP":
                img.save(buffer, format="WEBP", quality=quality, method=6)  # pyright: ignore[reportAttributeAccessIssue, reportOptionalMemberAccess]
                content_type = "image/webp"
                ext = ".webp"
            else:
                img.save(buffer, format="JPEG", quality=quality, optimize=True)  # pyright: ignore[reportAttributeAccessIssue, reportOptionalMemberAccess]
                content_type = "image/jpeg"
                ext = ".jpg"

            buffer.seek(0)
            compressed_size = len(buffer.getvalue())

            b64_encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
            data_uri = f"data:{content_type};base64,{b64_encoded}"

            original_name = os.path.splitext(uploaded_file.name)[0]

            #! 將結果與像素資訊寫入 context
            context["compressed_data_uri"] = data_uri
            context["original_size_str"] = format_size(original_size)
            context["compressed_size_str"] = format_size(compressed_size)
            #! 傳遞像素資訊至前端
            context["original_dimensions"] = f"{original_width} x {original_height} px"
            context["new_dimensions"] = f"{new_width} x {new_height} px"

            context["new_filename"] = f"{original_name}_processed{ext}"
            context["form"] = form
    else:
        context["form"] = ImageCompressForm()

    return render(request, "media_studio/compressor.html", context)
