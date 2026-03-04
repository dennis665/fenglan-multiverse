from django.contrib import admin

from .models import PointPackage, Product


@admin.register(PointPackage)
class PointPackageAdmin(admin.ModelAdmin):
    #! 後台列表顯示的欄位
    list_display = ("name", "price", "deposit_points", "bonus_points", "is_active")
    #! 右側篩選器
    list_filter = ("is_active",)
    #! 支援搜尋的欄位
    search_fields = ("name",)
    #! 可在列表直接編輯是否上架
    list_editable = ("is_active",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "price_in_points", "price_ntd", "stock", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    list_editable = ("is_active", "stock")
