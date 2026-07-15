from django.contrib import admin

from .models import TubeFolder, TubeResource


@admin.register(TubeFolder)
class TubeFolderAdmin(admin.ModelAdmin):
    #! 設定收藏資料夾在後台的顯示與管理選項
    list_display = ("name", "user", "folder_type", "created_at")
    list_filter = ("folder_type", "created_at")
    search_fields = ("name", "user__username")
    raw_id_fields = ("user",)


@admin.register(TubeResource)
class TubeResourceAdmin(admin.ModelAdmin):
    #! 設定影音資源在後台的顯示與分區管理選項
    list_display = (
        "title",
        "user",
        "category",
        "folder",
        "is_public",
        "created_at",
    )
    list_filter = ("category", "is_public", "created_at", "folder")
    search_fields = ("title", "url", "user__username", "personal_notes")
    raw_id_fields = ("user", "folder")
    readonly_fields = ("created_at",)

    fieldsets = (
        (None, {"fields": ("url", "title", "category")}),
        ("權限與分類", {"fields": ("user", "folder", "is_public")}),
        ("實體檔案", {"fields": ("video_file", "audio_file")}),
        ("內容與筆記", {"fields": ("primary_content", "secondary_content", "personal_notes")}),
        ("系統資訊", {"fields": ("created_at",)}),
    )
