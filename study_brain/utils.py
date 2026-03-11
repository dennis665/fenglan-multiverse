import json
import os

import docx
import pdfplumber
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from google import genai
from google.genai import types

#! 建立 Gemini 官方最新版 Client
client = genai.Client(api_key=settings.GEMINI_API_KEY)


def extract_text_from_file(file_path):
    """根據檔案副檔名萃取文字內容"""
    ext = os.path.splitext(file_path)[1].lower()
    text = ""

    try:
        if ext == ".pdf":
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
        elif ext in [".doc", ".docx"]:
            doc = docx.Document(file_path)
            for para in doc.paragraphs:
                text += para.text + "\n"
    except Exception as e:
        print(f"File extraction error: {e}")

    return text.strip()


def generate_ai_content(text_content, existing_summary=None, existing_questions=None):
    """呼叫 Gemini 產生重點摘要與 JSON 格式的測驗題 (支援動態擴充題庫)"""
    max_chars = 30000
    truncated_text = text_content[:max_chars]

    #! 動態建構 Prompt 任務指示
    prompt = f"請扮演專業的 AI 教材導師。閱讀以下教材內容：\n\n{truncated_text}\n\n"

    #! 如果沒有舊摘要，才要求 AI 產出
    if not existing_summary:
        prompt += "任務 1：請提供條理分明的重點摘要。\n"
    else:
        prompt += "任務 1：(您不需要提供重點摘要，請專注於出題)\n"

    #! 要求產出進階題目
    prompt += """
    任務 2：請出 5 題單選練習題，必須以純 JSON 陣列格式回傳。
    【難度與多樣性要求】：請出具備深度的「情境應用題」或「觀念變化題」，不要只考死背名詞。
    """

    #! 如果有舊題目，餵給 AI 當作黑名單
    if existing_questions:
        prompt += "\n【重要限制】：以下是已經出過的題目，請您「絕對不要」重複出類似或相同的題目：\n"
        for idx, q in enumerate(existing_questions):
            prompt += f"{idx + 1}. {q.get('question')}\n"

    prompt += """
    \nJSON 格式範例：
    [
        {
            "question": "題目內容",
            "options": ["選項A", "選項B", "選項C", "選項D"],
            "answer": "選項B"
        }
    ]
    
    請嚴格遵守以下輸出格式（請使用特定分隔符號以便程式解析）：
    """

    if not existing_summary:
        prompt += "===SUMMARY_START===\n(在此輸出重點摘要)\n===SUMMARY_END===\n"

    prompt += "===QUIZ_START===\n(在此輸出純 JSON 陣列)\n===QUIZ_END===\n"

    #! 呼叫 AI
    summary = existing_summary or ""  # * 如果有舊摘要，直接沿用
    quiz_data = []
    error_msg = None  # * 用來裝載給前端的錯誤提示

    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            config=types.GenerateContentConfig(
                temperature=0.3,  # * 稍微調高溫度(0.2->0.3)，讓情境題更豐富多變
            ),
            contents=prompt,
        )
        result_text = response.text

        #! 解析 AI 回傳的自訂格式
        if (
            not existing_summary
            and result_text
            and "===SUMMARY_START===" in result_text
            and "===SUMMARY_END===" in result_text
        ):
            summary = result_text.split("===SUMMARY_START===")[1].split("===SUMMARY_END===")[0].strip()

        if result_text and "===QUIZ_START===" in result_text and "===QUIZ_END===" in result_text:
            quiz_json_str = result_text.split("===QUIZ_START===")[1].split("===QUIZ_END===")[0].strip()
            quiz_json_str = quiz_json_str.replace("```json", "").replace("```", "").strip()
            quiz_data = json.loads(quiz_json_str)

    except Exception as e:
        print(f"AI Parsing Error: {e}")
        error_str = str(e)
        # * 判斷是否為伺服器忙碌
        if "503" in error_str or "429" in error_str:
            error_msg = _("AI 忙碌中，請稍後再試！")
        else:
            error_msg = _("AI 產出解析發生錯誤，請稍後再試。")

        summary = None
        quiz_data = None

    return summary, quiz_data, error_msg
