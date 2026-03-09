from django.contrib import admin

from .models import Holding, Portfolio, Stock, StockPrice, Transaction


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ("symbol", "name", "category", "exchange", "is_active")
    search_fields = ("symbol", "name")  # * 👈 讓你可以直接在後台用代碼或名稱搜尋
    list_filter = ("category", "exchange", "is_active")
    ordering = ("symbol",)


@admin.register(StockPrice)
class StockPriceAdmin(admin.ModelAdmin):
    list_display = ("stock", "current_price", "daily_change", "daily_change_percent", "updated_at")
    search_fields = ("stock__symbol", "stock__name")


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "created_at")
    search_fields = ("name", "user__username")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "stock", "transaction_type", "shares", "price_per_share", "fee", "trade_date")
    list_filter = ("transaction_type", "trade_date", "portfolio")
    search_fields = ("stock__symbol", "stock__name", "portfolio__name")
    date_hierarchy = "trade_date"  # * 👈 在上方加入日期篩選時間軸


@admin.register(Holding)
class HoldingAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "stock", "total_shares", "average_cost", "last_updated")
    search_fields = ("stock__symbol", "stock__name", "portfolio__name")
    list_filter = ("portfolio",)
    #! 💡 重要：將自動計算的欄位設為唯讀，確保資料是由 Transaction 算出來的，不能手動亂改
    readonly_fields = ("total_shares", "average_cost", "portfolio", "stock")

    def has_add_permission(self, request):
        #! 禁止在後台手動「新增」庫存，強制規定只能透過交易(Transaction)產生
        return False
