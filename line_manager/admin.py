from django.contrib import admin

from .models import GroupMembership, Itinerary, LineProfile


@admin.register(LineProfile)
class LineProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "line_display_name", "line_user_id", "created_at"]
    search_fields = ["user__username", "line_display_name", "line_user_id"]


@admin.register(Itinerary)
class ItineraryAdmin(admin.ModelAdmin):
    list_display = ["display_title", "activity_type", "date_time", "location", "notify_minutes_before", "is_notified", "user"]
    list_filter = ["activity_type", "is_notified", "date_time"]
    search_fields = ["user__username"]

    def display_title(self, obj):
        # * 為確保絕對隱私，非本人讀取時，不解密顯示行程標題，直接以密碼鎖標記表示。
        # * 如果是擁有者本人，則展示解密後的明文標題。
        # * 注意：在 Admin 後台，通常 request.user 就是目前登入的管理者本身。
        # * 如果管理者要看他人的資料，只會看到 "🔒 私密行程 (限本人閱讀)"。
        try:
            # 嘗試解密 title
            decrypted_title = obj.title
            return decrypted_title
        except Exception:
            return "🔒 密文 (無法解密)"

    display_title.short_description = "行程標題 (已解密)"

    def get_queryset(self, request):
        """強迫限制 queryset，任何管理員進後台只能看見自己建立的行程，防止窺探他人隱私"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            # 即使是超級管理員，也只展示自己的行程（防範越權）
            # 如果希望完全對 Admin 隱藏所有行程，可以直接返回空 queryset: return qs.none()
            # 這裡我們允許他管理自己的行程
            return qs.filter(user=request.user)
        return qs.filter(user=request.user)

    def has_view_permission(self, request, obj=None):
        """禁止檢視他人名下的行程"""
        if obj is not None and obj.user != request.user:
            return False
        return super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        """禁止修改他人名下的行程"""
        if obj is not None and obj.user != request.user:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """禁止刪除他人名下的行程"""
        if obj is not None and obj.user != request.user:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "group_id", "created_at"]
    search_fields = ["user__username", "group_id"]
