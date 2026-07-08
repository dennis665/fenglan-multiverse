class PetShimeji {
    constructor() {
        this.container = null;
        this.canvas = null;
        this.ctx = null;
        
        // 寵物屬性
        this.hasPet = false;
        this.petData = null;
        this.petImg = new Image();
        this.accessoryImgs = { head: new Image(), face: new Image(), back: new Image() };
        this.imgsLoaded = { body: false, head: false, face: false, back: false };
        
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

        // 建立繪圖畫布
        this.canvas = document.createElement("canvas");
        this.canvas.width = this.width;
        this.canvas.height = this.height;
        this.ctx = this.canvas.getContext("2d");
        this.container.appendChild(this.canvas);
        
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
        // 載入主體
        this.petImg.onload = () => { this.imgsLoaded.body = true; };
        this.petImg.src = this.petData.pixel_image_url;

        // 載入頭飾
        if (this.petData.equipped_head) {
            this.accessoryImgs.head.onload = () => { this.imgsLoaded.head = true; };
            this.accessoryImgs.head.src = `/static/pet_system/images/${this.petData.equipped_head}.webp`;
        }
        // 載入臉飾
        if (this.petData.equipped_face) {
            this.accessoryImgs.face.onload = () => { this.imgsLoaded.face = true; };
            this.accessoryImgs.face.src = `/static/pet_system/images/${this.petData.equipped_face}.webp`;
        }
        // 載入背飾
        if (this.petData.equipped_back) {
            this.accessoryImgs.back.onload = () => { this.imgsLoaded.back = true; };
            this.accessoryImgs.back.src = `/static/pet_system/images/${this.petData.equipped_back}.webp`;
        }
    }

    reload() {
        fetch("/pet/api/get_active_shimeji/")
            .then(res => res.json())
            .then(data => {
                if (data.status === "success") {
                    this.hasPet = true;
                    this.petData = data;
                    
                    // 重新重設加載狀態
                    this.imgsLoaded = { body: false, head: false, face: false, back: false };
                    
                    this.petImg.onload = () => { this.imgsLoaded.body = true; };
                    this.petImg.src = this.petData.pixel_image_url;

                    if (this.petData.equipped_head) {
                        this.accessoryImgs.head.onload = () => { this.imgsLoaded.head = true; };
                        this.accessoryImgs.head.src = `/static/pet_system/images/${this.petData.equipped_head}.webp`;
                    } else {
                        this.accessoryImgs.head.src = "";
                    }

                    if (this.petData.equipped_face) {
                        this.accessoryImgs.face.onload = () => { this.imgsLoaded.face = true; };
                        this.accessoryImgs.face.src = `/static/pet_system/images/${this.petData.equipped_face}.webp`;
                    } else {
                        this.accessoryImgs.face.src = "";
                    }

                    if (this.petData.equipped_back) {
                        this.accessoryImgs.back.onload = () => { this.imgsLoaded.back = true; };
                        this.accessoryImgs.back.src = `/static/pet_system/images/${this.petData.equipped_back}.webp`;
                    } else {
                        this.accessoryImgs.back.src = "";
                    }

                    // 若容器不存在，重啟建立與渲染循環
                    if (!this.container) {
                        this.setupDOM();
                        this.startLoop();
                    }
                } else {
                    // 若沒有出戰寵物，移除容器
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
        this.ctx.clearRect(0, 0, this.width, this.height);
        
        if (!this.imgsLoaded.body) return;

        this.ctx.save();
        
        // 繪製中心對齊並套用行走上下顛簸
        this.ctx.translate(this.width / 2, this.height / 2 + this.bobOffset);
        
        // 翻轉方向
        if (this.facingRight) {
            this.ctx.scale(-1, 1);
        }

        // 1. 繪製背部配件 (羽翼)
        if (this.petData.equipped_back && this.imgsLoaded.back) {
            this.ctx.drawImage(this.accessoryImgs.back, -this.width / 2, -this.height / 2, this.width, this.height);
        }

        // 2. 繪製身體
        this.ctx.drawImage(this.petImg, -this.width / 2, -this.height / 2, this.width, this.height);

        // 3. 繪製臉部配件 (墨鏡)
        if (this.petData.equipped_face && this.imgsLoaded.face) {
            this.ctx.drawImage(this.accessoryImgs.face, -this.width / 2, -this.height / 2, this.width, this.height);
        }

        // 4. 繪製頭部配件 (草帽、皇冠)
        if (this.petData.equipped_head && this.imgsLoaded.head) {
            this.ctx.drawImage(this.accessoryImgs.head, -this.width / 2, -this.height / 2, this.width, this.height);
        }

        // 5. 如果在睡覺，繪製可愛的 Zzz 氣泡
        if (this.state === 'sleep') {
            this.ctx.fillStyle = "rgba(52, 152, 219, 0.85)";
            this.ctx.font = "bold 9px Arial";
            const zCount = Math.floor((this.bobPhase % (Math.PI * 2)) / (Math.PI * 0.6)) + 1;
            const zStr = "Z".repeat(zCount);
            this.ctx.fillText(zStr, 15, -15);
        }

        this.ctx.restore();
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

// 當文件加載完成後自動載入全站桌寵
document.addEventListener("DOMContentLoaded", () => {
    window.petShimeji = new PetShimeji();
});
