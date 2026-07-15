from django.contrib import admin

from .models import (
    DailyLoginLog,
    Pet,
    PetExpedition,
    PetStoryUnlock,
    TowerProgress,
    UserAccessory,
    UserInventory,
    UserPetProfile,
)


@admin.register(Pet)
class PetAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "pet_type", "stage", "is_active", "growth_progress", "personality", "created_at")
    list_filter = ("pet_type", "stage", "is_active", "personality")
    search_fields = ("user__username", "name")


@admin.register(UserPetProfile)
class UserPetProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "pet_gold_coins", "last_daily_claim")
    search_fields = ("user__username",)


@admin.register(UserAccessory)
class UserAccessoryAdmin(admin.ModelAdmin):
    list_display = ("user", "accessory_id", "quantity")
    list_filter = ("accessory_id",)
    search_fields = ("user__username",)


@admin.register(PetExpedition)
class PetExpeditionAdmin(admin.ModelAdmin):
    list_display = ("pet", "duration_hours", "start_time", "end_time", "status")
    list_filter = ("status", "duration_hours")
    search_fields = ("pet__name", "pet__user__username")


@admin.register(TowerProgress)
class TowerProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "current_floor")
    search_fields = ("user__username",)


@admin.register(PetStoryUnlock)
class PetStoryUnlockAdmin(admin.ModelAdmin):
    list_display = ("user", "pet_type", "max_stage_reached")
    list_filter = ("pet_type",)
    search_fields = ("user__username",)


@admin.register(DailyLoginLog)
class DailyLoginLogAdmin(admin.ModelAdmin):
    list_display = ("user", "login_date")
    list_filter = ("login_date",)
    search_fields = ("user__username",)


@admin.register(UserInventory)
class UserInventoryAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "quantity")
    list_filter = ("product",)
    search_fields = ("user__username", "product__name")
