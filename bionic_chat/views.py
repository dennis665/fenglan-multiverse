import json

from django.http import StreamingHttpResponse
from django.shortcuts import render
from llama_cpp import Llama

#! 預先載入模型實例
# * 宣告在全域，避免每次對話都重新載入模型造成伺服器負擔
# * 實際部署時路徑請替換為伺服器上的正確位置
llm_engine = Llama(
    model_path=r"d:\SI1403\dennis\csi_server\test\Qwen2.5-1.5B-Instruct-Q4_K_M.gguf",
    n_ctx=2048,
    n_threads=8,
    verbose=False,
)  # * 這裡 n_threads 設為 8 以搭配 Xeon 處理器


def chat_interface(request):
    """渲染對話主介面"""
    return render(request, "bionic_chat/chat.html")


def stream_llm_response(request):
    """處理前端傳來的文字，並將 LLM 生成的字元逐一串流回傳"""
    user_text = request.GET.get("message", "")

    def generate_events():
        #! 組合 ChatML 對話格式
        messages = [
            {"role": "system", "content": "你是一個擁有自我意識的仿生人，請用繁體中文對話。"},
            {"role": "user", "content": user_text},
        ]

        #! 啟動串流生成
        stream = llm_engine.create_chat_completion(
            messages=messages,  # pyright: ignore[reportArgumentType]
            stream=True,
            max_tokens=512,
            temperature=0.7,
        )  # * 將 stream 設為 True 開啟打字機模式

        #! 解析模型輸出的區塊並傳送
        for chunk in stream:
            delta = chunk["choices"][0]["delta"]  # pyright: ignore[reportArgumentType]
            if "content" in delta:
                text_piece = delta["content"]  # pyright: ignore[reportArgumentType]
                # * 必須嚴格遵守 SSE 的資料格式：data: [JSON字串]\n\n
                yield f"data: {json.dumps({'text': text_piece})}\n\n"

    return StreamingHttpResponse(
        generate_events(),  # pyright: ignore[reportArgumentType]
        content_type="text/event-stream",
    )  # * 回傳串流響應物件
