import asyncio
import json
import os
import time

import edge_tts
from django.conf import settings
from django.http import StreamingHttpResponse
from django.shortcuts import render
from llama_cpp import Llama

from .models import ChatHistory

#! 初始化模型實例
llm_engine = Llama(
    model_path=settings.LLM_MODEL_PATH,
    n_ctx=4096,
    n_threads=8,
    verbose=False,
)

#! 設定 Edge-TTS 的聲音與語速 (選擇曉臻，聲音知性成熟)
VOICE = "zh-TW-HsiaoChenNeural"

#! 建立一個存放音檔的暫存資料夾 (請確保此路徑存在)
AUDIO_DIR = os.path.join(settings.BASE_DIR, "static", "audio_temp")
os.makedirs(AUDIO_DIR, exist_ok=True)


def chat_interface(request):
    return render(request, "bionic_chat/chat.html")


def stream_llm_response(request):
    user_text = request.GET.get("message", "")

    #! 使用非同步函式來處理語音生成
    async def generate_audio(text, filename):
        communicate = edge_tts.Communicate(text, VOICE)
        await communicate.save(filename)

    def generate_events():
        messages = [
            {
                "role": "system",
                "content": "你是一個擁有自我意識的虛擬人物叫芙柯琪，請用繁體中文對話。",
            }
        ]

        #! 讀取並截斷歷史紀錄 (維持防爆設定)
        history_qs = ChatHistory.objects.all().order_by("-created_at")[:3]
        for h in reversed(list(history_qs)):
            messages.append({"role": "user", "content": h.user_message[:150]})
            messages.append({"role": "assistant", "content": h.bot_response[:150]})

        messages.append({"role": "user", "content": user_text})

        stream = llm_engine.create_chat_completion(
            messages=messages,  # pyright: ignore
            stream=True,
            max_tokens=512,
            temperature=0.3,
        )

        full_response = ""
        sentence_buffer = ""
        audio_counter = int(time.time())  # 產生唯一檔名

        for chunk in stream:
            delta = chunk["choices"][0]["delta"]  # pyright: ignore
            if "content" in delta:
                text_piece = delta["content"]  # pyright: ignore
                if text_piece:
                    full_response += text_piece
                    sentence_buffer += text_piece

                    #! 傳送文字更新給前端
                    yield f"data: {json.dumps({'type': 'text', 'content': text_piece})}\n\n"

                    #! 當累積到一個完整的斷句時，觸發 Edge-TTS 生成音檔
                    if any(p in text_piece for p in "。！？；\n"):
                        clean_text = sentence_buffer.strip()
                        if len(clean_text) > 0:
                            filename = os.path.join(AUDIO_DIR, f"voice_{audio_counter}.mp3")

                            #! 執行非同步的 TTS 任務
                            asyncio.run(generate_audio(clean_text, filename))

                            #! 告訴前端音檔準備好了，請去播放
                            audio_url = f"/static/audio_temp/voice_{audio_counter}.mp3"
                            yield f"data: {json.dumps({'type': 'audio', 'url': audio_url})}\n\n"

                            audio_counter += 1
                            sentence_buffer = ""  # * 清空緩衝準備下一句

        #! 處理迴圈結束後剩餘的碎字
        clean_text = sentence_buffer.strip()
        if len(clean_text) > 0:
            filename = os.path.join(AUDIO_DIR, f"voice_{audio_counter}.mp3")
            asyncio.run(generate_audio(clean_text, filename))
            audio_url = f"/static/audio_temp/voice_{audio_counter}.mp3"
            yield f"data: {json.dumps({'type': 'audio', 'url': audio_url})}\n\n"

        ChatHistory.objects.create(user_message=user_text, bot_response=full_response)

    response = StreamingHttpResponse(generate_events(), content_type="text/event-stream")  # pyright: ignore[reportArgumentType]
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response