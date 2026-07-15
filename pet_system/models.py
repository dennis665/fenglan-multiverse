from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _

from finance.models import Product


class Pet(models.Model):
    STAGE_CHOICES = [
        (0, _("寵物蛋")),
        (1, _("幼年體")),
        (2, _("成長體")),
        (3, _("完全體")),
        (4, _("進化體")),
    ]

    PET_TYPES = [
        ("DRAGON", _("幻獸綠龍")),
        ("PUPPY", _("烈火幼犬")),
    ]

    PERSONALITY_CHOICES = [
        ("NORMAL", _("普通")),
        ("BRAVE", _("勇敢")),
        ("LAZY", _("懶散")),
        ("SMART", _("聰明")),
        ("CHUBBY", _("肥嘟嘟")),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pets", verbose_name=_("擁有者"))
    name = models.CharField(max_length=50, default=_("未命名寵物"), verbose_name=_("寵物名字"))
    pet_type = models.CharField(max_length=20, choices=PET_TYPES, default="DRAGON", verbose_name=_("寵物種類"))
    stage = models.IntegerField(choices=STAGE_CHOICES, default=0, verbose_name=_("成長階段"))

    # 是否為當前在畫面上跑動的寵物 (一個使用者同時只能設定一隻 active)
    is_active = models.BooleanField(default=False, verbose_name=_("是否出戰"))

    # 成長與餵食計數 (用以判斷分支進化)
    growth_progress = models.PositiveIntegerField(default=0, verbose_name=_("成長進度"))
    login_days_consumed = models.PositiveIntegerField(default=0, verbose_name=_("已消耗登入天數"))

    feed_items_consumed = models.PositiveIntegerField(default=0, verbose_name=_("普通乾糧消耗數"))
    potions_consumed = models.PositiveIntegerField(default=0, verbose_name=_("奇蹟藥水消耗數"))

    personality = models.CharField(max_length=20, choices=PERSONALITY_CHOICES, default="NORMAL", verbose_name=_("寵物性格"))

    # 裝備的配件 ID
    equipped_head = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("頭部裝飾"))
    equipped_face = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("臉部裝飾"))
    equipped_back = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("背部裝飾"))

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("領養時間"))
    last_interacted_at = models.DateTimeField(auto_now=True, verbose_name=_("最後互動時間"))

    class Meta:
        verbose_name = _("寵物")
        verbose_name_plural = _("寵物")

    def __str__(self):
        return f"{self.user.username} - {self.name} ({self.get_stage_display()})"

    def save(self, *args, **kwargs):
        # 限制：若設定 is_active=True，自動將該用戶其他寵物的 is_active 設為 False
        if self.is_active:
            Pet.objects.filter(user=self.user, is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class UserPetProfile(models.Model):
    """玩家的寵物金幣存摺"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="pet_profile", verbose_name=_("使用者"))
    pet_gold_coins = models.PositiveIntegerField(default=0, verbose_name=_("寵物金幣"))
    last_daily_claim = models.DateField(null=True, blank=True, verbose_name=_("最後每日金幣領取日期"))

    class Meta:
        verbose_name = _("玩家寵物存摺")
        verbose_name_plural = _("玩家寵物存摺")

    def __str__(self):
        return f"{self.user.username} - {self.pet_gold_coins} Coins"


class UserAccessory(models.Model):
    """玩家解鎖擁有的服飾配件"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="accessories", verbose_name=_("使用者"))
    accessory_id = models.CharField(max_length=50, verbose_name=_("配件ID"))
    quantity = models.PositiveIntegerField(default=1, verbose_name=_("擁有數量"))

    class Meta:
        unique_together = ("user", "accessory_id")
        verbose_name = _("玩家解鎖配件")
        verbose_name_plural = _("玩家解鎖配件")

    def __str__(self):
        return f"{self.user.username} - {self.accessory_id} ({self.quantity})"


class PetExpedition(models.Model):
    """探索派遣任務"""
    STATUS_CHOICES = [
        ("ACTIVE", _("探索中")),
        ("COMPLETED", _("探索完成")),
        ("CLAIMED", _("已領取獎勵")),
    ]
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name="expeditions", verbose_name=_("派遣寵物"))
    duration_hours = models.IntegerField(verbose_name=_("探索時長(小時)"))
    start_time = models.DateTimeField(auto_now_add=True, verbose_name=_("出發時間"))
    end_time = models.DateTimeField(verbose_name=_("預計結束時間"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE", verbose_name=_("狀態"))

    class Meta:
        verbose_name = _("探索派遣任務")
        verbose_name_plural = _("探索派遣任務")

    def __str__(self):
        return f"{self.pet.name} - {self.duration_hours}h ({self.get_status_display()})"


class TowerProgress(models.Model):
    """玩家爬塔關卡進度"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="tower_progress", verbose_name=_("使用者"))
    current_floor = models.PositiveIntegerField(default=1, verbose_name=_("當前爬塔層數"))

    class Meta:
        verbose_name = _("爬塔進度")
        verbose_name_plural = _("爬塔進度")

    def __str__(self):
        return f"{self.user.username} - Floor {self.current_floor}"


class PetStoryUnlock(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("使用者"))
    pet_type = models.CharField(max_length=20, choices=Pet.PET_TYPES, verbose_name=_("寵物種類"))
    max_stage_reached = models.IntegerField(default=0, verbose_name=_("已解鎖最高成長階段"))

    class Meta:
        unique_together = ("user", "pet_type")
        verbose_name = _("劇情解鎖紀錄")
        verbose_name_plural = _("劇情解鎖紀錄")

    def __str__(self):
        return f"{self.user.username} - {self.get_pet_type_display()} (Stage {self.max_stage_reached})"


class DailyLoginLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("使用者"))
    login_date = models.DateField(verbose_name=_("登入日期"))

    class Meta:
        unique_together = ("user", "login_date")
        verbose_name = _("每日登入日誌")
        verbose_name_plural = _("每日登入日誌")

    def __str__(self):
        return f"{self.user.username} - {self.login_date}"


class UserInventory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="inventory", verbose_name=_("使用者"))
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name=_("道具商品"))
    quantity = models.PositiveIntegerField(default=0, verbose_name=_("擁有數量"))

    class Meta:
        unique_together = ("user", "product")
        verbose_name = _("使用者背包道具")
        verbose_name_plural = _("使用者背包道具")

    def __str__(self):
        return f"{self.user.username} - {self.product.name} ({self.quantity})"
