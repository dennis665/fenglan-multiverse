const avatar = document.getElementById('avatar');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const chatHistory = document.getElementById('chat-history');
const subLangSelect = document.getElementById('sub-lang');
const voiceLangSelect = document.getElementById('voice-lang');
const volumeSlider = document.getElementById('volume-slider');
const loadingStatus = document.getElementById('loading-status');

// ==========================================
// 系統狀態防呆控管 (Loading State)
// ==========================================
function setLoading(isLoading) {
    if (loadingStatus) {
        loadingStatus.style.display = isLoading ? 'block' : 'none';
    }
    sendBtn.disabled = isLoading;
    userInput.disabled = isLoading;
    subLangSelect.disabled = isLoading;

    const replayBtns = document.querySelectorAll('.replay-btn');
    replayBtns.forEach(btn => btn.disabled = isLoading);
}

// ==========================================
// 音量記憶與控制系統
// ==========================================
let currentVolume = localStorage.getItem('bionic_volume') ? parseFloat(localStorage.getItem('bionic_volume')) : 1.0;
if (volumeSlider) {
    volumeSlider.value = currentVolume;
    volumeSlider.addEventListener('input', (e) => {
        currentVolume = e.target.value;
        localStorage.setItem('bionic_volume', currentVolume);
        if (currentAudioPlayer) {
            currentAudioPlayer.volume = currentVolume;
        }
    });
}

// ==========================================
// 動態與語音播放系統
// ==========================================
let isSpeaking = false;
let time = 0;
const audioQueue = [];
let isAudioPlaying = false;
let currentAudioPlayer = null;
let activeEventSource = null;

let currentSwayZ = 0, targetSwayZ = 0;
const characterLayer = document.getElementById('character-layer');
let currentZoom = 1.0, panX = 0, panY = 0;
let isDragging = false, startX = 0, startY = 0, initialDistance = 0;
const CONFIG = { breathIntensity: 0.5, baseScale: 1.0, baseAngleZ: 0 };

function triggerRandomSway() {
    if (!isSpeaking) {
        targetSwayZ = (Math.random() > 0.5 ? 1 : -1) * (Math.random() * 1 + 1.5);
        setTimeout(() => { targetSwayZ = 0; }, 1500);
    }
    setTimeout(triggerRandomSway, Math.random() * 2000 + 3000);
}
triggerRandomSway();

function updateAvatar() {
    if (!avatar) return;
    time += isSpeaking ? 0.015 : 0.008;
    const breathEffect = Math.sin(time) * 0.01 * CONFIG.breathIntensity;
    const finalScaleY = (CONFIG.baseScale + breathEffect) * currentZoom;
    const finalScaleX = (CONFIG.baseScale - (breathEffect * 0.1)) * currentZoom;
    currentSwayZ += (targetSwayZ - currentSwayZ) * 0.02;
    const finalAngleZ = CONFIG.baseAngleZ + (Math.sin(time * 0.2) * 0.3) + (isSpeaking ? Math.sin(time * 8) * 0.15 : 0) + currentSwayZ;

    avatar.style.transform = `translate(${panX}px, ${panY}px) scaleX(${finalScaleX}) scaleY(${finalScaleY}) rotateZ(${finalAngleZ}deg)`;
    requestAnimationFrame(updateAvatar);
}
updateAvatar();

function forceStopAudio() {
    if (activeEventSource) {
        activeEventSource.close();
        activeEventSource = null;
    }

    if (currentAudioPlayer) {
        currentAudioPlayer.pause();
        currentAudioPlayer.currentTime = 0;
        currentAudioPlayer.removeAttribute('src');
        currentAudioPlayer.load();
        currentAudioPlayer = null;
    }

    audioQueue.length = 0;
    isAudioPlaying = false;
    isSpeaking = false;
}

function playNextAudio() {
    if (audioQueue.length === 0) {
        isSpeaking = false; 
        isAudioPlaying = false;
        currentAudioPlayer = null;
        return;
    }

    isAudioPlaying = true;
    const audioUrl = audioQueue.shift();

    currentAudioPlayer = new Audio(audioUrl);
    currentAudioPlayer.volume = currentVolume;

    currentAudioPlayer.play().then(() => {
        isSpeaking = true;
    }).catch((e) => {
        playNextAudio();
    });

    currentAudioPlayer.onended = () => {
        playNextAudio();
    };

    currentAudioPlayer.onerror = (e) => {
        playNextAudio();
    };
}

// ==========================================
// 訊息快取與獨立重播系統
// ==========================================
const messageDatabase = [];

subLangSelect.addEventListener('change', async () => {
    const targetSubLang = subLangSelect.value;
    setLoading(true);

    try {
        for (let i = 0; i < messageDatabase.length; i++) {
            const msgData = messageDatabase[i];
            let textToDisplay = "";

            if (msgData.translations[targetSubLang]) {
                textToDisplay = msgData.translations[targetSubLang];
            } else {
                const response = await fetch(`/bionic_chat/api/translate/?text=${encodeURIComponent(msgData.originalText)}&target_lang=${targetSubLang}`);
                const data = await response.json();
                textToDisplay = data.translated_text;
                msgData.translations[targetSubLang] = textToDisplay;
            }

            const msgDiv = document.getElementById(`msg-text-${i}`);
            if (msgDiv) {
                msgDiv.innerHTML = marked.parse(textToDisplay);
            }
        }
        chatHistory.scrollTop = chatHistory.scrollHeight;
    } catch (e) {
        // 忽略錯誤，防止程式中斷
    } finally {
        setLoading(false);
    }
});

