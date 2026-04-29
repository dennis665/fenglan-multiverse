from utils.logger_utils import time_tracker

#! 包裝整個 import 區塊或初始化邏輯
with time_tracker("sh_recognition"):
    import os
    from datetime import datetime

    from django.conf import settings
    from django.contrib import messages
    from django.shortcuts import get_object_or_404, redirect, render
    from django.utils import timezone
    from django.utils.translation import gettext_lazy as _

    from .models import AIModel, ImageRecord


def index(request):
    #! 顯示首頁表單與最新紀錄
    models = AIModel.objects.all().order_by("-uploaded_at")
    records = ImageRecord.objects.all().order_by("-created_at")[:10]

    if request.method == "POST":
        action = request.POST.get("action")

        #! 處理圖片上傳並進行辨識 (支援多圖)
        if action == "recognize_image":
            image_files = request.FILES.getlist("image_file")
            model_id = request.POST.get("model_id")
            user_note = request.POST.get("user_note", "")

            try:
                threshold = float(request.POST.get("threshold", 0.5))
            except ValueError:
                threshold = 0.5

            if image_files and model_id:
                from .inference_utils import run_image_inference
                selected_model = AIModel.objects.get(id=model_id)
                success_count = 0
                error_msgs = []

                #! 迴圈處理每一張上傳的圖片
                for image_file in image_files:
                    try:
                        record = ImageRecord.objects.create(
                            original_image=image_file,
                            used_model=selected_model,
                            user_note=user_note,
                            conf_threshold=threshold,
                        )

                        orig_path = record.original_image.path
                        model_path = selected_model.model_file.path
                        output_dir = os.path.join(settings.MEDIA_ROOT, "images", "result")

                        result_img_path, result_txt, has_object = run_image_inference(
                            orig_path, model_path, output_dir, threshold=threshold
                        )

                        rel_result_path = os.path.relpath(result_img_path, settings.MEDIA_ROOT)
                        record.result_image.name = rel_result_path
                        record.result_text = result_txt
                        record.has_object = has_object
                        record.save()
                        success_count += 1

                    except Exception as e:
                        error_msgs.append(f"{image_file.name}: {str(e)}")

                if success_count > 0:
                    messages.success(request, _(f"成功完成 {success_count} 張圖片辨識！"))
                if error_msgs:
                    messages.error(request, _("部分圖片辨識失敗：") + " | ".join(error_msgs))

            return redirect("sh_recognition:index")

    context = {
        "models": models,
        "records": records,
    }
    return render(request, "sh_recognition/index.html", context)


def record_list(request):
    #! 清單查詢與刪除邏輯
    if request.method == "POST":
        action = request.POST.get("action")

        #! 處理批次刪除勾選的紀錄
        if action == "delete_records":
            record_ids = request.POST.getlist("record_ids")
            if record_ids:
                records_to_delete = ImageRecord.objects.filter(id__in=record_ids)
                deleted_count = 0

                for r in records_to_delete:
                    # * 1. 刪除結果圖片實體檔案
                    if r.result_image and os.path.isfile(r.result_image.path):
                        os.remove(r.result_image.path)

                    # * 2. 檢查原圖是否被其他紀錄共用，若無則一併刪除實體檔案
                    orig_name = r.original_image.name
                    if orig_name:
                        usage_count = ImageRecord.objects.filter(original_image=orig_name).count()
                        if usage_count <= 1 and os.path.isfile(r.original_image.path):
                            os.remove(r.original_image.path)

                    # * 3. 刪除資料庫紀錄
                    r.delete()
                    deleted_count += 1

                messages.success(request, _(f"已成功刪除 {deleted_count} 筆辨識紀錄。"))
            else:
                messages.error(request, _("請至少勾選一筆要刪除的資料。"))

            return redirect("sh_recognition:record_list")

    queryset = ImageRecord.objects.all().order_by("-created_at")

    model_filter = request.GET.get("model_id")
    date_filter = request.GET.get("date")
    keyword = request.GET.get("keyword")

    if "date" not in request.GET:
        date_filter = timezone.localtime().strftime("%Y-%m-%d")

    if model_filter:
        queryset = queryset.filter(used_model_id=model_filter)

    if date_filter:
        try:
            search_date = datetime.strptime(date_filter, "%Y-%m-%d").date()
            start_datetime = timezone.make_aware(datetime.combine(search_date, datetime.min.time()))
            end_datetime = timezone.make_aware(datetime.combine(search_date, datetime.max.time()))
            queryset = queryset.filter(created_at__range=(start_datetime, end_datetime))
        except ValueError:
            pass

    if keyword:
        queryset = queryset.filter(user_note__icontains=keyword)

    models = AIModel.objects.all()
    return render(
        request,
        "sh_recognition/record_list.html",
        {"records": queryset, "models": models, "current_date": date_filter},
    )


def record_detail(request, pk):
    #! 詳細查看頁面與重新辨識邏輯
    record = get_object_or_404(ImageRecord, pk=pk)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "re_recognize":
            new_model_id = request.POST.get("new_model_id")
            try:
                new_threshold = float(request.POST.get("new_threshold", 0.5))
            except ValueError:
                new_threshold = 0.5

            if new_model_id:
                from .inference_utils import run_image_inference
                new_model = get_object_or_404(AIModel, id=new_model_id)

                new_record = ImageRecord.objects.create(
                    original_image=record.original_image,
                    used_model=new_model,
                    user_note=record.user_note,
                    conf_threshold=new_threshold,
                )

                orig_path = new_record.original_image.path
                model_path = new_model.model_file.path
                output_dir = os.path.join(settings.MEDIA_ROOT, "images", "result")

                try:
                    result_img_path, result_txt, has_object = run_image_inference(
                        orig_path, model_path, output_dir, threshold=new_threshold
                    )
                    rel_result_path = os.path.relpath(result_img_path, settings.MEDIA_ROOT)
                    new_record.result_image.name = rel_result_path
                    new_record.result_text = result_txt
                    new_record.has_object = has_object
                    new_record.save()

                    messages.success(request, _("已使用新模型完成重新辨識！"))
                    return redirect("sh_recognition:record_detail", pk=new_record.pk)
                except Exception as e:
                    new_record.delete()
                    messages.error(request, f"辨識發生錯誤: {str(e)}")

        return redirect("sh_recognition:record_detail", pk=pk)

    #! 取得該原圖已使用過的模型 ID 清單
    used_model_ids = ImageRecord.objects.filter(
        original_image=record.original_image.name
    ).values_list("used_model_id", flat=True)

    #! 過濾掉已使用的模型，確保不會重複辨識
    available_models = AIModel.objects.exclude(id__in=used_model_ids).order_by("-uploaded_at")

    return render(
        request,
        "sh_recognition/record_detail.html",
        {"record": record, "available_models": available_models},
    )
