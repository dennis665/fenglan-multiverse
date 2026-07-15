from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Stock(models.Model):
    """標的資訊表：存儲股票或 ETF 的基本資料"""

    CATEGORY_CHOICES = [
        ("STOCK", _("股票")),
        ("ETF", _("指數型基金")),
    ]

    symbol = models.CharField(max_length=20, unique=True, verbose_name=_("代碼"))
    name = models.CharField(max_length=100, verbose_name=_("標的名稱"))
    exchange = models.CharField(max_length=20, default="TWSE", verbose_name=_("交易所"))  # * 如: TWSE, OTC, NYSE
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES, default="STOCK", verbose_name=_("類別"))
    is_active = models.BooleanField(default=True, verbose_name=_("啟用狀態"))

    class Meta:
        verbose_name = _("標的資訊")
        verbose_name_plural = _("標的資訊")

    def __str__(self):
        return f"{self.symbol} {self.name}"


class StockPrice(models.Model):
    """行情快取表：定時爬蟲或 API 更新的最新價格"""

    stock = models.OneToOneField(Stock, on_delete=models.CASCADE, related_name="price", verbose_name=_("標的"))
    current_price = models.DecimalField(max_digits=12, decimal_places=4, verbose_name=_("當前股價"))
    daily_change = models.DecimalField(max_digits=10, decimal_places=4, verbose_name=_("今日漲跌"))
    daily_change_percent = models.DecimalField(max_digits=10, decimal_places=4, verbose_name=_("漲跌幅(%)"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("更新時間"))

    class Meta:
        verbose_name = _("行情快取")
        verbose_name_plural = _("行情快取")


class Portfolio(models.Model):
    """投資組合表：一個使用者可以擁有多個不同的組合 (如: 退休計畫、短線操作)"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="portfolios", verbose_name=_("所屬用戶")
    )
    name = models.CharField(max_length=100, verbose_name=_("組合名稱"))
    description = models.TextField(blank=True, verbose_name=_("說明"))
    target_monthly_income = models.DecimalField(
        max_digits=10, decimal_places=0, default=Decimal("30000"), verbose_name=_("每月被動收入目標")
    )
    expected_dividend_yield = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("5.00"), verbose_name=_("預估殖利率(%)")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("建立時間"))

    class Meta:
        verbose_name = _("投資組合")
        verbose_name_plural = _("投資組合")

    def __str__(self):
        return f"{self.user.username} - {self.name}"


class Transaction(models.Model):
    """交易紀錄表：所有買賣動作的原始流水帳 (這是計算損益的來源)"""

    TRANSACTION_TYPES = [
        ("BUY", _("買入")),
        ("SELL", _("賣出")),
        ("DIVIDEND", _("股息")),
    ]

    portfolio = models.ForeignKey(
        Portfolio, on_delete=models.CASCADE, related_name="transactions", verbose_name=_("投資組合")
    )
    stock = models.ForeignKey(Stock, on_delete=models.PROTECT, verbose_name=_("標的"))
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES, verbose_name=_("交易類型"))

    shares = models.DecimalField(max_digits=12, decimal_places=4, verbose_name=_("成交股數"))
    price_per_share = models.DecimalField(max_digits=12, decimal_places=4, verbose_name=_("成交單價"))

    fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"), verbose_name=_("手續費"))
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"), verbose_name=_("稅金"))
    realized_pnl = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0"), verbose_name=_("已實現損益")
    )

    trade_date = models.DateField(verbose_name=_("交易日期"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("建立時間"))

    def save(self, *args, **kwargs):
        #! 在儲存這筆交易之前，我們先自動計算它的已實現損益
        is_new = self.pk is None

        if is_new:
            if self.transaction_type == "BUY":
                #! 買入沒有已實現損益
                self.realized_pnl = Decimal("0")

            elif self.transaction_type == "SELL":
                #! 賣出的損益 = (賣出單價 - 平均成本) * 賣出股數 - 手續費 - 交易稅
                #! 需要先去 Holding 查出你目前的平均成本
                try:
                    holding = Holding.objects.get(portfolio=self.portfolio, stock=self.stock)
                    avg_cost = holding.average_cost
                except Holding.DoesNotExist:
                    avg_cost = Decimal("0")  #! 如果防呆沒做好，沒庫存卻賣出，就當作零成本

                gross_profit = (self.price_per_share - avg_cost) * self.shares
                self.realized_pnl = gross_profit - self.fee - self.tax

            elif self.transaction_type == "DIVIDEND":
                #! 股息的損益 = (每股配息 * 持持有股數) - 匯費/手續費 - 稅金
                #! 這裡的 price_per_share 我們當作「每股配發金額」來用
                gross_dividend = self.price_per_share * self.shares
                self.realized_pnl = gross_dividend - self.fee - self.tax

        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-trade_date", "-created_at"]
        verbose_name = _("交易紀錄")
        verbose_name_plural = _("交易紀錄")

    def __str__(self):
        #! get_transaction_type_display() 會自動回傳翻譯後的選項
        return f"{self.portfolio.name} | {self.get_transaction_type_display()} {self.stock.name}"  # pyright: ignore[reportAttributeAccessIssue]


class Holding(models.Model):
    """當前持股統計表：記錄該組合目前持有哪些標的與成本 (由 Transaction 觸發更新)"""

    portfolio = models.ForeignKey(
        Portfolio, on_delete=models.CASCADE, related_name="holdings", verbose_name=_("投資組合")
    )
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, verbose_name=_("標的"))

    total_shares = models.DecimalField(
        max_digits=15, decimal_places=4, default=Decimal("0"), verbose_name=_("總持股數")
    )
    average_cost = models.DecimalField(
        max_digits=12, decimal_places=4, default=Decimal("0"), verbose_name=_("平均成本")
    )

    last_updated = models.DateTimeField(auto_now=True, verbose_name=_("最後更新時間"))

    class Meta:
        unique_together = ("portfolio", "stock")
        verbose_name = _("當前持股")
        verbose_name_plural = _("當前持股")

    def __str__(self):
        #! 這裡的 "股" 也可以被翻譯
        return f"{self.portfolio.name} - {self.stock.name} ({self.total_shares}{_('股')})"
