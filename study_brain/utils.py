import json
import os
import shutil
import tempfile
import time

import docx
import pdfplumber
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from google import genai
from google.genai import types

#! 建立 Gemini 官方最新版 Client
client = genai.Client(api_key=settings.GEMINI_API_KEY)

FALLBACK_MODELS = [
    "gemini-flash-latest",  # * 首選：最新主力 (每天 20 次)
    "gemini-2.5-flash",  # * 備援 1：前代主力 (每天額外 20 次)
    "gemini-3.1-flash-lite-preview",  # * 備援 2：超級救星！(每天 500 次，不再 404)
    "gemini-flash-lite-latest",  # * 備援 3：官方動態 Lite 捷徑
    "gemini-2.0-flash",  # * 備援 4：老將壓陣
]

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


def generate_ai_content(file_path, text_content, existing_summary=None, existing_questions=None, is_exam_paper=False):
    """混合雙引擎：PDF/影片 走 File API 視覺直讀，Word 走 50 萬字純文字萃取"""

    prompt = "請扮演專業的 AI 導師與出題專家。執行以下任務：\n\n"

    #! 判斷檔案類型，精細區分 PDF 與 影片
    is_pdf = file_path.lower().endswith(".pdf")
    is_video = file_path.lower().endswith((".mp4", ".mov", ".avi"))
    is_file_api_supported = is_pdf or is_video

    uploaded_gemini_file = None
    contents_payload = []  # * 用來裝載要送給 AI 的內容 (可以混搭檔案與文字)

    if is_pdf:
        #! PDF 模式：請 AI 閱讀圖文表格
        prompt += "【資料來源】：請仔細閱讀我附上的 PDF 檔案內容（包含文字、圖片與表格）。\n\n"
    elif is_video:
        #! 影片模式：請 AI 聽聲音並看畫面
        prompt += "【資料來源】：請仔細觀看我附上的影片檔案，聽取語音內容，並仔細觀察畫面細節（包含簡報、板書或軟體操作畫面）。\n\n"
    else:
        #! Word 模式：解放字數封印到 50 萬字
        max_chars = 500000
        truncated_text = text_content[:max_chars]
        prompt += f"【資料來源】：請閱讀以下內容：\n\n{truncated_text}\n\n"

    #! ======== 模式切換：歷屆考題 vs 一般教材 ========
    if is_exam_paper:
        prompt += """
        這是一份「歷屆考題」。
        任務：仔細閱讀資料來源，提取出裡面的「選擇題」或根據內容出題。
        - 如果文件中沒有提供正確答案，請您找出正確解答。
        - 請為每一題撰寫詳細的「解析 (explanation)」，說明正確答案為何正確，其他選項為何錯誤。
        - 不需要輸出重點摘要。
        """
    else:
        if not existing_summary:
            prompt += "任務 1：請提供條理分明的重點摘要。\n"
        else:
            prompt += "任務 1：(您不需要提供重點摘要，請專注於出題)\n"

        prompt += """
        任務 2：請出 15 題單選練習題，必須以純 JSON 陣列格式回傳。
        【難度與多樣性要求】：請出具備深度的「情境應用題」或「觀念變化題」。
        """
        if existing_questions:
            prompt += "\n【重要限制】：以下是已經出過的題目，請「絕對不要」重複出類似的題目：\n"
            for idx, q in enumerate(existing_questions):
                prompt += f"{idx + 1}. {q.get('question')}\n"

    prompt += """
    \nJSON 格式範例：
    [
        {
            "question": "題目內容",
            "options": ["選項A完整內容", "選項B完整內容", "選項C完整內容", "選項D完整內容"],
            "answer": "正確選項的完整內容",
            "explanation": "請詳細說明正確答案為何正確，並解釋其他選項為何錯誤。"
        }
    ]
    
    【極度重要】："answer" 欄位必須填寫「正確選項的完整文字內容」。
    請嚴格遵守以下輸出格式（請使用特定分隔符號以便程式解析）：
    """

    if not existing_summary and not is_exam_paper:
        prompt += "===SUMMARY_START===\n(在此輸出重點摘要)\n===SUMMARY_END===\n"
    prompt += "===QUIZ_START===\n(在此輸出純 JSON 陣列)\n===QUIZ_END===\n"

    #! ======== 準備發送 API 請求 ========
    temp_file_path = None  # * 用來追蹤本機暫存檔路徑
    if is_file_api_supported:
        try:
            file_type_name = "影片" if is_video else "PDF"

            #! 💡 關鍵防呆：建立純英文名稱的暫存檔，避開 Google SDK 的中文檔名 Bug
            ext = ".mp4" if is_video else ".pdf"
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
                shutil.copyfile(file_path, temp_file.name)
                temp_file_path = temp_file.name

            print(f"上傳 {file_type_name} 至 Google 伺服器 (使用安全暫存檔避開中文編碼)...")

            #! 上傳這個純英文的暫存檔，並強制指定顯示名稱為英文
            uploaded_gemini_file = client.files.upload(
                file=temp_file_path, config=types.UploadFileConfig(display_name="study_material")
            )

            #! 確保 Google 處理完畢
            while uploaded_gemini_file.state.name == "PROCESSING":  # pyright: ignore[reportOptionalMemberAccess]
                print(f"等待 Google 處理 {file_type_name} 檔案...")
                time.sleep(3)
                if uploaded_gemini_file.name:
                    uploaded_gemini_file = client.files.get(name=uploaded_gemini_file.name)

            contents_payload.append(uploaded_gemini_file)
        except Exception as e:
            file_type_name = "影片" if is_video else "PDF"
            print(f"{file_type_name} 上傳失敗，嘗試退回純文字模式: {e}")

            if is_pdf:
                prompt = prompt.replace(
                    "請仔細閱讀我附上的 PDF 檔案內容（包含文字、圖片與表格）。",
                    f"請閱讀以下內容：\n\n{text_content[:500000]}",
                )
            elif is_video:
                prompt = prompt.replace(
                    "請仔細觀看我附上的影片檔案，聽取語音內容，並仔細觀察畫面細節（包含簡報、板書或軟體操作畫面）。",
                    f"請閱讀以下內容：\n\n{text_content[:500000]}",
                )

    #! 將指令 Prompt 加入 Payload
    contents_payload.append(prompt)

    summary = existing_summary or ""
    quiz_data = []
    error_msg = None

    for model_name in FALLBACK_MODELS:
        try:
            print(f"🤖 正在嘗試使用模型: {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                config=types.GenerateContentConfig(temperature=0.3),
                contents=contents_payload,
            )
            result_text = response.text

            if result_text and not is_exam_paper and not existing_summary and "===SUMMARY_START===" in result_text:
                summary = result_text.split("===SUMMARY_START===")[1].split("===SUMMARY_END===")[0].strip()
            elif is_exam_paper:
                summary = str(_("此為歷屆考題匯入，無重點摘要。請直接前往「測驗練習」進行刷題！"))

            if result_text and "===QUIZ_START===" in result_text and "===QUIZ_END===" in result_text:
                quiz_json_str = result_text.split("===QUIZ_START===")[1].split("===QUIZ_END===")[0].strip()
                quiz_json_str = quiz_json_str.replace("```json", "").replace("```", "").strip()
                quiz_data = json.loads(quiz_json_str)
            break
        except Exception as e:
            error_msg = str(e)
            #! 檢查是否為 429 額度耗盡錯誤
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                print(f"⚠️ 模型 {model_name} 額度已滿 (429)，準備切換下一個備援模型...")
                continue  # * 忽略錯誤，進入下一次迴圈換模型
            else:
                #! 如果是其他錯誤 (例如 JSON 解析失敗、系統斷線)，就不換模型，直接報錯
                print(f"❌ 發生非額度相關錯誤: {error_msg}")
        error_msg = _("AI 忙碌中或檔案解析發生錯誤，請稍後再試！")

    #! ======== 雙重閱後即焚機制 ========
    #! 清理 Google 伺服器上的遠端檔案
    if uploaded_gemini_file and uploaded_gemini_file.name:
        try:
            print("清理 Google 伺服器上的暫存檔案...")
            client.files.delete(name=uploaded_gemini_file.name)
        except Exception as e:
            print(f"清理遠端檔案失敗: {e}")

    #! 清理剛剛在本機端產生的純英文暫存檔
    if temp_file_path and os.path.exists(temp_file_path):
        try:
            os.remove(temp_file_path)
        except Exception as e:
            print(f"清理本機暫存檔失敗: {e}")

    return summary, quiz_data, error_msg

