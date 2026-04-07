import os

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from youtube_transcript_api import YouTubeTranscriptApi
from yt_dlp import YoutubeDL

from .models import TubeFolder, TubeResource


@login_required  #! 重要：必須登入才能區分「我的」資料夾與資源
def search_youtube(request):
    """處理前端關鍵字搜尋請求與資源清單展示"""

    #! 取得未分類的資源
    unfolder_resources = TubeResource.objects.filter(
        user=request.user, folder__isnull=True
    ).order_by("-created_at")

    #! 取得使用者的資料夾，並預先載入 (Prefetch) 裡面的資源，依照時間排序
    my_folders = TubeFolder.objects.filter(user=request.user).prefetch_related(
        Prefetch(
            "tuberesource_set",
            queryset=TubeResource.objects.filter(user=request.user).order_by("-created_at"),
            to_attr="resources",
        )
    )

    #! 更新重點：先取得自己已經收藏的所有資源網址
    my_collected_urls = TubeResource.objects.filter(user=request.user).values_list("url", flat=True)

    #! 在撈取公開資源時，排除掉自己擁有的，以及「來源網址已經存在於我的收藏中」的資源
    public_resources = (
        TubeResource.objects.filter(is_public=True)
        .exclude(user=request.user)
        .exclude(url__in=my_collected_urls)
        .order_by("-created_at")
    )

    if request.method == "GET" and "q" in request.GET:
        query = request.GET.get("q")
        search_query = f"ytsearch5:{query}"
        ydl_opts = {"extract_flat": True, "quiet": True}

        def format_duration(seconds):
            if not seconds:
                return "未知長度"
            seconds = int(seconds)
            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            if h > 0:
                return f"{h}:{m:02d}:{s:02d}"
            return f"{m}:{s:02d}"

        try:
            with YoutubeDL(ydl_opts) as ydl:  # pyright: ignore[reportArgumentType]
                result = ydl.extract_info(search_query, download=False)
                entries = result.get("entries", []) if result else []
                results = []
                for e in entries:
                    video_id = e.get("id")
                    video_url = e.get("url") or (
                        f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
                    )
                    thumbnail_url = (
                        f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else ""
                    )
                    results.append(
                        {
                            "id": video_id,
                            "title": e.get("title", "未知標題"),
                            "url": video_url,
                            "duration": format_duration(e.get("duration")),
                            "thumbnail": thumbnail_url,
                        }
                    )
                return JsonResponse({"status": "success", "data": results})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})

    #! 將分類與資源丟給前端 HTML 渲染
    context = {
        "unfolder_resources": unfolder_resources,
        "my_folders": my_folders,
        "public_resources": public_resources,
    }
    return render(request, "tube_hub/search.html", context)


