import os

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from youtube_transcript_api import YouTubeTranscriptApi
from yt_dlp import YoutubeDL

from .models import TubeResource


def search_youtube(request):
    """處理前端關鍵字搜尋請求"""
    # * 獲取所有已下載資源供清單顯示
    resources = TubeResource.objects.all().order_by("-created_at")

    if request.method == "GET" and "q" in request.GET:
        query = request.GET.get("q")
        search_query = f"ytsearch5:{query}"
        ydl_opts = {"extract_flat": True, "quiet": True}

        #! 將秒數轉換為 MM:SS 或 HH:MM:SS 的小工具
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
                    video_url = e.get("url")
                    if not video_url and video_id:
                        video_url = f"https://www.youtube.com/watch?v={video_id}"

                    #! 利用 YouTube 官方的圖片伺服器直接取得高畫質縮圖 (hqdefault.jpg)
                    thumbnail_url = (
                        f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else ""
                    )

                    results.append(
                        {
                            "id": video_id,
                            "title": e.get("title", "未知標題"),
                            "url": video_url,
                            "duration": format_duration(e.get("duration")),
                            "thumbnail": thumbnail_url,  # * 新增預覽圖網址
                        }
                    )

                return JsonResponse({"status": "success", "data": results})
        except Exception as e:
            print(f"❌ yt-dlp 搜尋發生錯誤: {str(e)}")
            return JsonResponse({"status": "error", "message": str(e)})

    return render(request, "tube_hub/search.html", {"resources": resources})


@csrf_exempt
def download_resource(request):
    """處理影音雙向下載與字幕自動抓取"""
    if request.method == "POST":
        url = request.POST.get("url")
        title = request.POST.get("title")
        category = request.POST.get("category", "course")
        personal_notes = request.POST.get("personal_notes", "")

        #! 取得影片 ID 供字幕抓取使用
        video_id = url.split("v=")[-1].split("&")[0] if "v=" in url else url.split("/")[-1]

        #! 自動抓取原生字幕 (Primary Content)
        primary_content = ""
        try:
            transcript = YouTubeTranscriptApi.get_transcript(  # pyright: ignore[reportAttributeAccessIssue]
                video_id, languages=["zh-TW", "en", "ja"]
            )
            primary_content = "\n".join([t["text"] for t in transcript])
        except Exception:
            primary_content = "未找到原生字幕"

        #! 同時下載影片與音檔
        output_base = os.path.join(settings.MEDIA_ROOT, "tube_hub")
        ydl_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": os.path.join(output_base, "videos", f"{video_id}.%(ext)s"),
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            #! 讓 yt-dlp 執行完後保留原本影片
            "keepvideo": True,
            "quiet": True,
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:  # pyright: ignore[reportArgumentType]
                ydl.download([url])
                video_path = f"tube_hub/videos/{video_id}.mp4"
                audio_path = f"tube_hub/videos/{video_id}.mp3"  # * yt-dlp 預設會放在同資料夾

            #! 儲存至資料庫
            resource, created = TubeResource.objects.update_or_create(
                url=url,
                defaults={
                    "title": title,
                    "category": category,
                    "video_file": video_path,
                    "audio_file": audio_path,
                    "primary_content": primary_content,
                    "personal_notes": personal_notes,
                },
            )
            return JsonResponse({"status": "success", "resource_id": resource.pk})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


def player_room(request, resource_id):
    """影音播放與學習頁面"""
    resource = get_object_or_404(TubeResource, id=resource_id)
    return render(request, "tube_hub/player.html", {"resource": resource})
