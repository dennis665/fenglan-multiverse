#! tube_hub 後台管理設定
from django.contrib import admin

from .models import TubeResource


@admin.register(TubeResource)
class TubeResourceAdmin(admin.ModelAdmin):
    """影音資源庫的後台管理設定"""

    #! 列表頁面顯示的欄位 (加入 category 讓分類更清楚)
    list_display = (
        "title",
        "category",
        "url",
        "created_at",
    )

    #! 列表頁面右側的過濾器 (可以快速篩選是課程還是 KTV)
    list_filter = (
        "category",
        "created_at",
    )

    #! 提供搜尋的欄位
    search_fields = (
        "title",
        "url",
        "primary_content",
        "secondary_content",
        "personal_notes",
    )

    #! 設定唯讀欄位，避免修改建立時間發生錯誤
    readonly_fields = ("created_at",)

    #! 詳細頁面的欄位分區顯示設定
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "url",
                    "title",
                    "category",
                ),
            },
        ),
        (
            "實體檔案",
            {
                "fields": (
                    "video_file",
                    "audio_file",
                ),
            },
        ),
        (
            "學習與 AI 內容",
            {
                "fields": (
                    "primary_content",
                    "secondary_content",
                    "personal_notes",
                ),
            },
        ),
        (
            "系統資訊",
            {
                "fields": ("created_at",),
                "classes": ("collapse",),
            },
        ),
    )
