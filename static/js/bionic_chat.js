const avatar = document.getElementById('avatar');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const chatHistory = document.getElementById('chat-history');

let isSpeaking = false;
let time = 0;
const audioQueue = []; //* 語音佇列
let isAudioPlaying = false; //* 播放狀態追蹤

// 固定優化後的動態參數
const CONFIG = {
    breathIntensity: 0.5,
    baseScale: 1.0,
    baseAngleZ: 0
};

// 渲染循環
function updateAvatar() {
    if (!avatar) return;

    const breathRate = isSpeaking ? 0.015 : 0.008;
    time += breathRate;

    const breathEffect = Math.sin(time) * 0.01 * CONFIG.breathIntensity;

    const finalScaleY = CONFIG.baseScale + breathEffect;
    const finalScaleX = CONFIG.baseScale - (breathEffect * 0.1);
    const talkJitter = isSpeaking ? Math.sin(time * 8) * 0.15 : 0;
    const finalAngleZ = CONFIG.baseAngleZ + (Math.sin(time * 0.2) * 0.3) + talkJitter;

    avatar.style.transform = `scaleX(${finalScaleX}) scaleY(${finalScaleY}) rotateZ(${finalAngleZ}deg)`;
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
    botMsgDiv.textContent = '[Bionic] ';
    chatHistory.appendChild(botMsgDiv);

    eventSource.onmessage = (e) => {
        const data = JSON.parse(e.data);

        if (data.type === 'text') {
            botMsgDiv.textContent += data.content;
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