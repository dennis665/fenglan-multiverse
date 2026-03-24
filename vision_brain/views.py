import base64
import io
import os
import re
import time

#! 關閉 Paddle 每次都要連線上網檢查模型
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

import numpy as np
import pytesseract
from django.contrib import messages
from django.shortcuts import redirect, render
from paddleocr import PaddleOCR
from PIL import Image

from utils.logger_utils import jinfo

#! 設定 Tesseract 執行檔路徑 (Windows 必備)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

#! 讀取模型只執行一次
PADDLE_MODELS_CACHE = {}


def get_paddle_instance(lang_code):
    if lang_code not in PADDLE_MODELS_CACHE:
        start_time = time.time()
        PADDLE_MODELS_CACHE[lang_code] = PaddleOCR(
            use_textline_orientation=True,
            enable_mkldnn=False,
            #! 改用輕量化 Mobile 模型 (針對 PP-OCRv4/v5)
            text_detection_model_name="PP-OCRv4_mobile_det",
            text_recognition_model_name="PP-OCRv4_mobile_rec",
        )
        jinfo(f"🕒 首次讀取模型耗時: {time.time() - start_time:.2f} 秒")
    return PADDLE_MODELS_CACHE[lang_code]


def ocr_recognize(request):
    """處理即時圖片上傳與雙引擎 OCR 辨識"""
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
            #! 轉成 Base64 預覽圖
            img = Image.open(uploaded_file).convert("RGB")
            img.thumbnail((1024, 1024))
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG")
            encoded_img = base64.b64encode(buffered.getvalue()).decode("utf-8")
            image_data_uri = f"data:image/jpeg;base64,{encoded_img}"

            start_time = time.time()
            final_text = ""

            #! PaddleOCR 處理邏輯
            if selected_engine == "paddle":
                #! 語言代碼對應
                paddle_lang_map = {
                    "mix": "chinese_cht",  # * Paddle 的繁中模型天生支援中英混合
                    "cht": "chinese_cht",
                    "en": "en",
                }
                lang_code = paddle_lang_map.get(selected_lang, "chinese_cht")

                ocr = get_paddle_instance(lang_code)

                #! 執行辨識
                img_array = np.array(img)[:, :, ::-1]
                result = ocr.predict(img_array)

                #! 解析 Paddle 的多層陣列結果
                texts = []
                for res in result:
                    if "rec_texts" in res:
                        texts.extend(res["rec_texts"])

                final_text = "\n".join(texts)
                jinfo(f"🕒 PADDLEOCR 耗時: {time.time() - start_time:.2f} 秒")

            #! Tesseract 處理邏輯
            else:
                #! 語言代碼對應
                tesseract_lang_map = {"mix": "chi_tra+eng", "cht": "chi_tra", "en": "eng"}
                lang_code = tesseract_lang_map.get(selected_lang, "chi_tra+eng")

                #! 執行辨識
                text = pytesseract.image_to_string(img, lang=lang_code)
                #! 精準移除中文字之間的空格 (對 Tesseract 特別重要)
                final_text = re.sub(r"(?<=[\u4e00-\u9fa5])[ \t]+|[ \t]+(?=[\u4e00-\u9fa5])", "", text).strip()
                jinfo(f"🕒 TESSERACT 辨識耗時: {time.time() - start_time:.2f} 秒")

            if not final_text:
                messages.warning(request, "⚠️ 圖片中沒有辨識出任何文字。")
            else:
                messages.success(request, f"✅ 辨識成功！引擎：{selected_engine}")
                request.session["ocr_result_text"] = final_text
                request.session["ocr_image_uri"] = image_data_uri
            return redirect(request.path)

        except Exception as e:
            messages.error(request, f"❌ 辨識發生錯誤：{str(e)}")
            return redirect(request.path)

    context = {
        "result_text": result_text,
        "selected_lang": selected_lang,
        "selected_engine": selected_engine,
        "image_data_uri": image_data_uri,
    }
    return render(request, "vision_brain/index.html", context)
