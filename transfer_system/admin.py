#! transfer_system/admin.py
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django_fsm import TransitionNotAllowed

from .models import Item, TransferRecord


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "created_at")
    search_fields = ("name", "owner__username")


@admin.register(TransferRecord)
class TransferRecordAdmin(admin.ModelAdmin):
    """FSM 自動偵測工作流的管理後台"""

    list_display = ("created_at", "item", "sender", "receiver", "status_badge", "fsm_actions")
    list_filter = ("status", "created_at")
    readonly_fields = ("status", "created_at")  # * 設定為唯讀，強制必須透過 FSM 方法修改

    def status_badge(self, obj):
        status_mapping = {
            "pending": ("#fff3cd", "#856404", _("待處理")),
            "accepted": ("#d4edda", "#155724", _("已接受")),
            "rejected": ("#f8d7da", "#721c24", _("已拒絕")),
            "cancelled": ("#e2e3e5", "#383d41", _("已取消")),
        }
        bg, text, display_name = status_mapping.get(
            obj.status, ("#lightgray", "#black", obj.status)
        )
        return format_html(
            '<span style="background: {}; color: {}; padding: 4px 10px; '
            'border-radius: 12px; font-weight: bold; font-size: 12px;">'
            "{}</span>",
            bg,
            text,
            display_name,
        )

    status_badge.short_description = _("工作流狀態")

    def fsm_actions(self, obj):
        """自動偵測目前物件允許執行的 FSM 狀態按鈕"""
        buttons = []

        #! 獲取當前物件合法可行進的下一個路線
        transitions = obj.get_available_status_transitions()

        styles = {
            "accept": "background: #28a745; color: white;",
            "reject": "background: #dc3545; color: white;",
            "cancel": "background: #6c757d; color: white;",
        }
        names = {
            "accept": _("核准轉移"),
            "reject": _("駁回請求"),
            "cancel": _("強制取消"),
        }

        for t in transitions:
            style = styles.get(t.name, "background: #007bff; color: white;")
            name = names.get(t.name, t.name)
            buttons.append(
                f'<a class="button" style="margin-right: 5px; padding: 4px 8px; '
                f'font-size: 11px; {style}" '
                f'href="fsm-transition/{obj.id}/{t.name}/">{name}</a>'
            )

        #! 利用 mark_safe 將合併後的按鈕標記為安全字串，並安全填充
        if buttons:
            combined_buttons = mark_safe("".join(buttons))
            return format_html("{}", combined_buttons)

        return format_html('<span style="color: #999; font-size: 12px;">{}</span>', _("流程已結束"))

    fsm_actions.short_description = _("FSM 自動化操作")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "fsm-transition/<int:record_id>/<str:method_name>/",
                self.admin_site.admin_view(self.process_fsm_transition),
                name="transfer-record-fsm-transition",
            ),
        ]
        return custom_urls + urls

    def process_fsm_transition(self, request, record_id, method_name):
        """動態反射並執行 Model 上的 FSM 轉換方法"""
        record = self.get_object(request, record_id)
        if record and hasattr(record, method_name):
            try:
                # * 利用 Python 反射動態執行對應的方法 (如 record.accept() 或 record.cancel())
                transition_method = getattr(record, method_name)
                transition_method()
                record.save()
                self.message_user(request, _("工作流狀態轉換成功。"))
            except TransitionNotAllowed:
                self.message_user(request, _("轉換失敗：當前狀態不允許此操作。"), level="error")
        return redirect("admin:transfer_system_transferrecord_changelist")
