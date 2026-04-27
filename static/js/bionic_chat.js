document.getElementById('send-btn').addEventListener('click', () => {
    const inputElement = document.getElementById('user-input');
    const message = inputElement.value.trim(); //* 取得並清理使用者輸入字串

    if (!message) return; //* 避免發送空白訊息

    appendMessage('You', message); //* 將使用者訊息寫入歷史區塊
    inputElement.value = ''; //* 清空輸入框

    startTypingEffect(message); //* 啟動向伺服器請求的流程
});

function appendMessage(sender, text) {
    // 建立新的 DOM 元素來顯示單筆對話
    const historyBox = document.getElementById('chat-history');
    const msgDiv = document.createElement('div');

    msgDiv.textContent = `[${sender}] ${text}`;
    if (sender !== 'You') {
        msgDiv.className = 'bot-msg'; //* 為仿生人設定專屬樣式類別
    }

    historyBox.appendChild(msgDiv);
    historyBox.scrollTop = historyBox.scrollHeight; //* 自動捲動到最新訊息
    return msgDiv; //* 回傳節點以便後續追加文字
}

function startTypingEffect(userMessage) {
    // 透過 SSE 連線接收後端 LLM 產生的文字串流
    const encodedMsg = encodeURIComponent(userMessage);
    const eventSource = new EventSource(`/bionic_chat/api/stream/?message=${encodedMsg}`); //* 發起請求

    const botMsgDiv = appendMessage('Bionic', ''); //* 先建立一個空白的對話列

    eventSource.onmessage = function (event) {
        // 每次收到伺服器傳來的一個字，就接在現有文字後方
        const data = JSON.parse(event.data);
        botMsgDiv.textContent += data.text; //* 實現打字機的動態跳動效果

        const historyBox = document.getElementById('chat-history');
        historyBox.scrollTop = historyBox.scrollHeight; //* 確保打字過程中畫面跟著捲動
    };

    eventSource.onerror = function () {
        // 當模型生成結束或遇到錯誤時，關閉連線以節省資源
        eventSource.close(); //* 中斷 SSE 連線
    };
}