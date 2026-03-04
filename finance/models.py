from django.contrib.auth.models import User
from django.db import models


class UserPoints(models.Model):
    """錢包餘額 (與 User 一對一)"""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    deposit_points = models.PositiveIntegerField(default=0, verbose_name="儲值點數")
    bonus_points = models.PositiveIntegerField(default=0, verbose_name="紅利點數")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新時間")

    class Meta:
        verbose_name = "錢包餘額"
        verbose_name_plural = "錢包餘額"

    def __str__(self):
        return f"{self.user.username} - 儲值點數：{self.deposit_points} / 紅利點數：{self.bonus_points}"


class RechargeOrder(models.Model):
    """綠界儲值訂單"""

    STATUS_CHOICES = [
        ("PENDING", "待付款"),
        ("SUCCESS", "付款成功"),
        ("FAILED", "付款失敗"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    #! 綠界要求：特店交易編號 (不可重複)
    merchant_trade_no = models.CharField(max_length=50, unique=True)
    amount = models.PositiveIntegerField(verbose_name="儲值金額")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    payment_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PointTransaction(models.Model):
    """點數交易流水帳 (包含購物與儲值)"""

    TRANSACTION_TYPES = [
        ("RECHARGE", "儲值"),
        ("PURCHASE", "購物扣抵"),
        ("REWARD", "活動贈送"),
        ("REFUND", "退貨返還"),
    ]

    POINT_TYPES = [
        ("DEPOSIT", "儲值點數"),
        ("BONUS", "紅利點數"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="point_history")
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, verbose_name="交易類型")
    point_type = models.CharField(max_length=10, choices=POINT_TYPES, verbose_name="點數類型")

    #! 變動金額：增加為正數，減少為負數
    amount = models.IntegerField(verbose_name="變動金額")

    #! 關聯單號：例如訂單 ID 或 儲值單 ID，方便對帳
    reference_id = models.CharField(max_length=100, blank=True, null=True, verbose_name="關聯單號")

    #! 外鍵連向儲值訂單 (如果是儲值產生的點數)
    recharge_order = models.ForeignKey(RechargeOrder, on_delete=models.SET_NULL, null=True, blank=True)

    description = models.TextField(blank=True, verbose_name="備註")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="建立時間")

    class Meta:
        verbose_name = "點數交易紀錄"
        verbose_name_plural = "點數交易紀錄"
        ordering = ["-created_at"]


class PointPackage(models.Model):
    """儲值方案"""

    name = models.CharField(max_length=100, verbose_name="方案名稱")
    price = models.PositiveIntegerField(verbose_name="台幣售價")
    deposit_points = models.PositiveIntegerField(verbose_name="獲得儲值點數")
    bonus_points = models.PositiveIntegerField(default=0, verbose_name="加贈紅利點數")
    is_active = models.BooleanField(default=True, verbose_name="是否上架")

    class Meta:
        verbose_name = "儲值方案"
        verbose_name_plural = "儲值方案"

    def __str__(self):
        return f"{self.name} (NT${self.price})"


class Product(models.Model):
    """商城販售商品"""

    name = models.CharField(max_length=200, verbose_name="商品名稱")
    description = models.TextField(blank=True, verbose_name="商品描述")
    image = models.ImageField(upload_to="products/", blank=True, null=True, verbose_name="商品圖片")
    price_in_points = models.PositiveIntegerField(verbose_name="點數售價")
    price_ntd = models.PositiveIntegerField(default=0, verbose_name="台幣售價")
    stock = models.PositiveIntegerField(default=0, verbose_name="庫存數量")
    is_active = models.BooleanField(default=True, verbose_name="是否上架")

    class Meta:
        verbose_name = "商城商品"
        verbose_name_plural = "商城商品"

    def __str__(self):
        return self.name


class ShopOrder(models.Model):
    """點數購物訂單"""

    PAYMENT_CHOICES = [
        ("POINTS", "點數全額扣抵"),
        ("ECPAY", "綠界金流付款"),
    ]
    STATUS_CHOICES = [
        ("PENDING", "待付款"),  # * 綠界付款前
        ("PAID", "已付款"),  # * 綠界付款後 / 或點數扣抵成功
        ("FAILED", "付款失敗"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    #! 加入商品關聯 (如果是單件購買)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField(default=1, verbose_name="購買數量")

    #! 付款方式與狀態
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default="POINTS")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="COMPLETED")

    total_price = models.PositiveIntegerField(verbose_name="總點數花費")
    deposit_used = models.PositiveIntegerField(default=0, verbose_name="使用儲值點數")
    bonus_used = models.PositiveIntegerField(default=0, verbose_name="使用紅利點數")
    amount_paid = models.PositiveIntegerField(default=0, verbose_name="台幣實付金額")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "點數購物訂單"
