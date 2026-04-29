const avatar = document.getElementById('avatar');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const chatHistory = document.getElementById('chat-history');

let isSpeaking = false;
let time = 0;
const audioQueue = []; //* 語音佇列
let isAudioPlaying = false; //* 播放狀態追蹤

// --- 隨機擺動系統變數 ---
let currentSwayZ = 0; //* 當前實際的擺動角度
let targetSwayZ = 0;  //* 隨機產生的目標角度

// --- 互動控制系統變數 ---
const characterLayer = document.getElementById('character-layer');
let currentZoom = 1.0; //* 預設縮放值 100%
let panX = 0;          //* X 軸位移
let panY = 0;          //* Y 軸位移

// 拖拉狀態追蹤
let isDragging = false;
let startX = 0, startY = 0;
let initialDistance = 0; //* 用於手機雙指縮放

// 固定優化後的動態參數
const CONFIG = {
    breathIntensity: 0.5,
    baseScale: 1.0,
    baseAngleZ: 0
};

// 隨機擺動觸發器 (3~5秒觸發一次)
function triggerRandomSway() {
    // 只有在待機（沒說話）時才進行大幅度隨機擺動
    if (!isSpeaking) {
        // 隨機決定要擺動的角度：正負 1.5 度到 2.5 度之間
        const direction = Math.random() > 0.5 ? 1 : -1;
        targetSwayZ = direction * (Math.random() * 1 + 1.5);

        // 擺過去之後，大約 1.5 秒後自然回正，這樣就完成了一次「1~2次的自然擺動」
        setTimeout(() => {
            targetSwayZ = 0;
        }, 1500);
    }

    // 排程下一次觸發時間：隨機 3000ms 到 5000ms (3~5秒)
    const nextTriggerTime = Math.random() * 2000 + 3000;
    setTimeout(triggerRandomSway, nextTriggerTime);
}

// 啟動隨機擺動計時器
triggerRandomSway();

// 渲染循環
function updateAvatar() {
    if (!avatar) return;

    const breathRate = isSpeaking ? 0.015 : 0.008;
    time += breathRate;

    const breathEffect = Math.sin(time) * 0.01 * CONFIG.breathIntensity;

    // 將互動的 currentZoom 乘進去
    const finalScaleY = (CONFIG.baseScale + breathEffect) * currentZoom;
    const finalScaleX = (CONFIG.baseScale - (breathEffect * 0.1)) * currentZoom;

    const talkJitter = isSpeaking ? Math.sin(time * 8) * 0.15 : 0;

    // --- 平滑過渡演算 (Lerp) ---
    // 讓當前角度慢慢逼近目標角度，0.02 代表每次靠近剩下距離的 2%，數值越小動作越柔和
    currentSwayZ += (targetSwayZ - currentSwayZ) * 0.02;

    const finalAngleZ = CONFIG.baseAngleZ + (Math.sin(time * 0.2) * 0.3) + talkJitter + currentSwayZ;

    // 加入 translate(panX, panY) 來實現拖拉移動
    avatar.style.transform = `translate(${panX}px, ${panY}px) scaleX(${finalScaleX}) scaleY(${finalScaleY}) rotateZ(${finalAngleZ}deg)`;

    requestAnimationFrame(updateAvatar);
}
updateAvatar();

// 播放佇列中的下一個音檔
function playNextAudio() {
    if (audioQueue.length === 0) {
        isSpeaking = false; //* 佇列清空停止震動
        isAudioPlaying = false;
        return;
    }

    isAudioPlaying = true;
    isSpeaking = true; //* 開始震動
    const audioUrl = audioQueue.shift();

    const audioPlayer = new Audio(audioUrl);

    audioPlayer.onended = () => {
        playNextAudio();
    };

    audioPlayer.onerror = () => {
        playNextAudio(); //* 錯誤時忽略並繼續
    };

    audioPlayer.play().catch(() => playNextAudio());
}

