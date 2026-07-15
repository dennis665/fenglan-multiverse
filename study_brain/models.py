from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _


class Category(models.Model):
    """教材大類分類"""

    name = models.CharField(max_length=100, verbose_name=_("分類名稱"))
    description = models.TextField(blank=True, verbose_name=_("分類描述"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("建立時間"))

    class Meta:
        verbose_name = _("教材分類")
        verbose_name_plural = _("教材分類")

    def __str__(self):
        return self.name


class Material(models.Model):
    """上傳的教材原始檔案紀錄"""

    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="materials", verbose_name=_("所屬分類")
    )
    uploader = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name=_("上傳者"))
    #! 記錄有哪些使用者把這份教材加入了「我的教材庫」
    saved_by = models.ManyToManyField(User, related_name="saved_materials", blank=True, verbose_name=_("收藏的使用者"))

    is_exam_paper = models.BooleanField(default=False, verbose_name=_("是否為歷屆考題"))

    title = models.CharField(max_length=255, verbose_name=_("教材標題"))
    file = models.FileField(upload_to="study_materials/%Y/%m/", verbose_name=_("教材檔案"))  # * 預計存放 PDF 或 Word
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name=_("上傳時間"))

    class Meta:
        verbose_name = _("教材檔案")
        verbose_name_plural = _("教材檔案")

    def __str__(self):
        return self.title


class AnalysisResult(models.Model):
    """紀錄每次 AI 訓練產出的重點與題目"""

    material = models.ForeignKey(
        Material, on_delete=models.CASCADE, related_name="analysis_results", verbose_name=_("關聯教材")
    )
    summary = models.TextField(verbose_name=_("重點整理"))
    questions_data = models.JSONField(default=list, verbose_name=_("練習題資料"))  # * 使用 JSON 陣列儲存題目與選項
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("產出時間"))

    class Meta:
        verbose_name = _("AI 分析結果")
        verbose_name_plural = _("AI 分析結果")
        ordering = ["-created_at"]  # * 預設將最新產出的結果排在最前面

    def __str__(self):
        return f"{self.material.title} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class ReadingRecord(models.Model):
    """紀錄使用者何時閱讀了哪一份教材"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reading_records", verbose_name=_("使用者"))
    material = models.ForeignKey(Material, on_delete=models.CASCADE, verbose_name=_("閱讀教材"))
    read_at = models.DateTimeField(auto_now_add=True, verbose_name=_("閱讀時間"))

    class Meta:
        verbose_name = _("閱讀紀錄")
        verbose_name_plural = _("閱讀紀錄")
        ordering = ["-read_at"]

    def __str__(self):
        return f"{self.user.username} - {self.material.title}"


class QuizRecord(models.Model):
    """紀錄使用者每一次的測驗總結與錯誤率"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="quiz_records", verbose_name=_("使用者"))
    analysis_result = models.ForeignKey(AnalysisResult, on_delete=models.CASCADE, verbose_name=_("測驗來源"))
    total_questions = models.IntegerField(verbose_name=_("總題數"))
    correct_count = models.IntegerField(verbose_name=_("答對題數"))
    error_rate = models.FloatField(verbose_name=_("錯誤率"))  # * 儲存 0.0 到 100.0 的百分比
    attempted_questions = models.JSONField(default=list, blank=True, verbose_name=_("已作答題目"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("測驗時間"))

    class Meta:
        verbose_name = _("測驗紀錄")
        verbose_name_plural = _("測驗紀錄")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.created_at.strftime('%Y-%m-%d')} ({self.error_rate}%)"


class QuizMistake(models.Model):
    """紀錄具體答錯的題目明細，做為未來 AI 訓練的 Context 素材"""

    quiz_record = models.ForeignKey(
        QuizRecord, on_delete=models.CASCADE, related_name="mistakes", verbose_name=_("所屬測驗紀錄")
    )
    question_text = models.TextField(verbose_name=_("題目內容"))
    user_answer = models.TextField(verbose_name=_("使用者答案"))
    correct_answer = models.TextField(verbose_name=_("正確答案"))
    explanation = models.TextField(verbose_name=_("解析說明"), blank=True, null=True)

    class Meta:
        verbose_name = _("錯題明細")
        verbose_name_plural = _("錯題明細")

    def __str__(self):
        return f"錯題: {self.question_text[:20]}..."

class QuestionDeepAnalysis(models.Model):
    """紀錄單一題目的 AI 深度解析與延伸練習題"""

    analysis_result = models.ForeignKey(
        AnalysisResult, on_delete=models.CASCADE, related_name="deep_analyses", verbose_name=_("對應測驗卷")
    )
    question_index = models.IntegerField(verbose_name=_("題目索引(原題號)"))

    concept_explanation = models.TextField(verbose_name=_("觀念深度解析(Markdown)"))
    practice_questions = models.JSONField(default=list, verbose_name=_("3題相關練習題"))

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("生成時間"))

    class Meta:
        # 確保同一份考卷的同一題，只會生成一次解析
        unique_together = ("analysis_result", "question_index")
        verbose_name = _("AI 深度解析")
        verbose_name_plural = _("AI 深度解析")
