from django.contrib import admin

from .models import Announcement


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    #! 列表頁面顯示的欄位
    list_display = ("is_pinned", "title", "author", "is_active", "created_at")

    #! 點擊哪些欄位可以進入編輯頁面
    list_display_links = ("title",)

    #! 右側篩選過濾器
    list_filter = ("is_pinned", "is_active", "created_at")

    #! 搜尋欄位 (搜尋標題或作者帳號)
    search_fields = ("title", "author__username")

    #! 讓置頂按鈕可以直接在列表頁勾選修改 (選配)
    list_editable = ("is_pinned", "is_active")

    #! 自動填入發布者為當前登入的使用者 (進階功能)
    def save_model(self, request, obj, form, change):
        if not change:  # * 只有在「新增」時才自動設定作者
            obj.author = request.user
        super().save_model(request, obj, form, change)