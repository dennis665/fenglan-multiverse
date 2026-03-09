from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django_apscheduler.admin import DjangoJobAdmin, DjangoJobExecutionAdmin
from django_apscheduler.models import DjangoJob, DjangoJobExecution

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

#! 第三方套件更改
try:
    admin.site.unregister(DjangoJob)
    admin.site.unregister(DjangoJobExecution)
except admin.sites.NotRegistered:
    pass


#! 建立自訂的 Admin，繼承原本的邏輯，只覆寫顯示名稱
@admin.register(DjangoJob)
class CustomDjangoJobAdmin(DjangoJobAdmin):
    #! 包裝原本的方法，並掛上新的 i18n 翻譯標籤
    def average_duration(self, obj):
        return super().average_duration(obj)

    average_duration.short_description = _("平均耗時 (秒)")

    def local_run_time(self, obj):
        return super().local_run_time(obj)

    local_run_time.short_description = _("下次執行時間")

    #! 覆寫 Action 的名稱
    def run_selected_jobs(self, request, queryset):
        return super().run_selected_jobs(request, queryset)

    run_selected_jobs.short_description = _("立刻執行選定的任務")


@admin.register(DjangoJobExecution)
class CustomDjangoJobExecutionAdmin(DjangoJobExecutionAdmin):
    def html_status(self, obj):
        return super().html_status(obj)

    html_status.short_description = _("狀態標籤")

    def local_run_time(self, obj):
        return super().local_run_time(obj)

    local_run_time.short_description = _("本地執行時間")

    def duration_text(self, obj):
        return super().duration_text(obj)

    duration_text.short_description = _("實際耗時")