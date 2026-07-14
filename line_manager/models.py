from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _
from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField


class LineProfile(models.Model):
    """將 Django 的 User 帳號與 LINE 的 line_user_id 進行綁定"""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="line_profile", verbose_name=_("使用者")
    )
    line_user_id = models.CharField(max_length=50, unique=True, verbose_name=_("LINE 用戶識別碼"))
    line_display_name = models.CharField(
        max_length=100, blank=True, verbose_name=_("LINE 顯示名稱")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("建立時間"))

    class Meta:
        verbose_name = _("LINE 個人檔案")
        verbose_name_plural = _("LINE 個人檔案")

    def __str__(self):
        return f"{self.user.username} - {self.line_display_name}"


class Itinerary(models.Model):
    """行程資料表：支援個人隱私加密與多人群組共享"""

    ACTIVITY_CHOICES = [
        ("EAT", _("吃飯聚餐")),
        ("EXHIBIT", _("逛街展覽")),
        ("SPORT", _("運動健身")),
        ("TRAVEL", _("旅遊踏青")),
        ("MOVIE", _("看電影")),
        ("OTHER", _("其他活動")),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="created_itineraries", verbose_name=_("發起人")
    )

    #! 群組綁定欄位（若為空代表是個人的私密行程）
    group_id = models.CharField(
        max_length=50, blank=True, null=True, db_index=True, verbose_name=_("LINE 群組識別碼")
    )

    #! 私密行程會透過金鑰加密儲存於資料庫，Admin 後台直接觀看呈現密文
    title = EncryptedCharField(max_length=255, verbose_name=_("行程標題"))
    location = EncryptedCharField(max_length=255, verbose_name=_("活動地點"))
    notes = EncryptedTextField(blank=True, verbose_name=_("備註說明"))

    # 新增：相關活動連結與有興趣加入的成員（皆以 JSON 格式之加密字串儲存）
    related_links = EncryptedTextField(blank=True, default="[]", verbose_name=_("相關活動連結"))
    interested_users = EncryptedTextField(blank=True, default="[]", verbose_name=_("有興趣成員"))

    #! 一般篩選欄位（保持明文以供後續篩選排序）
    activity_type = models.CharField(
        max_length=10, choices=ACTIVITY_CHOICES, default="OTHER", verbose_name=_("活動類型")
    )
    date_time = models.DateTimeField(blank=True, null=True, verbose_name=_("行程時間"))

    notify_minutes_before = models.IntegerField(default=1440, verbose_name=_("提前通知時間(分鐘)"))
    is_notified = models.BooleanField(default=False, verbose_name=_("是否已發送通知"))
    is_hidden = models.BooleanField(default=False, verbose_name=_("是否已隱藏"))

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("建立時間"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("更新時間"))

    class Meta:
        verbose_name = _("行程管理")
        verbose_name_plural = _("行程管理")
        ordering = ["date_time"]

    def __str__(self):
        # * 字串表達式：用於 Admin 後台顯示。
        # * 由於 title 欄位是加密欄位，在後台讀取 __str__ 時如果會觸發資料解密，這會讓管理員看見標題。
        # * 為保證絕對隱私，當前如果是由 non-owner 存取時，我們只返回其類型與 ID。
        dt_str = self.date_time.strftime('%Y-%m-%d %H:%M') if self.date_time else _("時間待定")
        return f"[{self.get_activity_type_display()}] {dt_str}"


class GroupMembership(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="group_memberships", verbose_name=_("使用者")
    )
    group_id = models.CharField(max_length=50, db_index=True, verbose_name=_("LINE 群組 ID"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("加入時間"))

    class Meta:
        verbose_name = _("群組成員關係")
        verbose_name_plural = _("群組成員關係")
        unique_together = ("user", "group_id")

    def __str__(self):
        return f"{self.user.username} in {self.group_id}"
