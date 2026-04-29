from utils.logger_utils import time_tracker

#! 包裝整個 import 區塊或初始化邏輯
with time_tracker("media_studio"):
    import base64
    import os
    import tempfile
    from io import BytesIO

    from django.shortcuts import render
    from django.utils.translation import gettext_lazy as _
    from PIL import Image

    from .forms import ImageCompressForm, VideoStudioForm


#! 格式化檔案大小
def format_size(size_in_bytes):
    if size_in_bytes < 1024 * 1024:
        return f"{size_in_bytes / 1024:.2f} KB"
    return f"{size_in_bytes / (1024 * 1024):.2f} MB"


def media_studio_view(request):
    #! 整合圖片與影片處理的統一視圖
    context = {
        "title": _("多媒體處理工作室"),
        "image_form": ImageCompressForm(),
        "video_form": VideoStudioForm(),
        "active_tab": "image",  # * 預設顯示圖片頁籤
    }

    if request.method == "POST":
        action = request.POST.get("action")

        #! 處理圖片壓縮與去背
        if action == "image":
            context["active_tab"] = "image"
            form = ImageCompressForm(request.POST, request.FILES)
            if form.is_valid():
                uploaded_file = form.cleaned_data["image"]
                remove_bg = form.cleaned_data["remove_bg"]
                scale_percent = form.cleaned_data["scale_percent"]
                quality = form.cleaned_data["quality"]
                output_format = form.cleaned_data["output_format"]

                original_size = uploaded_file.size
                img = Image.open(uploaded_file)
                original_width, original_height = img.size

                if remove_bg:
                    from rembg import remove
                    img = remove(img)

                if output_format == "JPEG" and img.mode in ("RGBA", "P"):  # pyright: ignore[reportAttributeAccessIssue]
                    background = Image.new("RGB", img.size, (255, 255, 255))  # pyright: ignore[reportAttributeAccessIssue, reportArgumentType]
                    if img.mode == "RGBA":  # pyright: ignore[reportAttributeAccessIssue]
                        background.paste(img, mask=img.split()[3])  # pyright: ignore[reportArgumentType, reportAttributeAccessIssue]
                    else:
                        background.paste(img)  # pyright: ignore[reportArgumentType]
                    img = background

                new_width, new_height = original_width, original_height
                if scale_percent < 100:
                    new_width = int(original_width * (scale_percent / 100.0))
                    new_height = int(original_height * (scale_percent / 100.0))
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)  # pyright: ignore[reportArgumentType, reportAttributeAccessIssue]

                buffer = BytesIO()
                if output_format == "PNG":
                    img.save(buffer, format="PNG", optimize=True)  # pyright: ignore[reportAttributeAccessIssue, reportOptionalMemberAccess]
                    ext = ".png"
                    content_type = "image/png"
                elif output_format == "WEBP":
                    img.save(buffer, format="WEBP", quality=quality, method=6)  # pyright: ignore[reportAttributeAccessIssue, reportOptionalMemberAccess]
                    ext = ".webp"
                    content_type = "image/webp"
                else:
                    img.save(buffer, format="JPEG", quality=quality, optimize=True)  # pyright: ignore[reportAttributeAccessIssue, reportOptionalMemberAccess]
                    ext = ".jpg"
                    content_type = "image/jpeg"

                buffer.seek(0)
                compressed_size = len(buffer.getvalue())
                b64_encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")

                context.update(
                    {
                        "image_compressed_uri": f"data:{content_type};base64,{b64_encoded}",
                        "image_orig_size": format_size(original_size),
                        "image_comp_size": format_size(compressed_size),
                        "image_orig_dim": f"{original_width} x {original_height} px",
                        "image_new_dim": f"{new_width} x {new_height} px",
                        "image_new_name": f"{os.path.splitext(uploaded_file.name)[0]}_processed{ext}",
                    }
                )
            context["image_form"] = form

        #! 處理影片裁切與拼接
        elif action == "video":
            context["active_tab"] = "video"
            form = VideoStudioForm(request.POST, request.FILES)
            if form.is_valid():
                video_files = request.FILES.getlist("videos")
                quality = form.cleaned_data["quality"]
                res_scale = form.cleaned_data["resolution_scale"]

                #! 讀取前端動態產生的片段資料陣列
                fragment_indices = request.POST.getlist("f_idx[]")
                start_times = request.POST.getlist("f_start[]")
                end_times = request.POST.getlist("f_end[]")

                crf_val = int(51 - (quality / 100 * 30))

                with tempfile.TemporaryDirectory() as tmp_dir:
                    import ffmpeg
                    input_paths = []
                    #! 儲存所有上傳的原始檔案
                    for idx, vf in enumerate(video_files):
                        tmp_path = os.path.join(tmp_dir, f"input_{idx}_{vf.name}")
                        with open(tmp_path, "wb+") as destination:
                            for chunk in vf.chunks():
                                destination.write(chunk)
                        input_paths.append(tmp_path)

                    output_path = os.path.join(tmp_dir, "output.mp4")

                    try:
                        input_streams = []

                        #! 如果沒抓到片段(防呆)，預設整段接起來
                        if not fragment_indices:
                            fragment_indices = list(range(len(input_paths)))
                            start_times = [0] * len(input_paths)
                            end_times = [0] * len(input_paths)

                        #! 依照片段的 HTML 順序依序處理
                        for i in range(len(fragment_indices)):
                            file_idx = int(fragment_indices[i])
                            ss = float(start_times[i]) if start_times[i] else 0.0
                            to = float(end_times[i]) if end_times[i] else 0.0

                            #! 計算持續時間，若終點為 0，則不限制長度 (取至結束)
                            dur = (to - ss) if to > ss else None

                            in_file = ffmpeg.input(input_paths[file_idx])
                            v = in_file.video
                            a = in_file.audio

                            #! 動態套用裁切參數
                            trim_kwargs = {"start": ss}
                            if dur is not None:
                                trim_kwargs["duration"] = dur

                            if ss > 0 or dur is not None:
                                v = v.trim(**trim_kwargs).filter("setpts", "PTS-STARTPTS")
                                a = a.filter("atrim", **trim_kwargs).filter(
                                    "asetpts", "PTS-STARTPTS"
                                )

                            #! 處理解析度縮放
                            if res_scale == "1080":
                                v = v.filter(
                                    "scale", 1920, 1080, force_original_aspect_ratio="decrease"
                                ).filter("pad", 1920, 1080, "(ow-iw)/2", "(oh-ih)/2")
                            elif res_scale == "720":
                                v = v.filter(
                                    "scale", 1280, 720, force_original_aspect_ratio="decrease"
                                ).filter("pad", 1280, 720, "(ow-iw)/2", "(oh-ih)/2")

                            input_streams.append(v)
                            input_streams.append(a)

                        #! 執行拼接
                        joined = ffmpeg.concat(*input_streams, v=1, a=1).node
                        (
                            ffmpeg.output(
                                joined[0],
                                joined[1],
                                output_path,
                                vcodec="libx264",
                                crf=crf_val,
                                preset="fast",
                                acodec="aac",
                            )
                            .overwrite_output()
                            .run(capture_stdout=True, capture_stderr=True)
                        )

                        original_total_size = sum(f.size for f in video_files)
                        compressed_size = os.path.getsize(output_path)

                        with open(output_path, "rb") as f:
                            b64_data = base64.b64encode(f.read()).decode("utf-8")

                        context.update(
                            {
                                "video_compressed_uri": f"data:video/mp4;base64,{b64_data}",
                                "video_orig_size": format_size(original_total_size),
                                "video_comp_size": format_size(compressed_size),
                                "video_res_info": f"{res_scale}P"
                                if res_scale != "original"
                                else _("原始解析度"),
                                "video_new_name": "processed_video.mp4",
                            }
                        )

                    except ffmpeg.Error as e:
                        context["video_error"] = e.stderr.decode("utf8").splitlines()[-5:]

            context["video_form"] = form

    return render(request, "media_studio/studio.html", context)
