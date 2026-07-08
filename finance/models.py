from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserPoints(models.Model):
    """錢包餘額 (與 User 一對一)"""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet", verbose_name=_("使用者"))
    deposit_points = models.PositiveIntegerField(default=0, verbose_name=_("儲值點數"))
    bonus_points = models.PositiveIntegerField(default=0, verbose_name=_("紅利點數"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("更新時間"))

    class Meta:
        verbose_name = _("錢包餘額")
        verbose_name_plural = _("錢包餘額")

    def __str__(self):
        #! 將單位字眼也套用翻譯，確保切換語言時能正確轉換
        return f"{self.user.username} - {_('儲值點數')}：{self.deposit_points} / {_('紅利點數')}：{self.bonus_points}"


class RechargeOrder(models.Model):
    """綠界儲值訂單"""

    STATUS_CHOICES = [
        ("PENDING", _("待付款")),
        ("SUCCESS", _("付款成功")),
        ("FAILED", _("付款失敗")),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("使用者"))

    #! 綠界要求：特店交易編號 (不可重複)
    merchant_trade_no = models.CharField(max_length=50, unique=True, verbose_name=_("特店交易編號"))
    amount = models.PositiveIntegerField(verbose_name=_("儲值金額"))
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING", verbose_name=_("訂單狀態"))
    payment_date = models.DateTimeField(null=True, blank=True, verbose_name=_("付款時間"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("建立時間"))

    class Meta:
        verbose_name = _("綠界儲值訂單")
        verbose_name_plural = _("綠界儲值訂單")


class PointTransaction(models.Model):
    """點數交易流水帳 (包含購物與儲值)"""

    TRANSACTION_TYPES = [
        ("RECHARGE", _("儲值")),
        ("PURCHASE", _("購物扣抵")),
        ("REWARD", _("活動贈送")),
        ("REFUND", _("退貨返還")),
    ]

    POINT_TYPES = [
        ("DEPOSIT", _("儲值點數")),
        ("BONUS", _("紅利點數")),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="point_history", verbose_name=_("使用者"))
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, verbose_name=_("交易類型"))
    point_type = models.CharField(max_length=10, choices=POINT_TYPES, verbose_name=_("點數類型"))

    #! 變動金額：增加為正數，減少為負數
    amount = models.IntegerField(verbose_name=_("變動金額"))

    #! 關聯單號：例如訂單 ID 或 儲值單 ID，方便對帳
    reference_id = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("關聯單號"))

    #! 外鍵連向儲值訂單 (如果是儲值產生的點數)
    recharge_order = models.ForeignKey(
        RechargeOrder, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("關聯儲值訂單")
    )

    description = models.TextField(blank=True, verbose_name=_("備註"))
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name=_("建立時間"))

    class Meta:
        verbose_name = _("點數交易紀錄")
        verbose_name_plural = _("點數交易紀錄")
        ordering = ["-created_at"]


class PointPackage(models.Model):
    """儲值方案"""

    name = models.CharField(max_length=100, verbose_name=_("方案名稱"))
    price = models.PositiveIntegerField(verbose_name=_("台幣售價"))
    deposit_points = models.PositiveIntegerField(verbose_name=_("獲得儲值點數"))
    bonus_points = models.PositiveIntegerField(default=0, verbose_name=_("加贈紅利點數"))
    is_active = models.BooleanField(default=True, verbose_name=_("是否上架"))

    class Meta:
        verbose_name = _("儲值方案")
        verbose_name_plural = _("儲值方案")

    def __str__(self):
        return f"{self.name} (NT${self.price})"


class Product(models.Model):
    """商城販售商品"""

    name = models.CharField(max_length=200, verbose_name=_("商品名稱"))
    category = models.CharField(
        max_length=20,
        choices=[
            ("GENERAL", _("一般商品")),
            ("PET_EGG", _("寵物蛋")),
            ("PET_FOOD", _("寵物成長道具")),
        ],
        default="GENERAL",
        verbose_name=_("商品分類"),
    )
    description = models.TextField(blank=True, verbose_name=_("商品描述"))
    image = models.ImageField(upload_to="products/", blank=True, null=True, verbose_name=_("商品圖片"))
    price_in_points = models.PositiveIntegerField(verbose_name=_("點數售價"))
    price_ntd = models.PositiveIntegerField(default=0, verbose_name=_("台幣售價"))
    stock = models.PositiveIntegerField(default=0, verbose_name=_("庫存數量"))
    is_active = models.BooleanField(default=True, verbose_name=_("是否上架"))

    class Meta:
        verbose_name = _("商城商品")
        verbose_name_plural = _("商城商品")

    def __str__(self):
        return self.name


class ShopOrder(models.Model):
    """點數購物訂單"""

    PAYMENT_CHOICES = [
        ("POINTS", _("點數全額扣抵")),
        ("ECPAY", _("綠界金流付款")),
    ]
    STATUS_CHOICES = [
        ("PENDING", _("待付款")),  # * 綠界付款前
        ("PAID", _("已付款")),  # * 綠界付款後 / 或點數扣抵成功
        ("FAILED", _("付款失敗")),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("使用者"))

    #! 加入商品關聯 (如果是單件購買)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, verbose_name=_("購買商品"))
    quantity = models.PositiveIntegerField(default=1, verbose_name=_("購買數量"))

    #! 付款方式與狀態
    payment_method = models.CharField(
        max_length=10, choices=PAYMENT_CHOICES, default="POINTS", verbose_name=_("付款方式")
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="COMPLETED", verbose_name=_("訂單狀態"))

    total_price = models.PositiveIntegerField(verbose_name=_("總點數花費"))
    deposit_used = models.PositiveIntegerField(default=0, verbose_name=_("使用儲值點數"))
    bonus_used = models.PositiveIntegerField(default=0, verbose_name=_("使用紅利點數"))
    amount_paid = models.PositiveIntegerField(default=0, verbose_name=_("台幣實付金額"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("建立時間"))

    class Meta:
        verbose_name = _("點數購物訂單")
        verbose_name_plural = _("點數購物訂單")