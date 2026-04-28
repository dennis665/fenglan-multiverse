#! static/js/bionic_chat.js

const avatar = document.getElementById('avatar');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const chatHistory = document.getElementById('chat-history');
const dialogueSystem = document.getElementById('dialogue-system');

let isSpeaking = false;
let time = 0;
let sentenceBuffer = "";
let availableVoices = [];

// 固定優化後的動態參數
const CONFIG = {
    breathIntensity: 0.5,
    baseScale: 1.0,
    baseAngleZ: 0,
    pitch: 1.1,
    rate: 0.9
};

const synth = window.speechSynthesis;

function loadVoices() { availableVoices = synth.getVoices(); }
if (speechSynthesis.onvoiceschanged !== undefined) {
    speechSynthesis.onvoiceschanged = loadVoices;
}
loadVoices();

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

function playVoice(text) {
    if (!text) return;
    const msg = new SpeechSynthesisUtterance(text);
    const voice = availableVoices.find(v => v.lang.includes('zh-TW'));
    if (voice) msg.voice = voice;

    msg.pitch = CONFIG.pitch;
    msg.rate = CONFIG.rate;

    msg.onstart = () => { isSpeaking = true; };
    msg.onend = () => { if (!synth.speaking) isSpeaking = false; };
    synth.speak(msg);
}

function startBionicStream(message) {
    // 確保路徑包含 bionic_chat
    const apiUrl = `/bionic_chat/api/stream/?message=${encodeURIComponent(message)}`;
    const eventSource = new EventSource(apiUrl);

    const botMsgDiv = document.createElement('div');
    botMsgDiv.className = 'bot-msg';
    botMsgDiv.textContent = '[Bionic] ';
    chatHistory.appendChild(botMsgDiv);

    sentenceBuffer = "";

    eventSource.onmessage = (e) => {
        const data = JSON.parse(e.data);
        botMsgDiv.textContent += data.text;
        chatHistory.scrollTop = chatHistory.scrollHeight;

        sentenceBuffer += data.text;
        if (/[。！？；\n]/.test(data.text) || sentenceBuffer.length > 25) {
            playVoice(sentenceBuffer);
            sentenceBuffer = "";
        }
    };

    eventSource.onerror = () => {
        if (sentenceBuffer) playVoice(sentenceBuffer);
        eventSource.close();
        isSpeaking = false;
    };
}

sendBtn.addEventListener('click', () => {
    const val = userInput.value.trim();
    if (!val) return;
    synth.speak(new SpeechSynthesisUtterance('')); // 解鎖語音
    const userDiv = document.createElement('div');
    userDiv.textContent = `[You] ${val}`;
    chatHistory.appendChild(userDiv);
    userInput.value = '';
    startBionicStream(val);
});

userInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') sendBtn.click(); });