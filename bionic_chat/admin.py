from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import ChatHistory


@admin.register(ChatHistory)
class ChatHistoryAdmin(admin.ModelAdmin):
    #! 設定列表顯示欄位
    list_display = ("id", "display_user_message", "display_bot_response", "created_at")

    #! 設定可點擊進入編輯頁面的欄位
    list_display_links = ("id", "display_user_message")

    #! 設定側邊過濾器 (可用時間篩選)
    list_filter = ("created_at",)

    #! 設定搜尋欄位 (可搜尋對話內容)
    search_fields = ("user_message", "bot_response")

    #! 設定預設排序 (依時間倒序)
    ordering = ("-created_at",)

    #! 設定每頁顯示數量
    list_per_page = 20

    #! 自定義顯示方法，避免列表頁面被長文字撐破
    def display_user_message(self, obj):
        return obj.user_message[:30] + "..." if len(obj.user_message) > 30 else obj.user_message

    display_user_message.short_description = _("使用者內容截斷")

    def display_bot_response(self, obj):
        return obj.bot_response[:30] + "..." if len(obj.bot_response) > 30 else obj.bot_response

    display_bot_response.short_description = _("仿生人回覆截斷")