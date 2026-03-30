from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import GameProfile, SurvivorLevel, SurvivorMonster


@admin.register(GameProfile)
class GameProfileAdmin(admin.ModelAdmin):
    """玩家遊戲存檔後台管理"""

    #! 列表顯示的欄位
    list_display = ("user", "total_coins", "survivor_max_time", "survivor_max_kills")
    #! 支援透過使用者名稱搜尋
    search_fields = ("user__username", "user__email")

    #! 詳細頁面的欄位分組區塊
    fieldsets = (
        (_("基本資訊"), {"fields": ("user", "total_coins")}),
        (_("倖存者生存 - 遊戲紀錄"), {"fields": ("survivor_max_time", "survivor_max_kills")}),
        (_("倖存者生存 - 局外成長等級"), {"fields": ("survivor_hp_lv", "survivor_atk_lv", "survivor_speed_lv")}),
    )


@admin.register(SurvivorLevel)
class SurvivorLevelAdmin(admin.ModelAdmin):
    """倖存者關卡設定後台管理"""

    #! 列表顯示的欄位
    list_display = ("name", "time_limit", "spawn_rate_mult", "stat_mult", "win_bonus")
    #! 搜尋與過濾器
    search_fields = ("name",)
    list_filter = ("time_limit", "win_bonus")


@admin.register(SurvivorMonster)
class SurvivorMonsterAdmin(admin.ModelAdmin):
    """倖存者怪物圖鑑後台管理"""

    #! 列表顯示的欄位 (加入自訂的縮圖預覽)
    list_display = ("name", "image_preview", "base_hp", "base_atk", "base_speed", "base_size")
    search_fields = ("name",)

    def image_preview(self, obj):
        """在後台列表顯示怪物縮圖預覽"""
        if obj.image:
            #! 裁切成圓形縮圖，方便確認實際在 Canvas 中呈現的樣子
            return format_html(
                '<img src="{}" style="width: 35px; height: 35px; object-fit: cover; border-radius: 50%; border: 1px solid #ccc;" />',
                obj.image.url,
            )
        return "-"

    #! 設定欄位顯示名稱
    image_preview.short_description = _("圖片預覽")
