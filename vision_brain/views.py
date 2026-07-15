from utils.logger_utils import time_tracker

#! 包裝整個 import 區塊或初始化邏輯
with time_tracker("Vision_Brain"):
    import base64
    import io
    import os
    import re
    import time
    from collections import Counter

    #! 關閉 Paddle 每次都要連線上網檢查模型
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

    from django.contrib import messages
    from django.shortcuts import redirect, render
    from PIL import Image

    from utils.logger_utils import jinfo

    #! 讀取模型只執行一次 (快取字典)
    PADDLE_MODELS_CACHE = {}
    YOLO_MODEL_CACHE = None


def get_paddle_instance(lang_code):
    """獲取或初始化 PaddleOCR 模型"""
    if lang_code not in PADDLE_MODELS_CACHE:
        start_time = time.time()
        from paddleocr import PaddleOCR
        PADDLE_MODELS_CACHE[lang_code] = PaddleOCR(
            use_textline_orientation=True,
            enable_mkldnn=False,
            #! 改用輕量化 Mobile 模型 (針對 PP-OCRv4/v5)
            text_detection_model_name="PP-OCRv4_mobile_det",
            text_recognition_model_name="PP-OCRv4_mobile_rec",
        )
        jinfo(f"🕒 首次讀取 Paddle 模型耗時：{time.time() - start_time:.2f} 秒")
    return PADDLE_MODELS_CACHE[lang_code]


def get_yolo_instance():
    """獲取或初始化 YOLOv11 模型"""
    global YOLO_MODEL_CACHE
    if YOLO_MODEL_CACHE is None:
        start_time = time.time()
        from ultralytics import YOLO
        #! 載入最新的 YOLOv11 預訓練模型
        YOLO_MODEL_CACHE = YOLO("yolo11n.pt")
        jinfo(f"🕒 首次讀取 YOLO 模型耗時：{time.time() - start_time:.2f} 秒")
    return YOLO_MODEL_CACHE


def ocr_recognize(request):
    """處理即時圖片上傳與視覺 AI (OCR / YOLO) 辨識"""
    import cv2
    import numpy as np
    import pytesseract

    #! 設定 Tesseract 執行檔路徑 (Windows 必備)
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    result_text = request.session.pop("ocr_result_text", None)
    image_data_uri = request.session.pop("ocr_image_uri", None)
    selected_lang = request.session.get("ocr_selected_lang", "cht")
    selected_engine = request.session.get("ocr_selected_engine", "paddle")

    if request.method == "POST":
        uploaded_file = request.FILES.get("image")
        if not uploaded_file:
            messages.error(request, "未收到上傳的檔案，請重新嘗試。")
            return redirect(request.path)

        selected_lang = request.POST.get("language", "cht")
        selected_engine = request.POST.get("ocr_engine", "paddle")

        request.session["ocr_selected_lang"] = selected_lang
        request.session["ocr_selected_engine"] = selected_engine

        try:
            #! 先將上傳圖片轉為 PIL 格式並製作預設 Base64 預覽圖
            img = Image.open(uploaded_file).convert("RGB")
            img.thumbnail((1024, 1024))
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG")
            encoded_img = base64.b64encode(buffered.getvalue()).decode("utf-8")
            image_data_uri = f"data:image/jpeg;base64,{encoded_img}"

            start_time = time.time()
            final_text = ""

            # ==========================================
            #! PaddleOCR 處理邏輯
            # ==========================================
            if selected_engine == "paddle":
                paddle_lang_map = {
                    "mix": "chinese_cht",
                    "cht": "chinese_cht",
                    "en": "en",
                }
                lang_code = paddle_lang_map.get(selected_lang, "chinese_cht")
                ocr = get_paddle_instance(lang_code)

                #! 轉為 OpenCV BGR 格式
                img_array = np.array(img)[:, :, ::-1]
                result = ocr.predict(img_array)

                texts = []
                for res in result:
                    if "rec_texts" in res:
                        texts.extend(res["rec_texts"])

                final_text = "\n".join(texts)
                jinfo(f"🕒 PADDLEOCR 耗時：{time.time() - start_time:.2f} 秒")

            # ==========================================
            #! Tesseract 處理邏輯
            # ==========================================
            elif selected_engine == "tesseract":
                tesseract_lang_map = {"mix": "chi_tra+eng", "cht": "chi_tra", "en": "eng"}
                lang_code = tesseract_lang_map.get(selected_lang, "chi_tra+eng")

                text = pytesseract.image_to_string(img, lang=lang_code)
                final_text = re.sub(r"(?<=[\u4e00-\u9fa5])[ \t]+|[ \t]+(?=[\u4e00-\u9fa5])", "", text).strip()
                jinfo(f"🕒 TESSERACT 辨識耗時：{time.time() - start_time:.2f} 秒")

            # ==========================================
            #! YOLOv11 物件偵測邏輯
            # ==========================================
            elif selected_engine == "yolo":
                model = get_yolo_instance()

                #! 將 PIL 影像轉為 OpenCV 格式供 YOLO 使用
                img_cv = np.array(img)[:, :, ::-1].copy()

                #! 執行辨識，信心值設定為 50%
                results = model(img_cv, conf=0.5)
                result = results[0]

                #! 統計數量
                counts = Counter()
                for box in result.boxes:
                    cls_id = int(box.cls[0])
                    label = model.names[cls_id]
                    counts[label] += 1

                #! 格式化文字輸出結果
                stats_lines = ["【 📊 YOLOv11 物件偵測統計 】", "=" * 35]
                stats_lines.append(f"{'物品分類':<15} | {'數量':<5}")
                stats_lines.append("-" * 35)

                total_count = 0
                for item, num in counts.items():
                    stats_lines.append(f"{item:<15} | {num:<5}")
                    total_count += num

                stats_lines.append("-" * 35)
                stats_lines.append(f"{'總計':<15} | {total_count:<5}")
                stats_lines.append("=" * 35)

                final_text = "\n".join(stats_lines)

                #! 將標註好的圖片轉回 Base64，替換掉原本的預覽圖
                annotated_img = result.plot(labels=False, conf=False, line_width=2)
                _, buffer = cv2.imencode('.jpg', annotated_img)
                encoded_annotated = base64.b64encode(buffer).decode('utf-8')
                image_data_uri = f"data:image/jpeg;base64,{encoded_annotated}"

                jinfo(f"🕒 YOLO 辨識與繪圖耗時：{time.time() - start_time:.2f} 秒")

            # ==========================================
            #! 統一結果回傳
            # ==========================================
            if not final_text or (selected_engine == "yolo" and total_count == 0):
                messages.warning(request, "⚠️ 圖片中沒有偵測出任何內容。")
            else:
                messages.success(request, f"✅ 處理成功！引擎：{selected_engine}")
                request.session["ocr_result_text"] = final_text
                request.session["ocr_image_uri"] = image_data_uri

            return redirect(request.path)

        except Exception as e:
            messages.error(request, f"❌ 執行發生錯誤：{str(e)}")
            return redirect(request.path)

    context = {
        "result_text": result_text,
        "selected_lang": selected_lang,
        "selected_engine": selected_engine,
        "image_data_uri": image_data_uri,
    }
    return render(request, "vision_brain/index.html", context)