def generate_question_deep_analysis(question_text, options, answer, explanation):
    """針對單一題目呼叫 AI 產生深度解析與 3 題延伸練習"""
    prompt = f"""
    請扮演專業的 AI 導師。學生遇到了一道難題，請針對這道題目進行「深度觀念解析」，並出 3 題「相關觀念的單選練習題」來幫助他確認是否真的懂了。

    【原始題目資訊】：
    - 題目：{question_text}
    - 選項：{", ".join(options)}
    - 正確答案：{answer}
    - 原本的簡易解析：{explanation}

    【任務 1：深度觀念解析 (concept_explanation)】
    請使用流暢、易懂的語氣，詳細解釋這題背後的核心觀念、公式或歷史背景。可以使用 Markdown 語法（粗體、條列式）來排版。

    【任務 2：產出 3 題練習題 (practice_questions)】
    請基於上述核心觀念，變化情境或換個角度，出 3 題難度相近的單選題。

    【輸出格式要求】：
    請嚴格遵守以下純 JSON 格式輸出（不要加上 ```json 標籤）：
    ⚠️ 致命錯誤警告：如果內容包含數學公式 (LaTeX) 或任何反斜線，請務必進行 JSON 跳脫！例如數學的 \\pi 必須寫成 \\\\pi，分數 \\frac 必須寫成 \\\\frac，否則系統會崩潰！

    {{
        "concept_explanation": "此處填入 Markdown 格式的深度解析",
        "practice_questions": [
            {{
                "question": "練習題 1 題目",
                "options": ["選項A", "選項B", "選項C", "選項D"],
                "answer": "正確選項的完整內容",
                "explanation": "為什麼這題答案是這個"
            }},
            // ... 練習題 2 與 3
        ]
    }}
    """

    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            config=types.GenerateContentConfig(temperature=0.4),
            contents=[prompt],
        )
        if response.text:
            result_text = response.text.strip()
            result_text = result_text.replace("```json", "").replace("```", "").strip()

        #! 確保解析成功
        try:
            analysis_data = json.loads(result_text)
        except json.JSONDecodeError:
            print("⚠️ 發現 Invalid escape，啟動 Python 暴力修復...")
            #! 將單一反斜線替換為雙反斜線，並保留正確的換行(\n)與雙引號(\")
            cleaned_text = result_text.replace("\\", "\\\\").replace("\\\\n", "\\n").replace('\\\\"', '\\"')
            analysis_data = json.loads(cleaned_text)
            print("✅ JSON 自動修復成功！")
        return analysis_data

    except Exception as e:
        print(f"Deep Analysis API Error: {e}")
        return None
