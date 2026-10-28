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


class Friendship(models.Model):
    """好友關係模型 (僅限已綁定的 CSI 會員)"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="friendships", verbose_name=_("使用者"))
    friend = models.ForeignKey(User, on_delete=models.CASCADE, related_name="friend_of", verbose_name=_("好友"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("建立時間"))

    class Meta:
        verbose_name = _("追劇好友關係")
        verbose_name_plural = _("追劇好友關係")
        unique_together = ("user", "friend")

    def __str__(self):
        return f"{self.user.username} -> {self.friend.username}"


class AnimeFranchise(models.Model):
    """動漫作品 IP 系列主表（可在 Admin 後台自由建立、修改與設定關聯）"""
    name = models.CharField(max_length=150, unique=True, verbose_name=_("作品系列名稱"))
    description = models.TextField(blank=True, verbose_name=_("系列簡介/說明"))
    cover_image_url = EncryptedTextField(blank=True, default="", verbose_name=_("系列封面圖"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("建立時間"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("更新時間"))

    class Meta:
        verbose_name = _("動漫作品系列")
        verbose_name_plural = _("動漫作品系列")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} (關聯劇集: {self.dramas.count()} 部)"


class Drama(models.Model):
    """追劇主表（共享資訊部分）"""
    MEDIA_TYPE_CHOICES = [
        ("TV", _("TV 正篇 / 季番")),
        ("MOVIE", _("劇場版 / 電影")),
        ("OVA", _("OVA / 特別篇")),
        ("RECAP", _("總集篇")),
    ]

    title = EncryptedCharField(max_length=255, verbose_name=_("劇名"))
    category = models.CharField(max_length=50, default="其他", verbose_name=_("分類"))
    franchise = models.ForeignKey(
        AnimeFranchise,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dramas",
        verbose_name=_("所屬作品系列"),
    )
    media_type = models.CharField(
        max_length=20, default="TV", choices=MEDIA_TYPE_CHOICES, verbose_name=_("媒體類型")
    )
    total_seasons = models.IntegerField(default=1, verbose_name=_("總季數"))
    total_episodes = models.IntegerField(default=0, verbose_name=_("總集數"))
    info_links = EncryptedTextField(blank=True, default="[]", verbose_name=_("相關資訊連結"))
    mp3_links = EncryptedTextField(blank=True, default="[]", verbose_name=_("MP3 音樂播放清單"))
    mp4_links = EncryptedTextField(blank=True, default="[]", verbose_name=_("MP4 影片播放清單"))
    image_url = EncryptedTextField(blank=True, default="", verbose_name=_("預覽圖連結"))
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_dramas", verbose_name=_("建立者"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("建立時間"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("更新時間"))

    class Meta:
        verbose_name = _("追劇主檔")
        verbose_name_plural = _("追劇主檔")

    def __str__(self):
        return f"{self.title} ({self.category})"


class UserDramaProgress(models.Model):
    """個人追劇進度表（私有資訊部分）"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="drama_progresses", verbose_name=_("使用者"))
    drama = models.ForeignKey(Drama, on_delete=models.CASCADE, related_name="progresses", verbose_name=_("追劇"))
    current_season = models.IntegerField(default=1, verbose_name=_("目前看至第幾季"))
    current_episode = models.IntegerField(default=1, verbose_name=_("目前看至第幾集"))
    is_tracked = models.BooleanField(default=False, verbose_name=_("是否追蹤連結更新"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("更新時間"))

    class Meta:
        verbose_name = _("個人追劇進度")
        verbose_name_plural = _("個人追劇進度")
        unique_together = ("user", "drama")
        indexes = [
            models.Index(fields=["drama"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.drama.title} (S{self.current_season}E{self.current_episode})"


class DramaRecommendation(models.Model):
    """追劇推薦清單"""
    STATUS_CHOICES = (
        ("pending", _("未讀/待處理")),
        ("accepted", _("已加入清單")),
        ("rejected", _("已拒絕")),
        ("ignored", _("已忽略")),
    )

    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_recommendations", verbose_name=_("推薦人"))
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_recommendations", verbose_name=_("被推薦人"))
    drama = models.ForeignKey(Drama, on_delete=models.CASCADE, verbose_name=_("追劇項目"))
    recommend_notes = EncryptedTextField(blank=True, verbose_name=_("推薦心得語錄"))
    is_accepted = models.BooleanField(default=False, verbose_name=_("是否已接受"))
    is_rejected = models.BooleanField(default=False, verbose_name=_("是否已拒絕"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name=_("推薦狀態"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("建立時間"))

    class Meta:
        verbose_name = _("追劇推薦記錄")
        verbose_name_plural = _("追劇推薦記錄")

    def __str__(self):
        return f"{self.from_user.username} recommend {self.drama.title} to {self.to_user.username}"


class FDANutrition(models.Model):
    """衛生福利部 FDA 台灣食品營養成分資料庫"""
    code = models.CharField(max_length=50, unique=True, verbose_name=_("整合編號"))
    category = models.CharField(max_length=100, verbose_name=_("分類"), db_index=True)
    name = models.CharField(max_length=200, verbose_name=_("樣品名稱"), db_index=True)
    common_name = models.TextField(blank=True, default="", verbose_name=_("俗名"))
    calories = models.FloatField(default=0.0, verbose_name=_("熱量(kcal)"))
    protein = models.FloatField(default=0.0, verbose_name=_("粗蛋白(g)"))
    fat = models.FloatField(default=0.0, verbose_name=_("粗脂肪(g)"))
    carbs = models.FloatField(default=0.0, verbose_name=_("總碳水化合物(g)"))
    fiber = models.FloatField(default=0.0, verbose_name=_("膳食纖維(g)"))
    sodium = models.FloatField(default=0.0, verbose_name=_("鈉(mg)"))
    sugar = models.FloatField(default=0.0, verbose_name=_("總糖(g)"))
    raw_details = EncryptedTextField(blank=True, default="{}", verbose_name=_("全欄位JSON資料"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("更新時間"))

    class Meta:
        verbose_name = _("FDA食品營養成分")
        verbose_name_plural = _("FDA食品營養成分")

    def __str__(self):
        return f"[{self.category}] {self.name}"


class NutrientReference(models.Model):
    """人體每日營養成分建議、攝取過多/過少危害與優缺點知識庫"""
    name = models.CharField(max_length=100, unique=True, verbose_name=_("成分名稱"), db_index=True)
    unit = models.CharField(max_length=30, blank=True, default="", verbose_name=_("單位"))
    category = models.CharField(max_length=50, blank=True, default="微量元素", verbose_name=_("成分類別"))
    daily_recommended = models.CharField(max_length=150, blank=True, default="", verbose_name=_("每日建議攝取量 (RDA/DRI)"))
    daily_upper_limit = models.CharField(max_length=150, blank=True, default="", verbose_name=_("每日攝取上限 (UL)"))
    benefits = models.TextField(blank=True, default="", verbose_name=_("生理功能與主要優點"))
    concerns = models.TextField(blank=True, default="", verbose_name=_("注意事項"))
    excess_hazards = models.TextField(blank=True, default="", verbose_name=_("攝取過多危害"))
    deficiency_hazards = models.TextField(blank=True, default="", verbose_name=_("攝取過少危害"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("更新時間"))

    class Meta:
        verbose_name = _("營養成分對照與健康知識庫")
        verbose_name_plural = _("營養成分對照與健康知識庫")

    def __str__(self):
        return f"{self.name} ({self.daily_recommended})"


class DailyIntakeLog(models.Model):
    """每日飲食紀錄表"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="intake_logs", verbose_name=_("使用者"), null=True, blank=True)
    date = models.DateField(db_index=True, verbose_name=_("記錄日期"))
    food = models.ForeignKey(FDANutrition, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("食品"))
    custom_name = models.CharField(max_length=200, blank=True, default="", verbose_name=_("自訂名稱(保健品/餐點)"))
    custom_nutrients = EncryptedTextField(blank=True, default="{}", verbose_name=_("自訂成分JSON"))
    amount_g = models.FloatField(default=100.0, verbose_name=_("食用份量(公克)"))
    meal_type = models.CharField(max_length=50, blank=True, default="點心/其他", verbose_name=_("餐別 (早餐/午餐/晚餐/點心)"))
    notes = models.CharField(max_length=200, blank=True, default="", verbose_name=_("備註"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("建立時間"))

    class Meta:
        verbose_name = _("每日飲食紀錄")
        verbose_name_plural = _("每日飲食紀錄")
        ordering = ["-date", "-created_at"]

    def __str__(self):
        name = self.food.name if self.food else self.custom_name
        return f"{self.date} [{self.meal_type}] - {name} ({self.amount_g}g)"


class FoodAdditive(models.Model):
    """台灣人工食品添加物與健康危害知識庫"""
    name = models.CharField(max_length=150, unique=True, verbose_name=_("添加物名稱/俗名"), db_index=True)
    e_number = models.CharField(max_length=50, blank=True, default="", verbose_name=_("E編號/代碼"), db_index=True)
    category = models.CharField(max_length=100, verbose_name=_("法定類別 (如: 防腐劑, 人工色素)"), db_index=True)
    purpose = models.CharField(max_length=200, blank=True, default="", verbose_name=_("主要用途"))
    common_foods = models.TextField(blank=True, default="", verbose_name=_("常見於哪些食品"))
    health_hazards = models.TextField(blank=True, default="", verbose_name=_("吃了的健康危害與風險"))
    safe_advice = models.TextField(blank=True, default="", verbose_name=_("營養師安全建議"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("更新時間"))

    class Meta:
        verbose_name = _("食品添加物與健康危害")
        verbose_name_plural = _("食品添加物與健康危害")
        ordering = ["category", "name"]

    def __str__(self):
        return f"[{self.category}] {self.name} ({self.e_number})"


class GNNNews(models.Model):
    """巴哈姆特 GNN 即時新聞與動漫遊戲情報"""
    sn = models.CharField(max_length=50, unique=True, db_index=True, verbose_name=_("文章編號"))
    title = models.CharField(max_length=300, db_index=True, verbose_name=_("新聞標題"))
    link = models.URLField(max_length=500, verbose_name=_("原文連結"))
    tags = models.JSONField(default=list, blank=True, verbose_name=_("分類標籤(多項tag)"))
    thumbnail = models.URLField(max_length=500, blank=True, default="", verbose_name=_("縮圖網址"))
    summary = models.TextField(blank=True, default="", verbose_name=_("新聞摘要"))
    published_at = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name=_("發布時間"))
    crawl_date = models.DateField(db_index=True, verbose_name=_("出刊/爬取日期"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("建立時間"))

    class Meta:
        verbose_name = _("GNN動漫遊戲新聞")
        verbose_name_plural = _("GNN動漫遊戲新聞")
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return f"[{self.crawl_date}] {self.title}"


class PlannerNotebook(models.Model):
    """手帳筆記本（支援週間行程 WEEKLY PLAN 與每日記事 DAILY NOTES）"""
    PLAN_TYPE_CHOICES = [
        ("weekly", _("週間行程")),
        ("daily", _("每日記事")),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="planner_notebooks", verbose_name=_("使用者"))
    line_user_id = models.CharField(max_length=50, blank=True, default="", db_index=True, verbose_name=_("LINE 用戶識別碼"))
    plan_type = models.CharField(max_length=10, choices=PLAN_TYPE_CHOICES, db_index=True, verbose_name=_("筆記類型"))
    target_date = models.DateField(db_index=True, verbose_name=_("目標日期/週一日期"))
    content = models.JSONField(default=dict, blank=True, verbose_name=_("筆記內容資料"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("建立時間"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("最後更新時間"))

    class Meta:
        verbose_name = _("手帳筆記本")
        verbose_name_plural = _("手帳筆記本")
        unique_together = ("line_user_id", "plan_type", "target_date")
        ordering = ["-target_date", "-updated_at"]

    def __str__(self):
        owner = self.user.username if self.user else self.line_user_id
        return f"[{self.get_plan_type_display()}] {self.target_date} ({owner})"


class Novel(models.Model):
    """輕小說書籍主表"""
    novel_id = models.CharField(max_length=50, unique=True, db_index=True, verbose_name=_("小說 ID"))
    title = models.CharField(max_length=255, db_index=True, verbose_name=_("小說標題"))
    author = models.CharField(max_length=100, blank=True, default="", verbose_name=_("作者"))
    cover_url = models.URLField(max_length=500, blank=True, default="", verbose_name=_("封面連結"))
    description = models.TextField(blank=True, default="", verbose_name=_("小說簡介"))
    category = models.CharField(max_length=100, blank=True, default="", verbose_name=_("作品分類"))
    status = models.CharField(max_length=50, blank=True, default="", verbose_name=_("連載狀態"))
    source_url = models.URLField(max_length=500, blank=True, default="", verbose_name=_("來源網址"))
    total_chapters = models.PositiveIntegerField(default=0, verbose_name=_("總章節數"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("匯入時間"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("更新時間"))

    class Meta:
        verbose_name = _("輕小說")
        verbose_name_plural = _("輕小說庫")
        ordering = ["-updated_at", "-created_at"]

    def __str__(self):
        return f"{self.title} ({self.novel_id})"


class NovelChapter(models.Model):
    """小說目錄與章節"""
    novel = models.ForeignKey(Novel, on_delete=models.CASCADE, related_name="chapters", verbose_name=_("所屬小說"))
    volume_title = models.CharField(max_length=200, default="正文", verbose_name=_("分卷名稱"))
    chapter_id = models.CharField(max_length=50, db_index=True, verbose_name=_("章節 ID"))
    title = models.CharField(max_length=255, verbose_name=_("章節標題"))
    chapter_url = models.URLField(max_length=500, blank=True, default="", verbose_name=_("章節網址"))
    order = models.IntegerField(default=0, db_index=True, verbose_name=_("章節排序"))
    content_cached = models.JSONField(default=dict, blank=True, verbose_name=_("章節快取內容"))
    has_images = models.BooleanField(default=False, verbose_name=_("是否包含插圖"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("建立時間"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("更新時間"))

    class Meta:
        verbose_name = _("小說章節")
        verbose_name_plural = _("小說章節")
        unique_together = ("novel", "chapter_id")
        ordering = ["order", "id"]

    def __str__(self):
        return f"[{self.novel.title}] {self.volume_title} - {self.title}"


class NovelReadingProgress(models.Model):
    """使用者小說閱讀進度（支援精確段落紀錄與回訪導航）"""
    novel = models.ForeignKey(Novel, on_delete=models.CASCADE, related_name="reading_progresses", verbose_name=_("所屬小說"))
    line_user_id = models.CharField(max_length=50, db_index=True, verbose_name=_("LINE 用戶識別碼"))
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="novel_progresses", verbose_name=_("使用者"))
    last_chapter = models.ForeignKey(NovelChapter, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("最後閱讀章節"))
    last_chapter_key = models.CharField(max_length=50, blank=True, default="", verbose_name=_("最後章節 ID"))
    last_chapter_title = models.CharField(max_length=255, blank=True, default="", verbose_name=_("最後章節名稱"))
    last_paragraph_index = models.IntegerField(default=0, verbose_name=_("閱讀段落索引"))
    scroll_percentage = models.FloatField(default=0.0, verbose_name=_("滾動進度百分比"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("最後閱讀時間"))

    class Meta:
        verbose_name = _("小說閱讀進度")
        verbose_name_plural = _("小說閱讀進度")
        unique_together = ("novel", "line_user_id")
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.line_user_id} - {self.novel.title} ({self.last_chapter_title} P{self.last_paragraph_index})"
