from django.contrib import admin

from .models import AnalysisResult, Category, Material, QuizMistake, QuizRecord, ReadingRecord


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
