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


@login_required
def search_youtube(request):
    #! 處理前端關鍵字搜尋請求與資源清單展示
    unfolder_resources = TubeResource.objects.filter(
        user=request.user, folder__isnull=True
    ).order_by("-created_at")

    my_folders = TubeFolder.objects.filter(user=request.user).prefetch_related(
        Prefetch(
            "tuberesource_set",
            queryset=TubeResource.objects.filter(user=request.user).order_by("-created_at"),
            to_attr="resources",
        )
    )

    my_collected_urls = TubeResource.objects.filter(user=request.user).values_list("url", flat=True)

    public_resources = (
        TubeResource.objects.filter(is_public=True)
        .exclude(user=request.user)
        .exclude(url__in=my_collected_urls)
        .order_by("-created_at")
    )

    if request.method == "GET" and "q" in request.GET:
        query = request.GET.get("q")
        search_query = f"ytsearch5:{query}"

        ydl_opts = dict(
            extract_flat=True,
            quiet=True,
            extractor_args={"youtube": {"player_client": ["web"]}},
        )

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

                ytt_api = YouTubeTranscriptApi()

                for e in entries:
                    video_id = e.get("id")
                    video_url = e.get("url") or (
                        f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
                    )
                    thumbnail_url = (
                        f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else ""
                    )

                    available_subs = []
                    if video_id:
                        try:
                            transcript_list = ytt_api.list(video_id)
                            for transcript in transcript_list:
                                available_subs.append(transcript.language_code)
                        except Exception:
                            pass

                    results.append(
                        {
                            "id": video_id,
                            "title": e.get("title", "未知標題"),
                            "url": video_url,
                            "duration": format_duration(e.get("duration")),
                            "thumbnail": thumbnail_url,
                            "subtitles": available_subs,
                        }
                    )
                return JsonResponse({"status": "success", "data": results})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})

    context = {
        "unfolder_resources": unfolder_resources,
        "my_folders": my_folders,
        "public_resources": public_resources,
    }
    return render(request, "tube_hub/search.html", context)


@csrf_exempt
@login_required
def toggle_public_status(request):
    #! 切換資源的公開狀態
    if request.method == "POST":
        resource_id = request.POST.get("resource_id")
        is_public_str = request.POST.get("is_public", "false")
        is_public = True if is_public_str.lower() == "true" else False

        resource = get_object_or_404(TubeResource, id=resource_id, user=request.user)
        resource.is_public = is_public
        resource.save()

        return JsonResponse({"status": "success", "is_public": resource.is_public})

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@csrf_exempt
@login_required
def download_resource(request):
    #! 處理影音雙向下載與多語系字幕自動抓取
    if request.method == "POST":
        url = request.POST.get("url")
        title = request.POST.get("title")
        category = request.POST.get("category", "course")
        personal_notes = request.POST.get("personal_notes", "")

        folder_name = request.POST.get("folder_name", "").strip()
        is_public = request.POST.get("is_public", "false") == "true"

        folder_obj = None
        if folder_name:
            default_type = "ktv" if category == "ktv" else "course"
            folder_obj, _ = TubeFolder.objects.get_or_create(
                user=request.user, name=folder_name, defaults={"folder_type": default_type}
            )

        video_id = url.split("v=")[-1].split("&")[0] if "v=" in url else url.split("/")[-1]

        primary_content = "未找到字幕"
        try:
            ytt_api = YouTubeTranscriptApi()
            transcript_list = ytt_api.list(video_id)

            target_lang_groups = {
                "繁簡中文": ["zh-TW", "zh-Hant", "zh", "zh-CN", "zh-Hans"],
                "日文": ["ja"],
                "英文": ["en"],
            }

            found_transcripts_texts = []

            for label, codes in target_lang_groups.items():
                try:
                    transcript = transcript_list.find_transcript(codes)
                    data = transcript.fetch()

                    original_text = "\n".join(
                        [
                            t["text"]
                            if isinstance(t, dict) and "text" in t
                            else getattr(t, "text", "")
                            for t in data
                        ]
                    )
                    found_transcripts_texts.append(
                        f"【{label}字幕 ({transcript.language_code})】\n{original_text}"
                    )
                except Exception:
                    continue

            if found_transcripts_texts:
                primary_content = f"\n\n{'=' * 30}\n\n".join(found_transcripts_texts)
            else:
                primary_content = "未找到中、日、英文字幕"

        except Exception as e:
            print(f"字幕處理失敗: {str(e)}")

        output_base = os.path.join(settings.MEDIA_ROOT, "tube_hub")
        video_tmpl = os.path.join(output_base, "videos", f"{video_id}.%(ext)s")

        ydl_opts = dict(
            format="bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            outtmpl=video_tmpl,
            quiet=True,
            keepvideo=True,
            extractor_args={"youtube": {"player_client": ["web"]}},
            http_headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            },
            ignoreerrors=True,
        )

        if category == "ktv":
            ydl_opts["postprocessors"] = [  # pyright: ignore[reportArgumentType]
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
            ]

        try:
            with YoutubeDL(ydl_opts) as ydl:  # pyright: ignore[reportArgumentType]
                ydl.download([url])

                video_path = f"tube_hub/videos/{video_id}.mp4"
                audio_path = f"tube_hub/videos/{video_id}.mp3" if category == "ktv" else ""

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
    #! 一鍵收藏公開資源
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
                "is_public": False,
            },
        )
        return JsonResponse({"status": "success", "resource_id": new_resource.pk})
    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@csrf_exempt
@login_required
def delete_resource(request):
    #! 移除個人收藏
    if request.method == "POST":
        resource_id = request.POST.get("resource_id")
        resource = get_object_or_404(TubeResource, id=resource_id, user=request.user)

        video_path = resource.video_file.name if resource.video_file else None
        audio_path = resource.audio_file.name if resource.audio_file else None

        resource.delete()

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
    #! 移動資源
    if request.method == "POST":
        resource_id = request.POST.get("resource_id")
        folder_id = request.POST.get("folder_id")

        resource = get_object_or_404(TubeResource, id=resource_id, user=request.user)

        if folder_id and folder_id.isdigit():
            folder_obj = get_object_or_404(TubeFolder, id=folder_id, user=request.user)
            resource.folder = folder_obj
        else:
            resource.folder = None

        resource.save()
        return JsonResponse({"status": "success"})

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@csrf_exempt
@login_required
def update_notes(request):
    #! 更新使用者的個人筆記
    if request.method == "POST":
        resource_id = request.POST.get("resource_id")
        notes_content = request.POST.get("notes_content", "")

        resource = get_object_or_404(TubeResource, id=resource_id, user=request.user)
        resource.personal_notes = notes_content
        resource.save()

        return JsonResponse({"status": "success", "message": "筆記已儲存"})

    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


@login_required
def player_room(request, resource_id):
    #! 影音播放與學習頁面
    resource = get_object_or_404(TubeResource, id=resource_id)

    if resource.user != request.user and not resource.is_public:
        return render(request, "403.html")

    playlist_items = []
    if resource.folder and resource.folder.folder_type == "ktv":
        playlist_items = list(
            TubeResource.objects.filter(folder=resource.folder)
            .order_by("created_at")
            .values("id", "title")
        )

    return render(
        request, "tube_hub/player.html", {"resource": resource, "playlist_items": playlist_items}
    )