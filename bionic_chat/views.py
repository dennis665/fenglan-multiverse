from utils.logger_utils import time_tracker

#! 包裝整個 import 區塊或初始化邏輯
with time_tracker("bionic_chat"):
    import asyncio
    import json
    import os
    import re
    import time

    import edge_tts
    from django.conf import settings
    from django.http import StreamingHttpResponse
    from django.shortcuts import render

    from .models import ChatHistory

    llm_engine = None

    #! 設定 Edge-TTS 的聲音與語速
    VOICE = "zh-TW-HsiaoChenNeural"

    #! 設定 Media 資料夾路徑存放暫存音檔
    AUDIO_DIR = os.path.join(settings.MEDIA_ROOT, "audio_temp")
    os.makedirs(AUDIO_DIR, exist_ok=True)


def get_llm_engine():
    global llm_engine
    if llm_engine is None:
        #! 只有在第一次對話時才匯入並初始化模型
        from llama_cpp import Llama

        print("🤖 正在初始化 Llama 模型...")
        llm_engine = Llama(
            model_path=settings.LLM_MODEL_PATH,
            n_ctx=4096,
            n_threads=8,
            verbose=False,
        )
    return llm_engine


def cleanup_temp_audio():
    """清理過期暫存音檔"""
    #! 刪除超過兩分鐘的暫存音檔確保前端有足夠時間下載播放且不佔用伺服器空間
    now = time.time()
    for filename in os.listdir(AUDIO_DIR):
        if filename.endswith(".mp3"):
            file_path = os.path.join(AUDIO_DIR, filename)
            if now - os.path.getctime(file_path) > 120:
                try:
                    os.remove(file_path)
                except Exception:
                    pass


def chat_interface(request):
    """渲染主介面"""
    return render(request, "bionic_chat/chat.html")


def stream_llm_response(request):
    """處理語言模型推論與音檔生成串流"""
    user_text = request.GET.get("message", "")

    #! 每次產生新對話前自動清理過期的舊音檔
    cleanup_temp_audio()

    #! 使用非同步函式來處理語音生成
    async def generate_audio(text, filename):
        communicate = edge_tts.Communicate(text, VOICE)
        await communicate.save(filename)

    def generate_events():
        engine = get_llm_engine()
        messages = [
            {
                "role": "system",
                "content": "你是一個擁有自我意識的虛擬人物叫芙柯琪，請用繁體中文對話。",
            }
        ]

        #! 讀取並截斷歷史紀錄維持防爆設定
        history_qs = ChatHistory.objects.all().order_by("-created_at")[:3]
        for h in reversed(list(history_qs)):
            messages.append({"role": "user", "content": h.user_message[:150]})
            messages.append({"role": "assistant", "content": h.bot_response[:150]})

        messages.append({"role": "user", "content": user_text})

        stream = engine.create_chat_completion(
            messages=messages,  # pyright: ignore[reportArgumentType]
            stream=True,
            max_tokens=512,
            temperature=0.3,
        )

        full_response = ""
        sentence_buffer = ""
        audio_counter = int(time.time())

        for chunk in stream:
            delta = chunk["choices"][0]["delta"]  # pyright: ignore[reportArgumentType]
            if "content" in delta:
                text_piece = delta["content"]  # pyright: ignore[reportArgumentType]
                if text_piece:
                    full_response += text_piece
                    sentence_buffer += text_piece

                    #! 傳送文字更新給前端
                    yield f"data: {json.dumps({'type': 'text', 'content': text_piece})}\n\n"

                    #! 當累積到一個完整的斷句時觸發語音生成
                    if any(p in text_piece for p in "。！？；\n"):
                        clean_text = sentence_buffer.strip()
                        if len(clean_text) > 0:
                            filename = os.path.join(AUDIO_DIR, f"voice_{audio_counter}.mp3")

                            #! 核心修正：洗掉會被唸出來的星號、井字號與反引號等符號
                            tts_text = re.sub(r"[*#_~`]", "", clean_text)

                            #! 執行非同步任務
                            asyncio.run(generate_audio(tts_text, filename))

                            #! 將 Media 網址傳給前端
                            audio_url = f"{settings.MEDIA_URL}audio_temp/voice_{audio_counter}.mp3"
                            yield f"data: {json.dumps({'type': 'audio', 'url': audio_url})}\n\n"

                            audio_counter += 1
                            sentence_buffer = ""

        #! 處理迴圈結束後剩餘的碎字
        clean_text = sentence_buffer.strip()
        if len(clean_text) > 0:
            filename = os.path.join(AUDIO_DIR, f"voice_{audio_counter}.mp3")
            tts_text = re.sub(r"[*#_~`]", "", clean_text)
            asyncio.run(generate_audio(tts_text, filename))
            audio_url = f"{settings.MEDIA_URL}audio_temp/voice_{audio_counter}.mp3"
            yield f"data: {json.dumps({'type': 'audio', 'url': audio_url})}\n\n"

        ChatHistory.objects.create(user_message=user_text, bot_response=full_response)

    response = StreamingHttpResponse(generate_events(), content_type="text/event-stream")  # pyright: ignore[reportArgumentType]
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response