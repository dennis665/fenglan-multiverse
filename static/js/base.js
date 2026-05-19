// --- AI 客服對話邏輯 ---
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
                'X-CSRFToken': csrfToken
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
            chatBody.innerHTML += `<div class="msg msg-ai text-danger">${CSI_CONFIG.trans.systemError}</div>`;
        }
    } catch (error) {
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

// --- 背景動畫邏輯 ---
function createParticles() {
    const container = document.getElementById('bg-animation');
    if (!container) return; // 防呆
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

// ==========================================
// 長按 3 秒密碼鎖邏輯
// ==========================================
function initSecretGameTrigger() {
    const launcher = document.getElementById('ai-chat-launcher');
    if (!launcher) return;

    let pressTimer;
    let isLongPress = false;

    // 開始按壓
    const startPress = (e) => {
        isLongPress = false;

        // 啟動 3 秒計時器
        pressTimer = setTimeout(() => {
            isLongPress = true; // 標記為長按，避免觸發 click
            const pwd = prompt("請輸入存取密碼");

            // 這裡設定您的專屬密碼
            if (pwd === "666") {
                window.location.href = CSI_CONFIG.lobbyUrl;
            } else if (pwd !== null) {
                alert("密碼錯誤，存取被拒。");
            }
        }, 3000); // 3000 毫秒 = 3 秒
    };

    // 取消按壓
    const cancelPress = () => {
        clearTimeout(pressTimer);
    };

    // 處理點擊 (區分單點與長按)
    const handleClick = (e) => {
        if (isLongPress) {
            // 如果剛才是長按，就阻止預設行為，不要打開客服視窗
            e.preventDefault();
        } else {
            // 如果只是短點擊，就打開 AI 客服視窗
            toggleAIChat();
        }
    };

    // 綁定事件：支援滑鼠與手機觸控
    launcher.addEventListener('mousedown', startPress);
    launcher.addEventListener('mouseup', cancelPress);
    launcher.addEventListener('mouseleave', cancelPress);

    // 手機觸控事件
    launcher.addEventListener('touchstart', (e) => {
        // e.preventDefault(); // 注意：不要在這裡 preventDefault，否則 click 永遠不會觸發
        startPress(e);
    }, { passive: true });
    launcher.addEventListener('touchend', cancelPress);
    launcher.addEventListener('touchcancel', cancelPress);

    // 綁定點擊事件
    launcher.addEventListener('click', handleClick);
}

// --- 初始化執行 ---
document.addEventListener('DOMContentLoaded', () => {
    createParticles();
    initSecretGameTrigger(); // 啟動彩蛋監聽

    // 初始化 Select2 (如果該頁面有 class="searchable-select" 的元素)
    if (typeof jQuery !== 'undefined') {
        $('.searchable-select').select2({
            width: '100%',
            language: "zh-TW" //* 設定下拉選單提示為繁體中文
        });
    }
});

// 拖曳功能實作
function makeDraggable(elmnt) {
    var pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
    var header = document.getElementById(elmnt.id + "-header");

    if (header) {
        header.onmousedown = dragMouseDown; //* 滑鼠按下標題列時觸發
    } else {
        elmnt.onmousedown = dragMouseDown;
    }

    function dragMouseDown(e) {
        e = e || window.event;
        e.preventDefault();
        pos3 = e.clientX;
        pos4 = e.clientY;
        document.onmouseup = closeDragElement;
        document.onmousemove = elementDrag;
    }

    function elementDrag(e) {
        e = e || window.event;
        e.preventDefault();
        pos1 = pos3 - e.clientX;
        pos2 = pos4 - e.clientY;
        pos3 = e.clientX;
        pos4 = e.clientY;
        //* 更新元件的絕對位置
        elmnt.style.top = (elmnt.offsetTop - pos2) + "px";
        elmnt.style.left = (elmnt.offsetLeft - pos1) + "px";
        elmnt.style.bottom = "auto";
        elmnt.style.right = "auto";
    }

    function closeDragElement() {
        document.onmouseup = null; //* 釋放滑鼠時解除綁定
        document.onmousemove = null;
    }
}

// 切換縮小狀態與圖示
function toggleMinimizeWidget() {
    const widget = document.getElementById("transfer-notify-widget");
    const icon = document.getElementById("minimize-icon");

    if (widget && icon) {
        // 切換縮小狀態的 class
        widget.classList.toggle('widget-minimized');

        // 判斷目前是否為縮小狀態來更換圖示
        if (widget.classList.contains('widget-minimized')) {
            icon.classList.remove('fa-minus');
            icon.classList.add('fa-window-restore'); //* 變成還原圖示
        } else {
            icon.classList.remove('fa-window-restore');
            icon.classList.add('fa-minus'); //* 變回縮小圖示
        }
    }
}

// 關閉通知，並將該筆轉移 ID 記錄至會話快取中
function closeWidget() {
    const widget = document.getElementById("transfer-notify-widget");
    if (widget) {
        const recordId = widget.getAttribute('data-record-id');
        if (recordId) {
            // 將此紀錄 ID 存入 sessionStorage，代表本次登入會話中，使用者已不想看見此通知
            sessionStorage.setItem('processed_transfer_' + recordId, 'true');
        }
        widget.style.display = 'none';
    }
}

// 初始化浮動元件與快取檢查
document.addEventListener('DOMContentLoaded', () => {
    const notifyWidget = document.getElementById("transfer-notify-widget");

    if (notifyWidget) {
        const recordId = notifyWidget.getAttribute('data-record-id');

        // 檢查此轉移紀錄 ID 是否存在於已被關閉或已被處理的會話快取中
        if (recordId && sessionStorage.getItem('processed_transfer_' + recordId) === 'true') {
            notifyWidget.style.display = 'none'; //* 存在快取紀錄則直接封鎖不顯示
        } else {
            makeDraggable(notifyWidget); //* 正常狀態下才啟用拖曳功能
        }
    }

    // 初始化 Select2 樣式微調
    if (typeof jQuery !== 'undefined' && $.fn.select2) {
        $('.searchable-select').select2({
            width: '100%',
            language: "zh-TW"
        });
    }
});