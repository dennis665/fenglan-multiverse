from utils.logger_utils import time_tracker

#! 包裝整個 import 區塊或初始化邏輯
with time_tracker("study_brain"):
    import mimetypes
    import re

    from django.contrib import messages
    from django.contrib.auth.decorators import login_required
    from django.http import FileResponse, Http404, JsonResponse
    from django.shortcuts import get_object_or_404, redirect, render
    from django.utils.translation import gettext_lazy as _

    from .models import (
        AnalysisResult,
        Category,
        Material,
        QuestionDeepAnalysis,
        QuizMistake,
        QuizRecord,
        ReadingRecord,
    )
    from .utils import (
        extract_text_from_file,
        generate_ai_content,
        generate_question_deep_analysis,
    )


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
        #! 取得前端 checkbox 的值，如果有勾選，值會是 'on'
        is_exam_paper = request.POST.get("is_exam_paper") == "on"

        if category_id and title and file_obj:
            category = get_object_or_404(Category, id=category_id)
            material = Material.objects.create(
                category=category,
                uploader=request.user,
                title=title,
                file=file_obj,
                is_exam_paper=is_exam_paper,  # * 存入資料庫
            )
            #! 上傳者自動將該教材加入「我的教材庫」
            material.saved_by.add(request.user)
            messages.success(request, _("教材上傳成功！您可以開始進行 AI 訓練。"))
        else:
            messages.error(request, _("請填寫完整資訊並上傳檔案。"))

    return redirect("study_brain:dashboard")


@login_required
def generate_analysis(request, material_id):
    """觸發 AI 訓練與解析"""
    if request.method == "POST":
        #! 現在是公開教材，所以任何人都可以對該教材按下「訓練 AI」來擴充題庫
        material = get_object_or_404(Material, id=material_id)

        #! 歷屆考題防呆機制 (只能訓練一次)
        if material.is_exam_paper and AnalysisResult.objects.filter(material=material).exists():
            messages.warning(request, _("此為歷屆考題，題目內容固定，無法重複呼叫 AI 擴充新題！"))
        else:
            #! 檢查是否已經有歷史分析紀錄
            existing_analysis = AnalysisResult.objects.filter(material=material).first()
            existing_summary = existing_analysis.summary if existing_analysis else None
            existing_questions = existing_analysis.questions_data if existing_analysis else []

            #! 讀取實體檔案路徑並萃取文字
            file_path = material.file.path
            text_content = extract_text_from_file(file_path)

            if not text_content and not file_path.lower().endswith((".pdf", ".mp4", ".mov", ".avi")):
                messages.error(request, _("檔案解析失敗或內容為空，無法進行訓練。"))
                return redirect("study_brain:dashboard")

            #! 呼叫 AI 產生內容 (傳入歷史資料以避免重複)
            new_summary, new_quiz_data, error_msg = generate_ai_content(
                file_path=file_path,
                text_content=text_content,
                existing_summary=existing_summary,
                existing_questions=existing_questions,
                is_exam_paper=material.is_exam_paper,
            )

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
                    AnalysisResult.objects.create(
                        material=material, summary=new_summary, questions_data=combined_questions
                    )
                    messages.success(request, _("AI 首次分析完成！已產生重點摘要與初始練習題。"))
            else:
                messages.error(request, _("AI 產出過程發生未知錯誤，請稍後再試。"))

        next_url = request.POST.get("next_url")
        if next_url:
            return redirect(next_url)

    return redirect("study_brain:dashboard")