@csrf_exempt
@login_required
def toggle_public_status(request):
    """切換資源的公開/私有狀態"""
    if request.method == "POST":
        resource_id = request.POST.get("resource_id")
        is_public_str = request.POST.get("is_public", "false")
        is_public = True if is_public_str.lower() == "true" else False

        #! 確保只能修改自己的資源
        resource = get_object_or_404(TubeResource, id=resource_id, user=request.user)
        resource.is_public = is_public
        resource.save()

        return JsonResponse({"status": "success", "is_public": resource.is_public})

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@csrf_exempt
@login_required
def download_resource(request):
    """處理影音雙向下載與字幕自動抓取"""
    if request.method == "POST":
        url = request.POST.get("url")
        title = request.POST.get("title")
        category = request.POST.get("category", "course")
        personal_notes = request.POST.get("personal_notes", "")

        #! 取得前端傳來的資料夾與公開設定
        folder_name = request.POST.get("folder_name", "").strip()
        is_public = request.POST.get("is_public", "false") == "true"

        #! 處理資料夾建立邏輯
        folder_obj = None
        if folder_name:
            folder_obj, _ = TubeFolder.objects.get_or_create(user=request.user, name=folder_name)

        video_id = url.split("v=")[-1].split("&")[0] if "v=" in url else url.split("/")[-1]

        #! 自動抓取與翻譯字幕
        primary_content = "未找到字幕"
        try:
            ytt_api = YouTubeTranscriptApi()
            transcript_list = ytt_api.list(video_id)
            try:
                transcript = transcript_list.find_transcript(["zh-TW", "zh-Hant", "zh"])
                data = transcript.fetch()
                primary_content = "\n".join([t.text for t in data])
            except Exception:
                all_langs = [t.language_code for t in transcript_list]
                if all_langs:
                    transcript = transcript_list.find_transcript(all_langs)
                    original_text = "\n".join([t.text for t in transcript.fetch()])
                    if transcript.is_translatable:
                        translated_text = "\n".join(
                            [t.text for t in transcript.translate("zh-TW").fetch()]
                        )
                        primary_content = f"【自動翻譯 (zh-TW)】\n{translated_text}\n\n{'=' * 30}\n\n【原文 ({transcript.language_code})】\n{original_text}"
                    else:
                        primary_content = f"【原文 ({transcript.language_code})】\n{original_text}"
        except Exception as e:
            print(f"#! 字幕抓取失敗: {str(e)}")

        #! 設定下載路徑
        output_base = os.path.join(settings.MEDIA_ROOT, "tube_hub")
        video_tmpl = os.path.join(output_base, "videos", f"{video_id}.%(ext)s")

        ydl_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": video_tmpl,
            "quiet": True,
            "keepvideo": True,
        }

        #! KTV 模式才轉 MP3
        if category == "ktv":
            ydl_opts["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
            ]

        try:
            with YoutubeDL(ydl_opts) as ydl:  # pyright: ignore[reportArgumentType]
                ydl.download([url])

                video_path = f"tube_hub/videos/{video_id}.mp4"
                audio_path = f"tube_hub/videos/{video_id}.mp3" if category == "ktv" else ""

            #! 儲存至資料庫 (綁定 user, folder, is_public)
            resource, created = TubeResource.objects.update_or_create(
                user=request.user,
                url=url,
                defaults={
                    "title": title,
                    "category": category,
                    "video_file": video_path,
                    "audio_file": audio_path,
                    "primary_content": primary_content,
                    "personal_notes": personal_notes,
                    "folder": folder_obj,
                    "is_public": is_public,
                },
            )
            return JsonResponse({"status": "success", "resource_id": resource.pk})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@csrf_exempt
@login_required
def collect_public_resource(request):
    """一鍵收藏別人的公開資源 (共用檔案)"""
    if request.method == "POST":
        resource_id = request.POST.get("resource_id")
        original = get_object_or_404(TubeResource, id=resource_id, is_public=True)

        new_resource, created = TubeResource.objects.get_or_create(
            user=request.user,
            url=original.url,
            defaults={
                "title": original.title,
                "category": original.category,
                "video_file": original.video_file,
                "audio_file": original.audio_file,
                "primary_content": original.primary_content,
                "secondary_content": original.secondary_content,
                "is_public": False,  #! 預設自己收藏的為私有
            },
        )
        return JsonResponse({"status": "success", "resource_id": new_resource.pk})
    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@csrf_exempt
@login_required
def delete_resource(request):
    """移除個人收藏，若無人引用則刪除實體檔案"""
    if request.method == "POST":
        resource_id = request.POST.get("resource_id")
        resource = get_object_or_404(TubeResource, id=resource_id, user=request.user)

        video_path = resource.video_file.name if resource.video_file else None
        audio_path = resource.audio_file.name if resource.audio_file else None

        resource.delete()

        #! 檢查是否還有其他人收藏，若無則刪除實體檔案釋放空間
        if video_path and not TubeResource.objects.filter(video_file=video_path).exists():
            if default_storage.exists(video_path):
                default_storage.delete(video_path)

        if audio_path and not TubeResource.objects.filter(audio_file=audio_path).exists():
            if default_storage.exists(audio_path):
                default_storage.delete(audio_path)

        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@csrf_exempt
@login_required
def move_resource(request):
    """將影音資源移動到指定資料夾，或移出資料夾"""
    if request.method == "POST":
        resource_id = request.POST.get("resource_id")
        folder_id = request.POST.get("folder_id")  # * 可能為空字串，代表移至根目錄

        #! 確保只能移動自己的資源
        resource = get_object_or_404(TubeResource, id=resource_id, user=request.user)

        if folder_id and folder_id.isdigit():
            folder_obj = get_object_or_404(TubeFolder, id=folder_id, user=request.user)
            resource.folder = folder_obj
        else:
            #! 若 folder_id 為空，代表移出所有資料夾
            resource.folder = None

        resource.save()
        return JsonResponse({"status": "success"})

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@login_required
def player_room(request, resource_id):
    """影音播放與學習頁面"""
    resource = get_object_or_404(TubeResource, id=resource_id)

    #! 安全檢查：確保只能看到自己的，或是公開的資源
    if resource.user != request.user and not resource.is_public:
        return render(request, "403.html")

    return render(request, "tube_hub/player.html", {"resource": resource})