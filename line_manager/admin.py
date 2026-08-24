from django.contrib import admin, messages
from .models import AnimeFranchise, Drama, GroupMembership, Itinerary, LineProfile


def cleanup_empty_franchises():
    """輔助函數：自動清除已被移空、無任何劇集的舊作品系列"""
    empty_qs = AnimeFranchise.objects.filter(dramas__isnull=True)
    count = empty_qs.count()
    empty_qs.delete()
    return count


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
        try:
            decrypted_title = obj.title
            return decrypted_title
        except Exception:
            return "🔒 密文 (無法解密)"

    display_title.short_description = "行程標題 (已解密)"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs.filter(user=request.user)
        return qs.filter(user=request.user)

    def has_view_permission(self, request, obj=None):
        if obj is not None and obj.user != request.user:
            return False
        return super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.user != request.user:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.user != request.user:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "group_id", "created_at"]
    search_fields = ["user__username", "group_id"]


class DramaInline(admin.TabularInline):
    model = Drama
    extra = 0
    fields = ["title", "category", "media_type", "total_seasons", "total_episodes"]
    readonly_fields = ["title", "category"]
    can_delete = True
    show_change_link = True


@admin.register(AnimeFranchise)
class AnimeFranchiseAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "dramas_count", "created_at", "updated_at"]
    search_fields = ["name", "description"]
    inlines = [DramaInline]
    actions = ["merge_selected_franchises", "cleanup_empty_franchises_action"]

    def dramas_count(self, obj):
        return obj.dramas.count()

    dramas_count.short_description = "關聯劇集數"

    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        cleanup_empty_franchises()

    @admin.action(description="🔀 合併所選作品系列 (轉移所有劇集至第一個系列，並刪除其餘舊系列)")
    def merge_selected_franchises(self, request, queryset):
        franchises = list(queryset.order_by("id"))
        if len(franchises) < 2:
            self.message_user(request, "請至少勾選 2 個以上的作品系列進行合併！", level=messages.WARNING)
            return

        target_franchise = franchises[0]
        source_franchises = franchises[1:]

        total_moved = 0
        for src in source_franchises:
            dramas = src.dramas.all()
            moved_count = dramas.count()
            dramas.update(franchise=target_franchise)
            total_moved += moved_count
            src.delete()

        self.message_user(
            request,
            f"✅ 合併成功！已將 {len(source_franchises)} 個舊系列中的 {total_moved} 部劇集轉移併入【{target_franchise.name}】，並已自動刪除舊系列！",
            level=messages.SUCCESS,
        )

    @admin.action(description="🧹 清除所有空的舊系列 (無任何關聯劇集者)")
    def cleanup_empty_franchises_action(self, request, queryset):
        deleted_count = cleanup_empty_franchises()
        self.message_user(
            request,
            f"✅ 清理完成！共刪除了 {deleted_count} 個未關聯任何劇集的空系列。",
            level=messages.SUCCESS,
        )


@admin.register(Drama)
class DramaAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "title",
        "category",
        "franchise",
        "media_type",
        "total_seasons",
        "total_episodes",
        "created_at",
    ]
    list_filter = ["media_type", "category", "franchise"]
    search_fields = ["title", "category", "franchise__name"]
    list_editable = ["franchise", "media_type"]
    autocomplete_fields = ["franchise"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        cleanup_empty_franchises()

    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        cleanup_empty_franchises()

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        cleanup_empty_franchises()

    def delete_queryset(self, request, queryset):
        super().delete_queryset(request, queryset)
        cleanup_empty_franchises()