function startBionicStream(message) {
    const apiUrl = `/bionic_chat/api/stream/?message=${encodeURIComponent(message)}`;
    const eventSource = new EventSource(apiUrl);

    const botMsgDiv = document.createElement('div');
    botMsgDiv.className = 'bot-msg';
    botMsgDiv.textContent = '[Fukechi] ';
    chatHistory.appendChild(botMsgDiv);

    let fullMarkdownText = ""; //* 用來累積完整的 Markdown 字串

    eventSource.onmessage = (e) => {
        const data = JSON.parse(e.data);

        if (data.type === 'text') {
            fullMarkdownText += data.content;

            // 使用 marked.js 解析並以 HTML 渲染，取代原本的 textContent
            botMsgDiv.innerHTML = marked.parse(fullMarkdownText);

            chatHistory.scrollTop = chatHistory.scrollHeight;
        } else if (data.type === 'audio') {
            audioQueue.push(data.url); //* 將接收到的 Media 網址加入佇列
            if (!isAudioPlaying) {
                playNextAudio();
            }
        }
    };

    eventSource.onerror = () => {
        eventSource.close();
    };
}

sendBtn.addEventListener('click', () => {
    const val = userInput.value.trim();
    if (!val) return;

    const userDiv = document.createElement('div');
    userDiv.textContent = `[You] ${val}`;
    chatHistory.appendChild(userDiv);
    userInput.value = '';
    startBionicStream(val);
});

userInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') sendBtn.click(); });

// ==========================================
// 互動控制系統：滑鼠與觸控事件綁定
// ==========================================

// 電腦端：滑鼠滾輪縮放
characterLayer.addEventListener('wheel', (e) => {
    e.preventDefault(); // 防止網頁跟著上下捲動
    const zoomSpeed = 0.05;
    if (e.deltaY < 0) {
        currentZoom += zoomSpeed; // 向上滾放大
    } else {
        currentZoom -= zoomSpeed; // 向下滾縮小
    }
    // 限制縮放範圍 (0.5 倍到 3 倍之間)
    currentZoom = Math.max(0.5, Math.min(currentZoom, 3));
}, { passive: false });

// 電腦端：滑鼠左鍵拖曳
characterLayer.addEventListener('mousedown', (e) => {
    if (e.button !== 0) return; // 只允許左鍵拖曳
    isDragging = true;
    startX = e.clientX - panX;
    startY = e.clientY - panY;
});

window.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    panX = e.clientX - startX;
    panY = e.clientY - startY;
});

window.addEventListener('mouseup', () => {
    isDragging = false;
});

// 手機端：單指拖曳與雙指縮放
characterLayer.addEventListener('touchstart', (e) => {
    if (e.touches.length === 1) {
        // 單指拖曳
        isDragging = true;
        startX = e.touches[0].clientX - panX;
        startY = e.touches[0].clientY - panY;
    } else if (e.touches.length === 2) {
        // 雙指準備縮放：計算初始兩指距離
        isDragging = false; // 縮放時停止拖曳計算
        initialDistance = Math.hypot(
            e.touches[0].clientX - e.touches[1].clientX,
            e.touches[0].clientY - e.touches[1].clientY
        );
    }
}, { passive: false });

characterLayer.addEventListener('touchmove', (e) => {
    e.preventDefault(); // 防止手機畫面滑動

    if (e.touches.length === 1 && isDragging) {
        // 處理單指位移
        panX = e.touches[0].clientX - startX;
        panY = e.touches[0].clientY - startY;
    } else if (e.touches.length === 2) {
        // 處理雙指縮放
        const currentDistance = Math.hypot(
            e.touches[0].clientX - e.touches[1].clientX,
            e.touches[0].clientY - e.touches[1].clientY
        );

        // 根據兩指距離的變化比例來調整縮放 (0.005 是靈敏度係數)
        const diff = currentDistance - initialDistance;
        currentZoom += diff * 0.005;
        currentZoom = Math.max(0.5, Math.min(currentZoom, 3));

        initialDistance = currentDistance; // 更新距離供下一幀計算
    }
}, { passive: false });

characterLayer.addEventListener('touchend', (e) => {
    if (e.touches.length === 0) {
        isDragging = false;
    }
});