@login_required
def study_room(request, material_id):
    """專屬學習室視圖 (支援自由切換是否顯示已作答題目)"""
    material = get_object_or_404(Material, id=material_id)
    latest_analysis = AnalysisResult.objects.filter(material=material).first()

    if not latest_analysis:
        messages.warning(request, _("該教材尚未產生分析資料。"))
        return redirect("study_brain:dashboard")

    #! 取得前端的開關狀態 (預設為 False，也就是隱藏舊題)
    show_all = request.GET.get("show_all") == "true"

    #! 抓取該使用者過去作答過的紀錄
    past_records = QuizRecord.objects.filter(user=request.user, analysis_result=latest_analysis)
    seen_questions = set()
    for record in past_records:
        if isinstance(record.attempted_questions, list):
            seen_questions.update(record.attempted_questions)

    #! 決定要顯示哪些題目
    display_questions = []
    unseen_count = 0

    for i, q in enumerate(latest_analysis.questions_data):
        q_text = q.get("question")
        is_seen = q_text in seen_questions

        if not is_seen:
            unseen_count += 1

        #! 如果開啟了「顯示全部」，或是這題「還沒看過」，就加入顯示清單
        if show_all or not is_seen:
            q_copy = dict(q)
            q_copy["original_index"] = i
            q_copy["is_seen"] = is_seen  # * 標記這題是否做過，讓前端可以加上小標籤
            display_questions.append(q_copy)

    #! 只有在「沒有新題目」且「未開啟顯示全部」時，才顯示恭喜破關畫面
    all_done = (unseen_count == 0) and not show_all

    ReadingRecord.objects.create(user=request.user, material=material)

    #! 取得這份教材「已經生成過深度解析」的題目索引清單 (Set 加速查詢)
    analyzed_indices = set(
        QuestionDeepAnalysis.objects.filter(analysis_result=latest_analysis).values_list("question_index", flat=True)
    )

    context = {
        "material": material,
        "latest_analysis": latest_analysis,
        "quiz_questions": display_questions,
        "all_done": all_done,
        "total_bank_size": len(latest_analysis.questions_data),
        "seen_count": len(seen_questions),
        "show_all": show_all,  # * 把開關狀態傳給前端
        "analyzed_indices": analyzed_indices,
    }
    return render(request, "study_brain/study_room.html", context)


@login_required
def submit_quiz(request, analysis_id):
    """處理測驗批改與紀錄錯題 (支援動態題數)"""
    if request.method == "POST":
        analysis = get_object_or_404(AnalysisResult, id=analysis_id)
        questions = analysis.questions_data

        total_q = 0
        correct_count = 0
        mistakes = []
        attempted_list = []

        #! 核對答案
        for i, q_data in enumerate(questions):
            ans_key = f"question_{i}"

            #! 只有出現在前端表單裡的題目 (也就是還沒做過的) 才計分
            if ans_key in request.POST:
                total_q += 1
                user_answer = request.POST.get(ans_key, "").strip()
                attempted_list.append(q_data.get("question", ""))  # * 把這題加進「已作答」清單

                #! --- 以下為您原本的智慧批改邏輯 ---
                correct_answer_raw = str(q_data.get("answer", "")).strip()
                options = [str(opt).strip() for opt in q_data.get("options", [])]

                correct_text = correct_answer_raw
                correct_letter = "?"

                match = re.match(r"^(選項|Option\s*)?([A-Z])\.?$", correct_answer_raw, re.IGNORECASE)
                if match:
                    letter = match.group(2).upper()
                    idx = ord(letter) - ord("A")
                    if 0 <= idx < len(options):
                        correct_text = options[idx]
                        correct_letter = letter
                else:
                    if correct_text in options:
                        correct_letter = chr(ord("A") + options.index(correct_text))
                    else:
                        for idx, opt in enumerate(options):
                            if correct_text in opt or opt in correct_text:
                                correct_text = opt
                                correct_letter = chr(ord("A") + idx)
                                break

                user_letter = "?"
                if user_answer in options:
                    user_letter = chr(ord("A") + options.index(user_answer))

                if user_answer == correct_text:
                    correct_count += 1
                else:
                    formatted_user_ans = f"{user_letter}. {user_answer}" if user_answer else str(_("未作答"))
                    formatted_correct_ans = f"{correct_letter}. {correct_text}"
                    original_q_number = i + 1

                    mistakes.append(
                        {
                            "question": f"Q{original_q_number}. {q_data.get('question', '')}",
                            "user_answer": formatted_user_ans,
                            "correct_answer": formatted_correct_ans,
                            "explanation": q_data.get("explanation", _("此為舊版題目，無提供解析。")),
                        }
                    )

        #! 如果交了白卷或沒題目，擋下來
        if total_q == 0:
            messages.warning(request, _("沒有送出任何有效答案！"))
            return redirect("study_brain:study_room", material_id=analysis.material.pk)

        error_rate = round(((total_q - correct_count) / total_q) * 100, 2)

        #! 寫入測驗總紀錄
        quiz_record = QuizRecord.objects.create(
            user=request.user,
            analysis_result=analysis,
            total_questions=total_q,
            correct_count=correct_count,
            error_rate=error_rate,
            attempted_questions=attempted_list,  # * 存入剛才收集的作答清單
        )

        #! 寫入詳細錯題紀錄
        for mist in mistakes:
            QuizMistake.objects.create(
                quiz_record=quiz_record,
                question_text=mist["question"],
                user_answer=mist["user_answer"],
                correct_answer=mist["correct_answer"],
                explanation=mist["explanation"],
            )

        messages.success(request, str(_(f"測驗提交成功！您的正確率為 {correct_count}/{total_q}。")))
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


