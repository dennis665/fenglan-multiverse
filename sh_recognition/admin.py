#! 後台管理設定
from django.contrib import admin

from .models import AIModel, ImageRecord


@admin.register(AIModel)
class AIModelAdmin(admin.ModelAdmin):
    list_display = ("version_name", "uploaded_at")


@admin.register(ImageRecord)
class ImageRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "used_model", "created_at")
