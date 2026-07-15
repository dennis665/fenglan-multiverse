from django.contrib import admin

from .models import (
    AnalysisResult,
    Category,
    Material,
    QuestionDeepAnalysis,
    QuizMistake,
    QuizRecord,
    ReadingRecord,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "uploader", "uploaded_at")
    list_filter = ("category", "uploaded_at")
    search_fields = ("title",)


@admin.register(AnalysisResult)
class AnalysisResultAdmin(admin.ModelAdmin):
    list_display = ("material", "created_at")
    list_filter = ("created_at",)


@admin.register(ReadingRecord)
class ReadingRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "material", "read_at")
    list_filter = ("user", "read_at")


class QuizMistakeInline(admin.StackedInline):
    """在測驗紀錄中直接顯示錯題明細"""

    model = QuizMistake
    extra = 0
    readonly_fields = ("question_text", "user_answer", "correct_answer")


@admin.register(QuizRecord)
class QuizRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "analysis_result", "total_questions", "error_rate", "created_at")
    list_filter = ("user", "created_at")
    inlines = [QuizMistakeInline]  # * 讓錯題以子表單的形式顯示在測驗紀錄內


@admin.register(QuestionDeepAnalysis)
class QuestionDeepAnalysisAdmin(admin.ModelAdmin):
    """
    AI 深度解析後台管理介面
    """

    #! 列表頁顯示的欄位
    list_display = ("id", "analysis_result", "question_index", "created_at")
    #! 列表頁右側的過濾器
    list_filter = ("created_at", "analysis_result")
    #! 可供搜尋的欄位 (支援搜尋 Markdown 內容或對應測驗卷的 ID)
    search_fields = ("concept_explanation", "analysis_result__id")
    #! 唯讀欄位 (建立時間不可修改)
    readonly_fields = ("created_at",)
    #! 預設排序 (依建立時間由新到舊)
    ordering = ("-created_at",)
    #! 進入編輯頁面時的表單排版
    fieldsets = (
        ("關聯資訊", {"fields": ("analysis_result", "question_index")}),
        ("AI 生成內容", {"fields": ("concept_explanation", "practice_questions")}),
        ("系統時間", {"fields": ("created_at",)}),
    )
