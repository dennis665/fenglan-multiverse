class PetRenderer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.container = this.canvas.parentElement; // petCanvasContainer
        
        // 將 canvas 作為背景繪圖（可放著或不畫），寵物實體則採用 DOM 元件，以播放 WebP 動畫
        this.canvas.style.pointerEvents = "none"; 
        this.container.style.position = "relative";
        
        // 點擊事件已取消
        // this.container.addEventListener('click', (e) => this.handleCanvasClick(e));

        this.pets = []; // 存放所有未召喚出戰的寵物實例
        this.gravity = 0.4;
        this.jumpForce = -9;
        this.groundY = 180;
        this.breathPhase = 0;

        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
    }

    resizeCanvas() {
        if (!this.canvas) return;
        const rect = this.canvas.parentElement.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = 250; // 固定高度
        this.groundY = this.canvas.height - 70;
        
        // 修正非跳躍中寵物的地面高度與橫向邊界
        this.pets.forEach(pet => {
            if (!pet.isJumping) {
                pet.y = this.groundY;
            }
            if (pet.x > this.canvas.width - pet.radius) {
                pet.x = this.canvas.width - pet.radius;
            }
        });
    }

    setPets(inactivePetsList) {
        // 先清理所有的舊 DOM 寵物元素，避免累積殘留
        const oldPetEls = this.container.querySelectorAll(".dom-pet-instance");
        oldPetEls.forEach(el => el.remove());

        this.pets = [];

        inactivePetsList.forEach(petData => {
            // 建立寵物專用 DOM 容器，以 center bottom 定位方便縮放
            const petEl = document.createElement("div");
            petEl.className = "dom-pet-instance";
            Object.assign(petEl.style, {
                position: "absolute",
                width: "80px",
                height: "80px",
                pointerEvents: "none", // 設為 none 以取消所有點擊框與選取框
                cursor: "default",
                transformOrigin: "center bottom",
                transition: "transform 0.05s ease",
                outline: "none",
                border: "none",
                userSelect: "none",
                webkitUserSelect: "none",
                webkitTapHighlightColor: "transparent"
            });

            // 身體與配件的 <img> 標籤層疊
            const bodyImg = document.createElement("img");
            const headImg = document.createElement("img");
            const faceImg = document.createElement("img");
            const backImg = document.createElement("img");

            const imgStyle = {
                position: "absolute",
                width: "100%",
                height: "100%",
                left: "0px",
                top: "0px",
                objectFit: "contain",
                border: "none",
                outline: "none"
            };
            Object.assign(bodyImg.style, imgStyle);
            Object.assign(headImg.style, imgStyle);
            Object.assign(faceImg.style, imgStyle);
            Object.assign(backImg.style, imgStyle);

            // 預設將非身體的配件圖片隱藏，避免瀏覽器在空 src 時顯示框線與破圖圖示
            headImg.style.display = "none";
            faceImg.style.display = "none";
            backImg.style.display = "none";

            // Z-Order 層級：背飾 -> 身體 -> 臉飾 -> 頭飾
            petEl.appendChild(backImg);
            petEl.appendChild(bodyImg);
            petEl.appendChild(faceImg);
            petEl.appendChild(headImg);

            // 名字與等級標籤
            const nameTag = document.createElement("div");
            nameTag.innerText = petData.name || "未命名寵物";
            Object.assign(nameTag.style, {
                position: "absolute",
                top: "-15px",
                width: "120px",
                left: "-20px",
                textAlign: "center",
                fontSize: "11px",
                fontWeight: "bold",
                color: "#ffffff",
                textShadow: "1px 1px 3px rgba(0,0,0,0.8)",
                pointerEvents: "none"
            });
            petEl.appendChild(nameTag);

            this.container.appendChild(petEl);

            const petObj = {
                id: petData.id,
                name: petData.name,
                stage: petData.stage,
                pet_type: petData.pet_type,
                personality: petData.personality,
                
                // DOM 物件綁定
                el: petEl,
                bodyImg: bodyImg,
                headImg: headImg,
                faceImg: faceImg,
                backImg: backImg,
                
                // 物理運動屬性
                x: petData.stage === 0 ? this.canvas.width / 2 : 50 + Math.random() * (this.canvas.width - 100),
                y: this.groundY,
                radius: 40, 
                vx: petData.stage === 0 ? 0 : (Math.random() > 0.5 ? 0.7 : -0.7),
                vy: 0,
                
                state: petData.stage === 0 ? 'idle' : 'walking',
                facingRight: Math.random() > 0.5,
                rotation: 0,
                spinSpeed: 0,
                bobOffset: 0,
                isJumping: false,
                stateTimer: 60 + Math.random() * 120,
            };

            // 解析靜態圖片路徑
            let imageUrl = "/static/pet_system/images/pet_egg.webp";
            if (petData.pet_type === "DRAGON") {
                if (petData.stage === 1) imageUrl = "/static/pet_system/images/baby_dragon.webp";
                else if (petData.stage === 2) imageUrl = "/static/pet_system/images/growth_dragon.webp";
                else if (petData.stage === 3) imageUrl = "/static/pet_system/images/complete_dragon.webp";
                else if (petData.stage === 4) {
                    if (petData.personality === "CHUBBY") imageUrl = "/static/pet_system/images/pixel_chubby_dragon.webp";
                    else if (petData.personality === "BRAVE") imageUrl = "/static/pet_system/images/pixel_star_dragon.webp";
                    else imageUrl = "/static/pet_system/images/pixel_emerald_dragon.webp";
                }
            } else {
                if (petData.stage === 1) imageUrl = "/static/pet_system/images/baby_puppy.webp";
                else if (petData.stage === 2) imageUrl = "/static/pet_system/images/growth_puppy.webp";
                else if (petData.stage === 3) imageUrl = "/static/pet_system/images/complete_puppy.webp";
                else if (petData.stage === 4) {
                    if (petData.personality === "CHUBBY") imageUrl = "/static/pet_system/images/pixel_chubby_puppy.webp";
                    else if (petData.personality === "BRAVE") imageUrl = "/static/pet_system/images/pixel_star_puppy.webp";
                    else imageUrl = "/static/pet_system/images/pixel_emerald_puppy.webp";
                }
            }
            petObj.baseUrl = imageUrl;

            // 載入頭飾、臉飾、背飾，並套用動態骨骼對齊偏移
            if (petData.equipped_head) {
                headImg.src = `/static/pet_system/images/${petData.equipped_head}.webp`;
                headImg.style.transform = getAccessoryTransform(petData.pet_type, petData.stage, petData.personality, "head");
                headImg.style.display = "block";
            }
            if (petData.equipped_face) {
                faceImg.src = `/static/pet_system/images/${petData.equipped_face}.webp`;
                faceImg.style.transform = getAccessoryTransform(petData.pet_type, petData.stage, petData.personality, "face");
                faceImg.style.display = "block";
            }
            if (petData.equipped_back) {
                backImg.src = `/static/pet_system/images/${petData.equipped_back}.webp`;
                backImg.style.transform = getAccessoryTransform(petData.pet_type, petData.stage, petData.personality, "back");
                backImg.style.display = "block";
            }

            this.pets.push(petObj);
        });
    }

    handleCanvasClick(e) {
        if (this.pets.length === 0) return;
        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        
        // 點擊判定 (以 center 為基準)
        for (let i = this.pets.length - 1; i >= 0; i--) {
            const pet = this.pets[i];
            const dist = Math.hypot(mouseX - pet.x, mouseY - pet.y);
            if (dist <= pet.radius + 15) {
                this.triggerJump(pet);
                break;
            }
        }
    }

    triggerJump(pet) {
        if (pet.stage === 0) return; // 寵物蛋不跳躍
        if (!pet.isJumping) {
            pet.isJumping = true;
            pet.state = 'jumping';
            pet.vy = this.jumpForce;
            // 隨機空中翻轉速度
            pet.spinSpeed = Math.random() > 0.5 ? 0.15 : -0.15;
            
            if (window.petSound) {
                window.petSound.playClick();
            }
        }
    }

    update() {
        this.breathPhase += 0.05;
        
        this.pets.forEach(pet => {
            if (pet.isJumping) {
                // 跳躍物理
                pet.vy += this.gravity;
                pet.y += pet.vy;
                pet.rotation += pet.spinSpeed;
                
                // 落地檢測
                if (pet.y >= this.groundY) {
                    pet.y = this.groundY;
                    pet.isJumping = false;
                    pet.vy = 0;
                    pet.rotation = 0;
                    pet.state = 'idle';
                    pet.stateTimer = 30; // 落地短暫發呆
                }
            } else {
                if (pet.stage === 0) {
                    pet.state = 'idle';
                    pet.bobOffset = Math.sin(this.breathPhase) * 2;
                    return;
                }

                // 狀態隨機轉移
                pet.stateTimer--;
                if (pet.stateTimer <= 0) {
                    if (Math.random() > 0.4) {
                        pet.state = 'walking';
                        pet.vx = (Math.random() > 0.5 ? 0.7 : -0.7);
                        pet.facingRight = pet.vx > 0;
                    } else {
                        pet.state = 'idle';
                        pet.vx = 0;
                    }
                    pet.stateTimer = 60 + Math.random() * 120;
                }
                
                // 行走位移與上下顛簸
                if (pet.state === 'walking') {
                    pet.x += pet.vx;
                    pet.bobOffset = Math.sin(this.breathPhase * 2) * 3;
                    
                    // 左右邊界碰撞反彈
                    if (pet.x < pet.radius + 10) {
                        pet.x = pet.radius + 10;
                        pet.vx *= -1;
                        pet.facingRight = true;
                    } else if (pet.x > this.canvas.width - pet.radius - 10) {
                        pet.x = this.canvas.width - pet.radius - 10;
                        pet.vx *= -1;
                        pet.facingRight = false;
                    }
                } else {
                    pet.bobOffset = Math.sin(this.breathPhase) * 2;
                }
            }
        });
    }

    draw() {
        // 清理背景 (我們可以使用 Canvas 畫布，或者直接放任 DOM)
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        if (this.pets.length === 0) {
            // 沒有未召喚寵物時的文字提示
            this.ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
            this.ctx.textAlign = 'center';
            this.ctx.font = 'bold 15px "Inter", sans-serif';
            this.ctx.fillText("培育室目前空空如也", this.canvas.width / 2, this.groundY - 10);
            this.ctx.font = '12px "Inter", sans-serif';
            this.ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
            this.ctx.fillText("已召喚的出戰寵物在全網頁漫遊冒險！未出戰的寵物將會出現在這。", this.canvas.width / 2, this.groundY + 15);
            return;
        }

        // 渲染每個寵物的 DOM 元件位置與動作
        this.pets.forEach(pet => {
            if (!pet.el) return;

            // 1. 在背景 Canvas 繪製簡約的腳底微光陰影
            const shadowOpacity = Math.max(0.02, 0.12 - (this.groundY - pet.y) / 150);
            const shadowWidth = pet.radius * (1.1 - (this.groundY - pet.y) / 200);
            this.ctx.fillStyle = `rgba(0, 0, 0, ${shadowOpacity})`;
            this.ctx.beginPath();
            this.ctx.ellipse(pet.x, this.groundY + pet.radius - 8, shadowWidth, 6, 0, 0, Math.PI * 2);
            this.ctx.fill();

            // 2. 依物理狀態隨機或定點載入 walk, sleep, jump 動圖 WebP
            let action = "sleep";
            if (pet.stage === 0) {
                action = "sleep";
            } else if (pet.isJumping || pet.state === 'jumping') {
                action = "jump";
            } else if (pet.state === 'walking') {
                action = "walk";
            } else {
                action = "sleep";
            }

            let animUrl = pet.baseUrl;
            if (pet.baseUrl.endsWith(".webp") && pet.stage > 0) {
                let baseWithoutExt = pet.baseUrl.substring(0, pet.baseUrl.length - 5);
                if (action === "walk") {
                    let dirSuffix = pet.facingRight ? "right" : "left";
                    animUrl = `${baseWithoutExt}_walk_${dirSuffix}.webp`;
                } else {
                    animUrl = `${baseWithoutExt}_${action}.webp`;
                }
            }

            if (pet.bodyImg.src !== window.location.origin + animUrl && !pet.bodyImg.src.endsWith(animUrl)) {
                pet.bodyImg.src = animUrl;
            }

            // 3. 更新 DOM 物件的 X 軸與 Y 軸定位 (bottom 為基準，結合 bobOffset)
            const finalY = this.canvas.height - pet.y - 40 + pet.bobOffset;
            pet.el.style.left = `${pet.x - 40}px`;
            pet.el.style.bottom = `${finalY}px`;

            // 4. 套用翻轉、上下顛簸與旋轉 (避免翻轉整個容器導致文字反轉，改為翻轉主體與飾品)
            let scaleX = pet.facingRight ? -1 : 1;
            pet.el.style.transform = `rotate(${pet.rotation}rad)`;

            // 處理非正方形 (如 128x233 縱向加高) 的圖片播放縮小問題
            let naturalW = pet.bodyImg.naturalWidth;
            let naturalH = pet.bodyImg.naturalHeight;
            if (naturalW && naturalH && naturalH > naturalW) {
                let ratio = naturalH / naturalW;
                let heightPercent = `${ratio * 100}%`;
                
                pet.bodyImg.style.height = heightPercent;
                pet.bodyImg.style.top = "auto";
                pet.bodyImg.style.bottom = "0px";
                
                pet.headImg.style.height = heightPercent;
                pet.headImg.style.top = "auto";
                pet.headImg.style.bottom = "0px";
                
                pet.faceImg.style.height = heightPercent;
                pet.faceImg.style.top = "auto";
                pet.faceImg.style.bottom = "0px";
                
                pet.backImg.style.height = heightPercent;
                pet.backImg.style.top = "auto";
                pet.backImg.style.bottom = "0px";
            } else {
                pet.bodyImg.style.height = "100%";
                pet.bodyImg.style.top = "0px";
                pet.bodyImg.style.bottom = "auto";
                
                pet.headImg.style.height = "100%";
                pet.headImg.style.top = "0px";
                pet.headImg.style.bottom = "auto";
                
                pet.faceImg.style.height = "100%";
                pet.faceImg.style.top = "0px";
                pet.faceImg.style.bottom = "auto";
                
                pet.backImg.style.height = "100%";
                pet.backImg.style.top = "0px";
                pet.backImg.style.bottom = "auto";
            }

            if (action === "walk") {
                // 走路自帶左右向圖資，主體無須再翻轉
                pet.bodyImg.style.transform = "scaleX(1)";
            } else {
                // 其它動作由 CSS 翻轉
                pet.bodyImg.style.transform = `scaleX(${scaleX})`;
            }

            // 動態更新配件翻轉與插槽偏移
            const headTrans = getAccessoryTransform(pet.pet_type, pet.stage, pet.personality, "head");
            const faceTrans = getAccessoryTransform(pet.pet_type, pet.stage, pet.personality, "face");
            const backTrans = getAccessoryTransform(pet.pet_type, pet.stage, pet.personality, "back");

            pet.headImg.style.transform = `scaleX(${scaleX}) ${headTrans}`;
            pet.faceImg.style.transform = `scaleX(${scaleX}) ${faceTrans}`;
            pet.backImg.style.transform = `scaleX(${scaleX}) ${backTrans}`;
        });
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
