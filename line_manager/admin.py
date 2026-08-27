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
    readonly_fields = ["github_media_picker"]
    fields = [
        "title",
        "category",
        "franchise",
        "media_type",
        "total_seasons",
        "total_episodes",
        "image_url",
        "github_media_picker",
        "mp3_links",
        "mp4_links",
        "info_links",
        "creator",
    ]

    def github_media_picker(self, obj):
        from django.utils.safestring import mark_safe
        return mark_safe("""
            <div style="background: #1e1e2d; color: #fff; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                <h4 style="margin-top: 0; color: #00f2fe;">🔍 GitHub (fenglan-media-assets/video) 影音速查與自動帶入工具</h4>
                <p style="font-size: 0.85rem; color: #aaa; margin-bottom: 10px;">點擊下方按鈕讀取 GitHub video 目錄檔案，可搜尋、選擇 MP3 或 MP4，點擊按鈕自動寫入下方欄位。</p>
                <button type="button" class="button" onclick="openGitHubMediaPicker()" style="background: #4facfe; color: #fff; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; cursor: pointer;">
                    🚀 載入當前劇集影音
                </button>
                <a href="/admin/line_manager/drama/github_media_manager/" class="button" style="background: #00f2fe; color: #000; font-weight: bold; margin-left: 10px; padding: 8px 16px; border-radius: 4px; text-decoration: none; display: inline-block;">
                    🎬 開啟全影音反向批次指定與對應儀表板
                </a>
                <div id="gh-picker-results" style="display: none; margin-top: 15px; max-height: 380px; overflow-y: auto; background: #151521; padding: 12px; border-radius: 6px; border: 1px solid #333;">
                    <input type="text" id="gh-picker-search" placeholder="輸入關鍵字搜尋檔名 (如：芙莉蓮)..." onkeyup="filterGitHubFiles()" style="width: 100%; padding: 8px 12px; margin-bottom: 10px; border-radius: 4px; border: 1px solid #444; background: #222; color: #fff; font-size: 0.9rem;">
                    <div style="display: flex; gap: 20px;">
                        <div style="flex: 1;">
                            <h5 style="color: #00f2fe; margin: 5px 0 10px 0;">🎵 MP3 音樂清單</h5>
                            <div id="gh-mp3-list" style="max-height: 240px; overflow-y: auto;"></div>
                        </div>
                        <div style="flex: 1;">
                            <h5 style="color: #ffb703; margin: 5px 0 10px 0;">🎬 MP4 影片清單</h5>
                            <div id="gh-mp4-list" style="max-height: 240px; overflow-y: auto;"></div>
                        </div>
                    </div>
                    <div style="margin-top: 15px; text-align: right; border-top: 1px solid #333; padding-top: 10px;">
                        <button type="button" class="button" onclick="applySelectedGitHubFiles()" style="background: #28a745; color: #fff; padding: 8px 16px; border-radius: 4px; font-weight: bold; cursor: pointer;">
                            ✅ 將勾選的檔案帶入下方欄位
                        </button>
                    </div>
                </div>
            </div>
            <script>
                let allGitHubFiles = [];
                function openGitHubMediaPicker() {
                    const resDiv = document.getElementById('gh-picker-results');
                    resDiv.style.display = 'block';
                    if (allGitHubFiles.length > 0) return;

                    fetch('/line/api/dramas/github_media_list/')
                        .then(res => res.json())
                        .then(data => {
                            if (data.status === 'success') {
                                allGitHubFiles = data.files || [];
                                renderGitHubFilesList();
                            } else {
                                alert('載入失敗：' + data.error);
                            }
                        })
                        .catch(err => alert('連線失敗: ' + err));
                }

                function renderGitHubFilesList(filterStr = '') {
                    const mp3Div = document.getElementById('gh-mp3-list');
                    const mp4Div = document.getElementById('gh-mp4-list');
                    mp3Div.innerHTML = '';
                    mp4Div.innerHTML = '';

                    const currentTitle = (document.getElementById('id_title')?.value || '').trim();

                    allGitHubFiles.forEach(f => {
                        if (filterStr && !f.name.toLowerCase().includes(filterStr.toLowerCase())) return;

                        const isAutoMatch = currentTitle && f.name.includes(currentTitle);
                        const label = `<label style="display: block; margin-bottom: 6px; font-size: 0.85rem; color: #ddd; cursor: pointer;">
                            <input type="checkbox" class="gh-file-cb" data-name="${f.name}" data-title="${f.title}" data-url="${f.url}" data-type="${f.type}" ${isAutoMatch ? 'checked' : ''}>
                            ${f.name}
                        </label>`;

                        if (f.type === 'mp3') mp3Div.innerHTML += label;
                        else if (f.type === 'mp4') mp4Div.innerHTML += label;
                    });
                }

                function filterGitHubFiles() {
                    const q = document.getElementById('gh-picker-search').value;
                    renderGitHubFilesList(q);
                }

                function applySelectedGitHubFiles() {
                    const cbs = document.querySelectorAll('.gh-file-cb:checked');
                    const mp3s = [];
                    const mp4s = [];

                    cbs.forEach(cb => {
                        const item = {
                            title: cb.getAttribute('data-title'),
                            url: cb.getAttribute('data-url')
                        };
                        if (cb.getAttribute('data-type') === 'mp3') mp3s.push(item);
                        else if (cb.getAttribute('data-type') === 'mp4') mp4s.push(item);
                    });

                    const mp3Field = document.getElementById('id_mp3_links');
                    const mp4Field = document.getElementById('id_mp4_links');

                    if (mp3Field && mp3s.length > 0) mp3Field.value = JSON.stringify(mp3s, null, 2);
                    if (mp4Field && mp4s.length > 0) mp4Field.value = JSON.stringify(mp4s, null, 2);

                    alert(`已成功帶入 ${mp3s.length} 首 MP3 與 ${mp4s.length} 支 MP4 連結！請記得點擊頁面下方「儲存」按鈕。`);
                }
            </script>
        """)

    github_media_picker.short_description = "GitHub 媒體連線工具"

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                "github_media_manager/",
                self.admin_site.admin_view(self.github_media_manager_view),
                name="drama_github_media_manager",
            ),
        ]
        return custom_urls + urls

    def github_media_manager_view(self, request):
        from django.shortcuts import render
        import json
        from .models import Drama

        dramas_qs = Drama.objects.all().order_by("title")
        dramas_list = []
        for d in dramas_qs:
            mp3_list = []
            if d.mp3_links:
                try:
                    mp3_list = json.loads(d.mp3_links)
                except Exception:
                    pass
            mp4_list = []
            if d.mp4_links:
                try:
                    mp4_list = json.loads(d.mp4_links)
                except Exception:
                    pass

            dramas_list.append({
                "id": d.pk,
                "title": d.title,
                "category": d.category,
                "mp3_links": mp3_list,
                "mp4_links": mp4_list
            })

        context = {
            "title": "GitHub 影音反向批次指定與綁定檢查儀表板",
            "dramas_json": json.dumps(dramas_list, ensure_ascii=False),
            "opts": self.model._meta,
        }
        return render(request, "admin/line_manager/drama/github_media_manager.html", context)

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
