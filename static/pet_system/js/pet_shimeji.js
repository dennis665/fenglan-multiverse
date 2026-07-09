class PetShimeji {
    constructor() {
        this.container = null;
        this.petEl = null;
        this.headEl = null;
        this.faceEl = null;
        this.backEl = null;
        
        // 寵物屬性
        this.hasPet = false;
        this.petData = null;
        
        // 狀態與座標 (相對於 viewport)
        this.x = window.innerWidth - 150;
        this.y = 0; // 相對於瀏覽器底部的偏移 (0 代表在最底部)
        this.stableFloor = 0; // 拖拉後維持的穩定垂直高度
        this.vx = 0.4;
        this.vy = 0;
        this.width = 64;
        this.height = 64;
        
        // 拖拉相關狀態
        this.isDragging = false;
        this.dragStartX = 0;
        this.dragStartY = 0;
        this.dragStartPetX = 0;
        this.dragStartPetY = 0;
        this.hasMoved = false;

        // 動作邏輯
        this.state = 'walk'; // walk, idle, sleep, climb
        this.stateTimer = 100;
        this.facingRight = false;
        this.bobPhase = 0;
        this.bobOffset = 0;
        this.climbDirection = 1; // 1 = 向上, -1 = 向下
        
        // 對話庫
        this.dialogues = {
            CHUBBY: [
                "嗝～好飽喔... (摸肚子)",
                "主人，今天也要乖乖登入喔！金幣交給我守護！",
                "呼...呼... 感覺又變圓了... Zzz",
                "有沒有好吃的乾糧啊？(口水)",
            ],
            BRAVE: [
                "喝！火球術！(中二病發作)",
                "衝啊！冒險塔的怪獸在哪裡？",
                "星光烈焰在我的雙翼上燃燒！",
                "主人，今天完成任務了嗎？讓我們一起變強！",
            ],
            DEFAULT: [
                "主人，今天也是元氣滿滿的一天！",
                "點擊我有驚喜喔！(跳躍)",
                "啦啦啦～散步真開心～",
                "記得去 [寵物培育室] 看看我喔！",
            ]
        };

        this.init();
    }

    init() {
        // 先請求後端 API，確定是否有召喚出戰寵物
        fetch("/pet/api/get_active_shimeji/")
            .then(res => res.json())
            .then(data => {
                if (data.status === "success") {
                    this.hasPet = true;
                    this.petData = data;
                    this.setupDOM();
                    this.loadImages();
                    this.startLoop();
                }
            })
            .catch(err => console.log("Shimeji init failed:", err));
    }

    setupDOM() {
        // 建立浮動容器
        this.container = document.createElement("div");
        this.container.id = "shimeji-container";
        Object.assign(this.container.style, {
            position: "fixed",
            width: `${this.width}px`,
            height: `${this.height}px`,
            bottom: "0px",
            left: `${this.x}px`,
            zIndex: "99999",
            cursor: "grab",
            pointerEvents: "auto",
            transition: "bottom 0.1s ease",
            userSelect: "none"
        });

        // 建立身體與配件圖片元素堆疊以播放 WebP 動圖動作檔
        this.petEl = document.createElement("img");
        this.headEl = document.createElement("img");
        this.faceEl = document.createElement("img");
        this.backEl = document.createElement("img");

        const commonStyle = {
            position: "absolute",
            width: "100%",
            height: "100%",
            left: "0px",
            top: "0px",
            objectFit: "contain"
        };
        Object.assign(this.petEl.style, commonStyle);
        Object.assign(this.headEl.style, commonStyle);
        Object.assign(this.faceEl.style, commonStyle);
        Object.assign(this.backEl.style, commonStyle);

        this.container.appendChild(this.backEl);
        this.container.appendChild(this.petEl);
        this.container.appendChild(this.faceEl);
        this.container.appendChild(this.headEl);
        
        document.body.appendChild(this.container);

        // 綁定拖拉與點擊事件
        const onMouseDown = (e) => {
            this.isDragging = true;
            this.hasMoved = false;
            this.container.style.cursor = "grabbing";

            // 觸控或滑鼠座標取得
            const clientX = e.touches ? e.touches[0].clientX : e.clientX;
            const clientY = e.touches ? e.touches[0].clientY : e.clientY;

            this.dragStartX = clientX;
            this.dragStartY = clientY;
            this.dragStartPetX = this.x;
            this.dragStartPetY = this.y;

            // 暫停過渡以求拖拉流暢
            this.container.style.transition = "none";
            
            // 阻止網頁預設選取行為
            if (e.cancelable) {
                e.preventDefault();
            }
        };

        const onMouseMove = (e) => {
            if (!this.isDragging) return;

            const clientX = e.touches ? e.touches[0].clientX : e.clientX;
            const clientY = e.touches ? e.touches[0].clientY : e.clientY;

            const deltaX = clientX - this.dragStartX;
            const deltaY = clientY - this.dragStartY;

            // 判定為拖拉而非單純點擊
            if (Math.hypot(deltaX, deltaY) > 5) {
                this.hasMoved = true;
            }

            // 更新 X, Y 座標 (Y 相對於底部)
            this.x = this.dragStartPetX + deltaX;
            this.y = this.dragStartPetY - deltaY;

            // 視窗邊界限制
            this.x = Math.max(0, Math.min(this.x, window.innerWidth - this.width));
            this.y = Math.max(0, Math.min(this.y, window.innerHeight - this.height));

            // 即時更新元件 DOM 位置
            this.container.style.left = `${this.x}px`;
            this.container.style.bottom = `${this.y}px`;
            
            // 更新對話泡泡位置
            const bubble = document.getElementById("shimeji-bubble");
            if (bubble) {
                bubble.style.left = `${this.x - 50}px`;
                bubble.style.bottom = `${this.y + 68}px`;
            }
        };

        const onMouseUp = () => {
            if (!this.isDragging) return;
            this.isDragging = false;
            this.container.style.cursor = "grab";

            // 恢復過渡效果
            this.container.style.transition = "bottom 0.1s ease";
            
            // 設定拖拉釋放後的新穩定高度 ground level
            this.stableFloor = this.y;

            if (!this.hasMoved) {
                // 如果移動距離極小，觸發一般點擊互動
                this.handleInteract();
            }
        };

        // 滑鼠監聽
        this.container.addEventListener("mousedown", onMouseDown);
        window.addEventListener("mousemove", onMouseMove);
        window.addEventListener("mouseup", onMouseUp);

        // 觸控監聽
        this.container.addEventListener("touchstart", onMouseDown, { passive: false });
        window.addEventListener("touchmove", onMouseMove, { passive: false });
        window.addEventListener("touchend", onMouseUp);
    }

    loadImages() {
        this.draw();
    }

    reload() {
        fetch("/pet/api/get_active_shimeji/")
            .then(res => res.json())
            .then(data => {
                if (data.status === "success") {
                    this.hasPet = true;
                    this.petData = data;
                    
                    if (this.container) {
                        this.draw();
                    } else {
                        this.setupDOM();
                        this.startLoop();
                    }
                } else {
                    this.hasPet = false;
                    this.petData = null;
                    if (this.container) {
                        this.container.remove();
                        this.container = null;
                    }
                }
            })
            .catch(err => console.log("Shimeji reload failed:", err));
    }


    handleInteract() {
        // 1. 播放 Q 彈叫聲
        if (window.petSound) {
            window.petSound.init();
            window.petSound.playClick();
        }

        // 2. 觸發跳躍動作 (相對於目前的穩定高度)
        if (this.state !== 'climb') {
            this.vy = -6;
            this.y = this.stableFloor + 1; // 浮空啟動
        }

        // 3. 彈出隨機對話泡泡
        this.showBubble();
    }

    showBubble() {
        const oldBubble = document.getElementById("shimeji-bubble");
        if (oldBubble) oldBubble.remove();

        const pType = this.petData.personality;
        const pool = this.dialogues[pType] || this.dialogues.DEFAULT;
        const msg = pool[Math.floor(Math.random() * pool.length)];

        const bubble = document.createElement("div");
        bubble.id = "shimeji-bubble";
        Object.assign(bubble.style, {
            position: "fixed",
            bottom: `${this.y + 68}px`,
            left: `${this.x - 50}px`,
            width: "160px",
            background: "rgba(255, 255, 255, 0.95)",
            border: "2px solid #28a745",
            borderRadius: "12px",
            padding: "8px 12px",
            fontSize: "12px",
            color: "#155724",
            boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
            zIndex: "100000",
            pointerEvents: "none",
            textAlign: "center",
            fontWeight: "bold",
            animation: "fadeInUp 0.3s ease"
        });
        
        if (!document.getElementById("shimeji-anim-style")) {
            const style = document.createElement("style");
            style.id = "shimeji-anim-style";
            style.innerHTML = `
                @keyframes fadeInUp {
                    from { opacity: 0; transform: translateY(10px); }
                    to { opacity: 1; transform: translateY(0); }
                }
            `;
            document.head.appendChild(style);
        }

        bubble.innerText = msg;
        document.body.appendChild(bubble);

        setTimeout(() => {
            if (bubble) bubble.remove();
        }, 3000);
    }

    update() {
        this.bobPhase += 0.08;
        
        // 拖拉時暫停自動位移更新
        if (this.isDragging) {
            this.bobOffset = Math.sin(this.bobPhase * 2) * 3; // 保持抓起時的走動掙扎動畫
            return;
        }

        // 確保泡泡定位跟著寵物移動
        const bubble = document.getElementById("shimeji-bubble");
        if (bubble) {
            bubble.style.left = `${this.x - 50}px`;
            bubble.style.bottom = `${this.y + 68}px`;
        }

        // 處理重力跳躍物理 (落回 stableFloor)
        if (this.y > this.stableFloor) {
            this.vy += 0.3; // 模擬重力
            this.y -= this.vy;
            if (this.y <= this.stableFloor) {
                this.y = this.stableFloor;
                this.vy = 0;
            }
        }

        // 狀態機行為更新
        this.stateTimer--;
        if (this.stateTimer <= 0) {
            this.stateTimer = 80 + Math.random() * 120;
            
            const rand = Math.random();
            if (rand < 0.4) {
                this.state = 'walk';
                this.vx = (Math.random() > 0.5 ? 0.3 : -0.3);
                this.facingRight = this.vx > 0;
            } else if (rand < 0.7) {
                this.state = 'idle';
                this.vx = 0;
            } else if (rand < 0.9) {
                this.state = 'sleep';
                this.vx = 0;
            } else {
                // 攀爬側邊牆壁
                this.state = 'climb';
                this.vx = 0;
                this.x = (Math.random() > 0.5) ? 0 : window.innerWidth - this.width;
                this.climbDirection = (Math.random() > 0.5) ? 1 : -1;
            }
        }

        // 執行狀態機
        if (this.state === 'walk' && this.y === this.stableFloor) {
            this.x += this.vx;
            this.bobOffset = Math.sin(this.bobPhase * 2) * 3;
            
            // 左右邊界反彈
            if (this.x < 10) {
                this.x = 10;
                this.vx *= -1;
                this.facingRight = true;
            } else if (this.x > window.innerWidth - this.width - 10) {
                this.x = window.innerWidth - this.width - 10;
                this.vx *= -1;
                this.facingRight = false;
            }
        } else if (this.state === 'climb') {
            // 垂直攀爬
            this.y += this.climbDirection * 0.4;
            this.bobOffset = Math.sin(this.bobPhase * 2) * 2;
            
            // 爬到頂部折返，爬到底部著地
            if (this.y > window.innerHeight - 150) {
                this.climbDirection = -1;
            } else if (this.y <= this.stableFloor) {
                this.y = this.stableFloor;
                this.state = 'walk'; // 著地後開始走動
                this.vx = 0.3;
                this.stateTimer = 100;
            }
        } else if (this.state === 'sleep') {
            this.bobOffset = Math.sin(this.bobPhase * 0.5) * 1;
        } else {
            this.bobOffset = Math.sin(this.bobPhase) * 1.5;
        }

        // 更新 DOM 元件定位
        if (this.container) {
            this.container.style.left = `${this.x}px`;
            this.container.style.bottom = `${this.y}px`;
        }
    }

    draw() {
        if (!this.container || !this.petData) return;

        // 根據狀態選擇對應的 WebP 動畫動作檔
        let action = "sleep";
        if (this.state === 'walk' || this.state === 'climb') {
            action = "walk";
        } else if (this.y > this.stableFloor) {
            action = "jump";
        } else if (this.state === 'sleep') {
            action = "sleep";
        } else {
            action = "sleep";
        }

        // 解析對應的動畫 WebP 檔
        let baseUrl = this.petData.pixel_image_url;
        let animUrl = baseUrl;
        if (baseUrl.endsWith(".webp") && this.petData.stage > 0) {
            let baseWithoutExt = baseUrl.substring(0, baseUrl.length - 5);
            if (action === "walk") {
                let dirSuffix = this.facingRight ? "right" : "left";
                animUrl = `${baseWithoutExt}_walk_${dirSuffix}.webp`;
            } else {
                animUrl = `${baseWithoutExt}_${action}.webp`;
            }
        }

        if (this.petEl.src !== window.location.origin + animUrl && !this.petEl.src.endsWith(animUrl)) {
            this.petEl.src = animUrl;
        }

        // 配件
        if (this.petData.equipped_head) {
            this.headEl.src = `/static/pet_system/images/${this.petData.equipped_head}.webp`;
            this.headEl.style.display = "block";
        } else {
            this.headEl.style.display = "none";
        }

        if (this.petData.equipped_face) {
            this.faceEl.src = `/static/pet_system/images/${this.petData.equipped_face}.webp`;
            this.faceEl.style.display = "block";
        } else {
            this.faceEl.style.display = "none";
        }

        if (this.petData.equipped_back) {
            this.backEl.src = `/static/pet_system/images/${this.petData.equipped_back}.webp`;
            this.backEl.style.display = "block";
        } else {
            this.backEl.style.display = "none";
        }

        // 處理非正方形 (如 128x233 縱向加高) 的圖片播放縮小問題
        let naturalW = this.petEl.naturalWidth;
        let naturalH = this.petEl.naturalHeight;
        if (naturalW && naturalH && naturalH > naturalW) {
            let ratio = naturalH / naturalW;
            let heightPercent = `${ratio * 100}%`;
            
            this.petEl.style.height = heightPercent;
            this.petEl.style.top = "auto";
            this.petEl.style.bottom = "0px";
            
            this.headEl.style.height = heightPercent;
            this.headEl.style.top = "auto";
            this.headEl.style.bottom = "0px";
            
            this.faceEl.style.height = heightPercent;
            this.faceEl.style.top = "auto";
            this.faceEl.style.bottom = "0px";
            
            this.backEl.style.height = heightPercent;
            this.backEl.style.top = "auto";
            this.backEl.style.bottom = "0px";
        } else {
            this.petEl.style.height = "100%";
            this.petEl.style.top = "0px";
            this.petEl.style.bottom = "auto";
            
            this.headEl.style.height = "100%";
            this.headEl.style.top = "0px";
            this.headEl.style.bottom = "auto";
            
            this.faceEl.style.height = "100%";
            this.faceEl.style.top = "0px";
            this.faceEl.style.bottom = "auto";
            
            this.backEl.style.height = "100%";
            this.backEl.style.top = "0px";
            this.backEl.style.bottom = "auto";
        }

        // 套用翻轉、上下顛簸與旋轉，並融合動態骨骼插槽偏移量
        let scaleX = this.facingRight ? -1 : 1;
        if (action === "walk") {
            this.petEl.style.transform = "scaleX(1)";
        } else {
            this.petEl.style.transform = `scaleX(${scaleX})`;
        }
        
        // 取得插槽偏移值
        const headTrans = getAccessoryTransform(this.petData.pet_type, this.petData.stage, this.petData.personality, "head");
        const faceTrans = getAccessoryTransform(this.petData.pet_type, this.petData.stage, this.petData.personality, "face");
        const backTrans = getAccessoryTransform(this.petData.pet_type, this.petData.stage, this.petData.personality, "back");
        
        this.headEl.style.transform = `scaleX(${scaleX}) ${headTrans}`;
        this.faceEl.style.transform = `scaleX(${scaleX}) ${faceTrans}`;
        this.backEl.style.transform = `scaleX(${scaleX}) ${backTrans}`;
        
        // 對容器套用 bobOffset (上下顛簸)
        this.container.style.transform = `translateY(${this.bobOffset}px)`;
    }

    startLoop() {
        const loop = () => {
            this.update();
            this.draw();
            requestAnimationFrame(loop);
        };
        requestAnimationFrame(loop);
    }
}

