#! 遊戲中心資料庫模型
from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _


class GameProfile(models.Model):
    """玩家全域遊戲檔案與各項紀錄"""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="game_profile", verbose_name=_("玩家"))

    #! 通用貨幣 (所有遊戲共用)
    total_coins = models.IntegerField(default=0, verbose_name=_("總遊戲幣"))

    #! 倖存者生存專屬紀錄
    survivor_max_time = models.IntegerField(default=0, verbose_name=_("倖存者-最高存活秒數"))
    survivor_max_kills = models.IntegerField(default=0, verbose_name=_("倖存者-最高擊殺數"))

    #! 倖存者局外成長等級
    survivor_hp_lv = models.IntegerField(default=0, verbose_name=_("倖存者-血量等級"))
    survivor_atk_lv = models.IntegerField(default=0, verbose_name=_("倖存者-攻擊等級"))
    survivor_speed_lv = models.IntegerField(default=0, verbose_name=_("倖存者-移速等級"))

    #! 未來擴充預留 (例如：俄羅斯方塊最高分)
    # tetris_high_score = models.IntegerField(default=0)

    class Meta:
        verbose_name = _("玩家遊戲存檔")
        verbose_name_plural = _("玩家遊戲存檔")

    def __str__(self):
        return f"{self.user.username}'s Game Hub"


class SurvivorLevel(models.Model):
    """倖存者生存 - 關卡設定"""

    name = models.CharField(max_length=50, verbose_name=_("關卡名稱"))
    time_limit = models.IntegerField(default=300, verbose_name=_("通關時間(秒)"))
    spawn_rate_mult = models.FloatField(default=1.0, verbose_name=_("出怪頻率倍率(越高越快)"))
    stat_mult = models.FloatField(default=1.0, verbose_name=_("怪物屬性倍率(難度)"))
    win_bonus = models.IntegerField(default=100, verbose_name=_("通關獎勵金幣"))

    class Meta:
        verbose_name = _("倖存者-關卡設定")
        verbose_name_plural = _("倖存者-關卡設定")

    def __str__(self):
        return f"{self.name} ({self.time_limit}秒)"


class SurvivorMonster(models.Model):
    """倖存者生存 - 怪物圖鑑"""

    name = models.CharField(max_length=50, verbose_name=_("怪物名稱"))
    image = models.ImageField(upload_to="games/monsters/", blank=True, null=True, verbose_name=_("怪物圖片"))
    base_hp = models.IntegerField(default=10, verbose_name=_("基礎血量"))
    base_atk = models.IntegerField(default=5, verbose_name=_("基礎攻擊力"))
    base_speed = models.FloatField(default=1.5, verbose_name=_("基礎跑速"))
    base_size = models.IntegerField(default=15, verbose_name=_("碰撞體積(半徑)"))

    class Meta:
        verbose_name = _("倖存者-怪物圖鑑")
        verbose_name_plural = _("倖存者-怪物圖鑑")

    def __str__(self):
        return self.name
