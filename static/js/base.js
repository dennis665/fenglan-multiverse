async function sendToAI(csrfToken) {
    const input = document.getElementById('ai-user-input');
    const chatBody = document.getElementById('ai-chat-body');
    const message = input.value.trim();
    if (!message) return;

    chatBody.innerHTML += `<div class="msg msg-user">${message}</div>`;
    input.value = '';
    chatBody.scrollTop = chatBody.scrollHeight;

    const loadingId = 'ai-loading-' + Date.now();
    chatBody.insertAdjacentHTML('beforeend', `<div id="${loadingId}" class="msg msg-ai"><div class="typing-loader"><span></span><span></span><span></span></div></div>`);
    chatBody.scrollTop = chatBody.scrollHeight;

    try {
        const response = await fetch('/ai-chat/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': csrfToken // 改由參數傳入
            },
            body: `message=${encodeURIComponent(message)}`
        });
        const data = await response.json();
        const loadingElement = document.getElementById(loadingId);
        if (loadingElement) loadingElement.remove();

        if (data.reply) {
            const formattedReply = marked.parse(data.reply);
            chatBody.innerHTML += `<div class="msg msg-ai">${formattedReply}</div>`;
        } else {
            // 錯誤訊息套用翻譯
            chatBody.innerHTML += `<div class="msg msg-ai text-danger">${CSI_CONFIG.trans.systemError}</div>`;
        }
    } catch (error) {
        // 連線訊息套用翻譯
        chatBody.innerHTML += `<div class="msg msg-ai text-danger">${CSI_CONFIG.trans.netError}</div>`;
    }
    chatBody.scrollTop = chatBody.scrollHeight;
}

function toggleAIChat() {
    const container = document.getElementById('ai-chat-container');
    container.style.display = (container.style.display === 'none' || container.style.display === '') ? 'flex' : 'none';
}

function handleChatKey(e) {
    if (e.key === 'Enter') sendToAI(CSI_CONFIG.csrfToken);
}

function createParticles() {
    const container = document.getElementById('bg-animation');
    const particleCount = 20;
    const icons = ['🍁', '🍂', '❄', '❅'];
    for (let i = 0; i < particleCount; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.innerText = icons[Math.floor(Math.random() * icons.length)];
        particle.style.left = Math.random() * 100 + 'vw';
        particle.style.animationDuration = (Math.random() * 15 + 10) + 's';
        particle.style.animationDelay = (Math.random() * 20) + 's';
        particle.style.fontSize = (Math.random() * 10 + 15) + 'px';
        container.appendChild(particle);
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    createParticles();
});