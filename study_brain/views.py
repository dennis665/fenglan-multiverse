import mimetypes

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

from .models import AnalysisResult, Category, Material, QuizMistake, QuizRecord, ReadingRecord
from .utils import extract_text_from_file, generate_ai_content


@login_required
def dashboard(request):
    """AI 教材大腦主控台"""
    categories = Category.objects.all()

    # * 我的教材庫 (使用者有加入收藏的)
    my_materials = Material.objects.filter(saved_by=request.user).order_by("-uploaded_at")

    # * 探索公開教材 (使用者還沒加入收藏的)
    explore_materials = Material.objects.exclude(saved_by=request.user).order_by("-uploaded_at")

    context = {"categories": categories, "my_materials": my_materials, "explore_materials": explore_materials}
    return render(request, "study_brain/dashboard.html", context)


@login_required
def upload_material(request):
    """處理教材檔案上傳"""
    if request.method == "POST":
        category_id = request.POST.get("category")
        title = request.POST.get("title")
        file_obj = request.FILES.get("file")

        if category_id and title and file_obj:
            category = get_object_or_404(Category, id=category_id)
            material = Material.objects.create(category=category, uploader=request.user, title=title, file=file_obj)
            #! 上傳者自動將該教材加入「我的教材庫」
            material.saved_by.add(request.user)
            messages.success(request, _("教材上傳成功！您可以開始進行 AI 訓練。"))
        else:
            messages.error(request, _("請填寫完整資訊並上傳檔案。"))

    return redirect("study_brain:dashboard")


@login_required
def generate_analysis(request, material_id):
    """觸發 AI 訓練與解析 (支援題庫無限擴充)"""
    if request.method == "POST":
        #! 現在是公開教材，所以任何人都可以對該教材按下「訓練 AI」來擴充題庫
        material = get_object_or_404(Material, id=material_id)

        #! 檢查是否已經有歷史分析紀錄
        existing_analysis = AnalysisResult.objects.filter(material=material).first()
        existing_summary = existing_analysis.summary if existing_analysis else None
        existing_questions = existing_analysis.questions_data if existing_analysis else []

        #! 讀取實體檔案路徑並萃取文字
        file_path = material.file.path
        text_content = extract_text_from_file(file_path)

        if not text_content:
            messages.error(request, _("檔案解析失敗或內容為空，無法進行訓練。"))
            return redirect("study_brain:dashboard")

        #! 呼叫 AI 產生內容 (傳入歷史資料以避免重複)
        new_summary, new_quiz_data, error_msg = generate_ai_content(text_content, existing_summary, existing_questions)

        #! 如果有明確的錯誤訊息，直接發送給前端
        if error_msg:
            messages.error(request, error_msg)
        elif new_quiz_data:
            combined_questions = existing_questions + new_quiz_data

            if existing_analysis:
                existing_analysis.questions_data = combined_questions
                existing_analysis.save()
                messages.success(request, _(f"AI 進階訓練完成！已為教材新增 {len(new_quiz_data)} 題情境題。"))
            else:
                AnalysisResult.objects.create(material=material, summary=new_summary, questions_data=combined_questions)
                messages.success(request, _("AI 首次分析完成！已產生重點摘要與初始練習題。"))
        else:
            messages.error(request, _("AI 產出過程發生未知錯誤，請稍後再試。"))

    return redirect("study_brain:dashboard")


@login_required
def study_room(request, material_id):
    """專屬學習室視圖"""
    material = get_object_or_404(Material, id=material_id)
    latest_analysis = AnalysisResult.objects.filter(material=material).first()

    if not latest_analysis:
        messages.warning(request, _("該教材尚未產生分析資料。"))
        return redirect("study_brain:dashboard")

    #! 寫入閱讀紀錄
    ReadingRecord.objects.create(user=request.user, material=material)

    context = {"material": material, "latest_analysis": latest_analysis}
    return render(request, "study_brain/study_room.html", context)


@login_required
def submit_quiz(request, analysis_id):
    """處理測驗批改與紀錄錯題"""
    if request.method == "POST":
        analysis = get_object_or_404(AnalysisResult, id=analysis_id)
        questions = analysis.questions_data

        total_q = len(questions)
        correct_count = 0
        mistakes = []

        #! 核對答案
        for i, q_data in enumerate(questions):
            #! 前端傳來的 name 是 question_0, question_1...
            user_answer = request.POST.get(f"question_{i}", "")
            correct_answer = q_data.get("answer", "")

            if user_answer == correct_answer:
                correct_count += 1
            else:
                mistakes.append(
                    {
                        "question": q_data.get("question", ""),
                        "user_answer": user_answer,
                        "correct_answer": correct_answer,
                    }
                )

        error_rate = 0.0
        if total_q > 0:
            error_rate = round(((total_q - correct_count) / total_q) * 100, 2)

        #! 寫入測驗總紀錄
        quiz_record = QuizRecord.objects.create(
            user=request.user,
            analysis_result=analysis,
            total_questions=total_q,
            correct_count=correct_count,
            error_rate=error_rate,
        )

        #! 寫入詳細錯題紀錄
        for mist in mistakes:
            QuizMistake.objects.create(
                quiz_record=quiz_record,
                question_text=mist["question"],
                user_answer=mist["user_answer"],
                correct_answer=mist["correct_answer"],
            )

        messages.success(request, _(f"測驗提交成功！您的正確率為 {correct_count}/{total_q}。"))
        return redirect("study_brain:quiz_result", record_id=quiz_record.pk)

    return redirect("study_brain:dashboard")


@login_required
def quiz_result(request, record_id):
    """測驗結果報表與錯題解析視圖"""
    record = get_object_or_404(QuizRecord, id=record_id, user=request.user)
    mistakes = QuizMistake.objects.filter(quiz_record=record)

    context = {
        "record": record,
        "mistakes": mistakes,
    }
    return render(request, "study_brain/quiz_result.html", context)


@login_required
def view_material(request, material_id):
    """線上觀看原始教材檔案"""
    material = get_object_or_404(Material, id=material_id)

    if not material.file or not material.file.storage.exists(material.file.name):
        raise Http404(_("檔案不存在或已遺失"))

    # * 自動判斷檔案 MIME 類型
    content_type, encoding = mimetypes.guess_type(material.file.name)
    if not content_type:
        content_type = "application/octet-stream"

    # * 使用 FileResponse 回傳檔案流
    response = FileResponse(material.file.open("rb"), content_type=content_type)

    # * 設定 inline 讓瀏覽器嘗試直接渲染（如 PDF），若不支援則會自動下載
    file_name = material.file.name.split("/")[-1]
    response["Content-Disposition"] = f'inline; filename="{file_name}"'

    return response


@login_required
def toggle_save_material(request, material_id, action):
    """將教材加入或移出個人教材庫"""
    material = get_object_or_404(Material, id=material_id)

    if action == "add":
        material.saved_by.add(request.user)
        messages.success(request, _(f"已將「{material.title}」加入您的教材庫！"))
    elif action == "remove":
        material.saved_by.remove(request.user)
        messages.success(request, _(f"已將「{material.title}」從教材庫移除。"))

    return redirect("study_brain:dashboard")


@login_required
def quiz_history_list(request):
    """使用者的測驗歷史紀錄清單"""
    #! 抓取當前使用者所有的測驗紀錄，並預先載入關聯的分析結果與教材資料 (避免 N+1 查詢問題)
    records = (
        QuizRecord.objects.filter(user=request.user).select_related("analysis_result__material").order_by("-created_at")
    )

    context = {"records": records}
    return render(request, "study_brain/quiz_history.html", context)