// 統一的配件骨骼插槽定位對齊函數
function getAccessoryTransform(petType, stage, personality, slot) {
    let dx = 0, dy = 0, scale = 1.0;
    
    if (petType === "DRAGON") {
        if (stage === 1) {
            if (slot === "head") { dx = -2; dy = 14; scale = 0.65; }
            else if (slot === "face") { dx = 4; dy = 14; scale = 0.65; }
            else if (slot === "back") { dx = 12; dy = 12; scale = 0.65; }
        } else if (stage === 2) {
            if (slot === "head") { dx = -4; dy = 2; scale = 0.8; }
            else if (slot === "face") { dx = 6; dy = 4; scale = 0.8; }
            else if (slot === "back") { dx = 12; dy = 4; scale = 0.8; }
        } else if (stage === 3) {
            if (slot === "head") { dx = -16; dy = -8; scale = 1.15; }
            else if (slot === "face") { dx = -4; dy = -6; scale = 1.15; }
            else if (slot === "back") { dx = 16; dy = -2; scale = 1.15; }
        } else if (stage === 4) {
            if (personality === "CHUBBY") {
                if (slot === "head") { dx = -4; dy = 8; scale = 1.05; }
                else if (slot === "face") { dx = 6; dy = 10; scale = 1.05; }
                else if (slot === "back") { dx = 14; dy = 8; scale = 1.05; }
            } else if (personality === "BRAVE") {
                if (slot === "head") { dx = -2; dy = -12; scale = 1.1; }
                else if (slot === "face") { dx = 8; dy = -8; scale = 1.1; }
                else if (slot === "back") { dx = 12; dy = -4; scale = 1.1; }
            } else { // EMERALD
                if (slot === "head") { dx = -4; dy = -6; scale = 1.1; }
                else if (slot === "face") { dx = 8; dy = -2; scale = 1.1; }
                else if (slot === "back") { dx = 14; dy = -2; scale = 1.1; }
            }
        }
    } else { // PUPPY
        if (stage === 1) {
            if (slot === "head") { dx = -2; dy = 16; scale = 0.6; }
            else if (slot === "face") { dx = 4; dy = 18; scale = 0.6; }
            else if (slot === "back") { dx = 10; dy = 16; scale = 0.6; }
        } else if (stage === 2) {
            if (slot === "head") { dx = -4; dy = 8; scale = 0.8; }
            else if (slot === "face") { dx = 6; dy = 10; scale = 0.8; }
            else if (slot === "back") { dx = 12; dy = 8; scale = 0.8; }
        } else if (stage === 3) {
            if (slot === "head") { dx = -10; dy = -2; scale = 1.1; }
            else if (slot === "face") { dx = -2; dy = 2; scale = 1.1; }
            else if (slot === "back") { dx = 16; dy = 0; scale = 1.1; }
        } else if (stage === 4) {
            if (personality === "CHUBBY") {
                if (slot === "head") { dx = -4; dy = 12; scale = 1.0; }
                else if (slot === "face") { dx = 6; dy = 14; scale = 1.0; }
                else if (slot === "back") { dx = 14; dy = 12; scale = 1.0; }
            } else if (personality === "BRAVE") {
                if (slot === "head") { dx = -6; dy = -8; scale = 1.1; }
                else if (slot === "face") { dx = 2; dy = -4; scale = 1.1; }
                else if (slot === "back") { dx = 14; dy = -4; scale = 1.1; }
            } else { // EMERALD
                if (slot === "head") { dx = -6; dy = -10; scale = 1.1; }
                else if (slot === "face") { dx = 2; dy = -6; scale = 1.1; }
                else if (slot === "back") { dx = 14; dy = -6; scale = 1.1; }
            }
        }
    }
    
    return `translate(${dx}px, ${dy}px) scale(${scale})`;
}

// 當文件加載完成後自動載入全站桌寵
document.addEventListener("DOMContentLoaded", () => {
    window.petShimeji = new PetShimeji();
});