async function handleReplay(msgIndex) {
    forceStopAudio();
    setLoading(true);

    const msgData = messageDatabase[msgIndex];
    const targetVoiceLang = voiceLangSelect.value;

    try {
        let textForVoice = msgData.translations[targetVoiceLang];

        if (!textForVoice) {
            const response = await fetch(`/bionic_chat/api/translate/?text=${encodeURIComponent(msgData.originalText)}&target_lang=${targetVoiceLang}`);
            const data = await response.json();
            if (data.error) throw new Error("API Error");
            textForVoice = data.translated_text;
            msgData.translations[targetVoiceLang] = textForVoice;
        }

        let audioUrls = msgData.audios[targetVoiceLang];

        if (!audioUrls || audioUrls.length === 0) {
            const response = await fetch(`/bionic_chat/api/tts/?text=${encodeURIComponent(textForVoice)}&voice_lang=${targetVoiceLang}`);
            const data = await response.json();
            if (data.error) throw new Error("API Error");

            audioUrls = [data.audio_url];
            msgData.audios[targetVoiceLang] = audioUrls;
        }

        if (audioUrls && audioUrls.length > 0) {
            audioUrls.forEach(url => audioQueue.push(url));
            if (!isAudioPlaying) {
                playNextAudio();
            }
        }

    } catch (e) {
        alert("語音生成發生錯誤，請稍後再試或檢查網路連線。");
    } finally {
        setLoading(false);
    }
}

// ==========================================
// 核心對話串流與接收
// ==========================================
function startBionicStream(message) {
    forceStopAudio();
    setLoading(true);

    const subLang = subLangSelect.value;
    const voiceLang = voiceLangSelect.value;

    const apiUrl = `/bionic_chat/api/stream/?message=${encodeURIComponent(message)}&sub_lang=${subLang}&voice_lang=${voiceLang}`;
    activeEventSource = new EventSource(apiUrl);

    const msgIndex = messageDatabase.length;
    const msgData = { originalText: "", translations: {}, audios: {} };
    messageDatabase.push(msgData);

    const wrapperDiv = document.createElement('div');
    wrapperDiv.className = 'msg-wrapper';

    const replayBtn = document.createElement('button');
    replayBtn.className = 'replay-btn';
    replayBtn.innerHTML = '▶';
    replayBtn.title = '依當前設定重新播放語音';
    replayBtn.disabled = true;
    replayBtn.onclick = () => handleReplay(msgIndex); 

    const botMsgDiv = document.createElement('div');
    botMsgDiv.className = 'bot-msg';
    botMsgDiv.id = `msg-text-${msgIndex}`;

    wrapperDiv.appendChild(replayBtn);
    wrapperDiv.appendChild(botMsgDiv);
    chatHistory.appendChild(wrapperDiv);

    let fullSubText = "";

    activeEventSource.onmessage = (e) => {
        const data = JSON.parse(e.data);

        if (data.type === 'text') {
            fullSubText += data.content;
            if (subLang !== 'zh-TW') {
                msgData.translations[subLang] = fullSubText;
            }
            botMsgDiv.innerHTML = marked.parse(fullSubText);
            chatHistory.scrollTop = chatHistory.scrollHeight;

        } else if (data.type === 'original_text') {
            msgData.originalText += data.content + " ";

            if (subLang === 'zh-TW') {
                msgData.translations['zh-TW'] = msgData.originalText;
            }

        } else if (data.type === 'audio') {
            if (!msgData.audios[voiceLang]) {
                msgData.audios[voiceLang] = [];
            }
            msgData.audios[voiceLang].push(data.url);

            audioQueue.push(data.url); 
            if (!isAudioPlaying) {
                playNextAudio();
            }
        }
    };

    activeEventSource.onerror = () => {
        if (activeEventSource) {
            activeEventSource.close();
            activeEventSource = null;
        }
        setLoading(false); 
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
characterLayer.addEventListener('wheel', (e) => {
    e.preventDefault();
    currentZoom += e.deltaY < 0 ? 0.05 : -0.05; 
    currentZoom = Math.max(0.5, Math.min(currentZoom, 3));
}, { passive: false });

characterLayer.addEventListener('mousedown', (e) => {
    if (e.button !== 0) return;
    isDragging = true; startX = e.clientX - panX; startY = e.clientY - panY;
});

window.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    panX = e.clientX - startX; panY = e.clientY - startY;
});

window.addEventListener('mouseup', () => { isDragging = false; });

characterLayer.addEventListener('touchstart', (e) => {
    if (e.touches.length === 1) {
        isDragging = true; startX = e.touches[0].clientX - panX; startY = e.touches[0].clientY - panY;
    } else if (e.touches.length === 2) {
        isDragging = false;
        initialDistance = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
    }
}, { passive: false });

characterLayer.addEventListener('touchmove', (e) => {
    e.preventDefault(); 
    if (e.touches.length === 1 && isDragging) {
        panX = e.touches[0].clientX - startX; panY = e.touches[0].clientY - startY;
    } else if (e.touches.length === 2) {
        const currentDistance = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
        currentZoom += (currentDistance - initialDistance) * 0.005;
        currentZoom = Math.max(0.5, Math.min(currentZoom, 3));
        initialDistance = currentDistance; 
    }
}, { passive: false });

characterLayer.addEventListener('touchend', (e) => { if (e.touches.length === 0) isDragging = false; });