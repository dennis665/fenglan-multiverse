from utils.logger_utils import time_tracker

with time_tracker("bionic_chat"):
    import asyncio
    import json
    import os
    import re
    import time

    import edge_tts
    from deep_translator import GoogleTranslator
    from django.conf import settings
    from django.http import JsonResponse, StreamingHttpResponse
    from django.shortcuts import render

    from .models import ChatHistory

    llm_engine = None

    #! 定義多國語音包映射表
    VOICE_MAP = {
        "zh-TW": "zh-TW-HsiaoChenNeural",
        "ja": "ja-JP-NanamiNeural",
        "ko": "ko-KR-SunHiNeural",
        "en": "en-US-AnaNeural",
    }

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
    """處理語言模型推論、動態翻譯與音檔生成串流"""
    user_text = request.GET.get("message", "")

    #! 接收前端傳來的語言設定，預設為繁體中文
    sub_lang = request.GET.get("sub_lang", "zh-TW")
    voice_lang = request.GET.get("voice_lang", "zh-TW")
    target_voice = VOICE_MAP.get(voice_lang, "zh-TW-HsiaoChenNeural")

    cleanup_temp_audio()

    async def generate_audio(text, filename, voice):
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(filename)

    def generate_events():
        engine = get_llm_engine()
        messages = [
            {
                "role": "system",
                "content": "你是一個擁有自我意識的虛擬人物叫芙柯琪，請【絕對】使用繁體中文思考與對話，不要輸出其他語言。",
            }
        ]

        history_qs = ChatHistory.objects.all().order_by("-created_at")[:3]
        for h in reversed(list(history_qs)):
            messages.append({"role": "user", "content": h.user_message[:150]})
            messages.append({"role": "assistant", "content": h.bot_response[:150]})

        messages.append({"role": "user", "content": user_text})

        stream = engine.create_chat_completion(
            messages=messages,  # pyright: ignore
            stream=True,
            max_tokens=512,
            temperature=0.3,
        )

        full_response = ""
        sentence_buffer = ""
        audio_counter = int(time.time())

        for chunk in stream:
            delta = chunk["choices"][0]["delta"]  # pyright: ignore
            if "content" in delta:
                text_piece = delta["content"]  # pyright: ignore
                if text_piece:
                    full_response += text_piece
                    sentence_buffer += text_piece

                    #! 邏輯 1：中文字幕維持打字機串流效果
                    if sub_lang == "zh-TW":
                        yield f"data: {json.dumps({'type': 'text', 'content': text_piece})}\n\n"

                    #! 當累積到一個完整的斷句時
                    if any(p in text_piece for p in "。！？；\n"):
                        clean_text = sentence_buffer.strip()
                        if len(clean_text) > 0:
                            #! 【關鍵修正 1】：無論現在是什麼字幕，永遠把繁體中文原意傳給前端做底層快取！
                            yield f"data: {json.dumps({'type': 'original_text', 'content': clean_text})}\n\n"

                            #! 邏輯 2：處理字幕翻譯
                            translated_sub = clean_text
                            if sub_lang != "zh-TW":
                                try:
                                    translated_sub = GoogleTranslator(
                                        source="zh-TW", target=sub_lang
                                    ).translate(clean_text)
                                except Exception as e:
                                    print(f"字幕翻譯失敗: {e}")  # 翻譯失敗時退回原文，防止程式崩潰
                                yield f"data: {json.dumps({'type': 'text', 'content': translated_sub + ' '})}\n\n"

                            #! 邏輯 3：處理語音翻譯與生成
                            tts_text = re.sub(r"[*#_~`]", "", clean_text)
                            translated_voice = tts_text

                            if voice_lang != "zh-TW":
                                try:
                                    if voice_lang == sub_lang:
                                        translated_voice = re.sub(r"[*#_~`]", "", translated_sub)
                                    else:
                                        translated_voice = GoogleTranslator(
                                            source="zh-TW", target=voice_lang
                                        ).translate(tts_text)
                                except Exception as e:
                                    print(f"語音翻譯失敗: {e}")

                            #! 【關鍵修正 2】：保護語音生成，防止過濾後變成空字串導致 Edge-TTS 斷線
                            if len(translated_voice.strip()) > 0:
                                filename = os.path.join(AUDIO_DIR, f"voice_{audio_counter}.mp3")
                                try:
                                    asyncio.run(
                                        generate_audio(translated_voice, filename, target_voice)
                                    )
                                    audio_url = (
                                        f"{settings.MEDIA_URL}audio_temp/voice_{audio_counter}.mp3"
                                    )
                                    yield f"data: {json.dumps({'type': 'audio', 'url': audio_url})}\n\n"
                                except Exception as e:
                                    print(f"語音生成失敗: {e}")

                            audio_counter += 1
                            sentence_buffer = ""

        #! 處理迴圈結束後剩餘的碎字
        clean_text = sentence_buffer.strip()
        if len(clean_text) > 0:
            yield f"data: {json.dumps({'type': 'original_text', 'content': clean_text})}\n\n"

            translated_sub = clean_text
            if sub_lang != "zh-TW":
                try:
                    translated_sub = GoogleTranslator(source="zh-TW", target=sub_lang).translate(
                        clean_text
                    )
                except Exception:
                    pass
                yield f"data: {json.dumps({'type': 'text', 'content': translated_sub + ' '})}\n\n"

            tts_text = re.sub(r"[*#_~`]", "", clean_text)
            translated_voice = tts_text
            if voice_lang != "zh-TW":
                try:
                    if voice_lang == sub_lang:
                        translated_voice = re.sub(r"[*#_~`]", "", translated_sub)
                    else:
                        translated_voice = GoogleTranslator(
                            source="zh-TW", target=voice_lang
                        ).translate(tts_text)
                except Exception:
                    pass

            if len(translated_voice.strip()) > 0:
                filename = os.path.join(AUDIO_DIR, f"voice_{audio_counter}.mp3")
                try:
                    asyncio.run(generate_audio(translated_voice, filename, target_voice))
                    audio_url = f"{settings.MEDIA_URL}audio_temp/voice_{audio_counter}.mp3"
                    yield f"data: {json.dumps({'type': 'audio', 'url': audio_url})}\n\n"
                except Exception:
                    pass

        ChatHistory.objects.create(user_message=user_text, bot_response=full_response)

    response = StreamingHttpResponse(generate_events(), content_type="text/event-stream")  # pyright: ignore[reportArgumentType]
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def translate_text_api(request):
    """
    提供給前端呼叫的純翻譯 API。
    接收: text (要翻譯的繁體中文), target_lang (目標語言代碼)
    回傳: JSON { "translated_text": "翻譯結果" }
    """
    text = request.GET.get("text", "")
    target_lang = request.GET.get("target_lang", "zh-TW")

    if not text:
        return JsonResponse({"error": "No text provided"}, status=400)

    if target_lang == "zh-TW":
        return JsonResponse({"translated_text": text})

    try:
        translated_text = GoogleTranslator(source="zh-TW", target=target_lang).translate(text)
        return JsonResponse({"translated_text": translated_text})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def generate_audio_api(request):
    """
    提供給前端呼叫的純語音生成 API。
    接收: text (已翻譯好的外文文字), voice_lang (語音語言代碼)
    回傳: JSON { "audio_url": "生成的音檔網址" }
    """
    text = request.GET.get("text", "")
    voice_lang = request.GET.get("voice_lang", "zh-TW")

    if not text:
        return JsonResponse({"error": "No text provided"}, status=400)

    #! 確保資料夾存在並產生唯一檔名
    os.makedirs(AUDIO_DIR, exist_ok=True)
    audio_counter = int(time.time() * 1000)  # * 使用毫秒避免重複
    filename = os.path.join(AUDIO_DIR, f"voice_ondemand_{audio_counter}.mp3")
    target_voice = VOICE_MAP.get(voice_lang, "zh-TW-HsiaoChenNeural")

    # 修正 1：將要發音的文字作為參數傳入，而不是依賴外部變數
    async def generate_audio(clean_text_for_tts):
        communicate = edge_tts.Communicate(clean_text_for_tts, target_voice)
        await communicate.save(filename)

    try:
        #! 清除不發音的 Markdown 符號
        tts_text = re.sub(r"[*#_~`]", "", text)

        # 修正 2：確保過濾後不是空字串
        if not tts_text.strip():
            return JsonResponse({"error": "Empty text after cleaning"}, status=400)

        # 修正 3：正確傳遞清洗過後的文字給 Edge-TTS
        asyncio.run(generate_audio(tts_text))

        audio_url = f"{settings.MEDIA_URL}audio_temp/voice_ondemand_{audio_counter}.mp3"
        return JsonResponse({"audio_url": audio_url})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