@login_required
def api_get_deep_analysis(request, analysis_id, q_index):
    """處理前端請求：取得或生成深度解析"""
    analysis_result = get_object_or_404(AnalysisResult, id=analysis_id)

    #! 檢查 DB 是否已經有前人生成過這題的解析
    deep_analysis = QuestionDeepAnalysis.objects.filter(analysis_result=analysis_result, question_index=q_index).first()

    if deep_analysis:
        return JsonResponse(
            {
                "status": "success",
                "is_new": False,
                "concept_explanation": deep_analysis.concept_explanation,
                "practice_questions": deep_analysis.practice_questions,
            }
        )

    #! 如果沒有，就立刻去查題庫，並呼叫 AI
    try:
        q_data = analysis_result.questions_data[q_index]
    except IndexError:
        return JsonResponse({"status": "error", "message": "找不到該題目"}, status=404)

    ai_result = generate_question_deep_analysis(
        question_text=q_data.get("question", ""),
        options=q_data.get("options", []),
        answer=q_data.get("answer", ""),
        explanation=q_data.get("explanation", ""),
    )

    if not ai_result:
        return JsonResponse(
            {"status": "error", "message": "AI 目前請求量過大需要喘口氣 🥵，請等待約 60 秒後再點擊一次！"}, status=429
        )

    #! 儲存進 DB 造福後人
    deep_analysis = QuestionDeepAnalysis.objects.create(
        analysis_result=analysis_result,
        question_index=q_index,
        concept_explanation=ai_result.get("concept_explanation", ""),
        practice_questions=ai_result.get("practice_questions", []),
    )

    return JsonResponse(
        {
            "status": "success",
            "is_new": True,
            "concept_explanation": deep_analysis.concept_explanation,
            "practice_questions": deep_analysis.practice_questions,
        }
    )


#! 定義 Python 專屬的「自然排序」邏輯
def natural_sort_key(mistake):
    #! 利用正規表達式，抓出題目字串裡面的「第一個數字」
    #! 例如從 "Q10. 請問..." 抓出數字 10。如果沒數字就給個預設值 9999
    match = re.search(r"\d+", mistake.question_text)
    q_num = int(match.group()) if match else 9999

    #! 回傳一個 Tuple，Python 會依序比較這三個值來決定順序：
    return (
        #! 教材 ID (-號代表由大到小，越新的教材在越上面)
        -mistake.quiz_record.analysis_result.material.id,
        #! 題號數字 (正常的整數排序，1, 2, 3... 10，完美解決字串問題！)
        q_num,
        #! 測驗時間 (-號代表越近期的錯題紀錄排在越上面)
        -mistake.quiz_record.created_at.timestamp(),
    )


@login_required
def mistake_book(request):
    """
    專屬錯題本：顯示使用者曾經答錯的所有題目與 AI 解析
    """
    mistakes_qs = QuizMistake.objects.filter(quiz_record__user=request.user).select_related(
        "quiz_record__analysis_result__material"
    )
    #! 執行排序，並轉成 List 傳給前端的 {% regroup %} 使用
    mistakes = sorted(mistakes_qs, key=natural_sort_key)

    context = {
        "mistakes": mistakes,
    }
    return render(request, "study_brain/mistake_book.html", context)
