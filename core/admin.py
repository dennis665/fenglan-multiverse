from django.contrib import admin

from .models import FeatureStatus


#! admin.py
@admin.register(FeatureStatus)
class FeatureStatusAdmin(admin.ModelAdmin):
    list_display = (
        "sort_order",
        "name",
        "is_active",
        "guest_access",
        "user_access",
        "staff_access",
        "superuser_access",
    )
    list_editable = ("sort_order", "is_active", "guest_access", "user_access", "staff_access", "superuser_access")
    list_display_links = ("name",)
    list_filter = ("is_active",)
