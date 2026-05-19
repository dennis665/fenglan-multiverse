import csv

from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.translation import gettext_lazy as _

from .models import Item, TransferRecord


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    """物品管理與 CSV 匯入擴充"""

    list_display = ("name", "owner", "created_at")
    change_list_template = "admin/item_changelist.html"
    exclude = ("owner",)

    def get_urls(self):
        """擴充路由以支援 CSV 上傳頁面"""
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-csv/", self.admin_site.admin_view(self.import_csv), name="import_item_csv"
            ),
        ]
        return custom_urls + urls

    def import_csv(self, request):
        """處理 CSV 檔案上傳與資料解析"""
        if request.method == "POST":
            csv_file = request.FILES.get("csv_file")
            if not csv_file or not csv_file.name.endswith(".csv"):
                messages.error(request, _("請上傳正確的 CSV 檔案"))
                return redirect("..")

            #! 讀取檔案並解析
            file_data = csv_file.read().decode("utf-8").splitlines()
            reader = csv.reader(file_data)
            next(reader, None)  # * 跳過標題列

            for row in reader:
                if len(row) >= 2:
                    #! CSV 欄位對應：物品名稱, 擁有者ID, 物品描述
                    name = row[0]
                    owner_id = row[1]
                    description = row[2] if len(row) > 2 else ""

                    Item.objects.create(name=name, owner_id=owner_id, description=description)

            messages.success(request, _("CSV 匯入成功"))
            return redirect("..")

        return render(request, "admin/csv_upload.html")

    def save_model(self, request, obj, form, change):
        """覆寫儲存邏輯，若為新增則自動將擁有者設為當前使用者"""
        if not obj.pk:
            obj.owner = request.user
        super().save_model(request, obj, form, change)


@admin.register(TransferRecord)
class TransferRecordAdmin(admin.ModelAdmin):
    """轉移紀錄管理"""

    list_display = ("item", "sender", "receiver", "status", "created_at")
