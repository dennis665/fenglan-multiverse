class PetRenderer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        
        this.pets = []; // 存放所有未召喚出戰的寵物實例
        this.gravity = 0.4;
        this.jumpForce = -9;
        this.groundY = 180;
        this.breathPhase = 0;

        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
        
        // 點擊事件監聽 (點擊特定寵物觸發彈跳)
        this.canvas.addEventListener('click', (e) => this.handleCanvasClick(e));
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
        // 清理原有寵物渲染實例，重新載入
        this.pets = [];

        inactivePetsList.forEach(petData => {
            const petObj = {
                id: petData.id,
                name: petData.name || "未命名寵物",
                stage: petData.stage,
                stageName: petData.stage_display || "寵物蛋",
                personality: petData.personality,
                
                // 物理屬性 (隨機起點防止重疊擠在一起)
                x: petData.stage === 0 ? this.canvas.width / 2 : 50 + Math.random() * (this.canvas.width - 100),
                y: this.groundY,
                radius: 40, // 稍微縮小半徑以容納多隻寵物在同一畫布
                vx: petData.stage === 0 ? 0 : (Math.random() > 0.5 ? 0.7 : -0.7),
                vy: 0,
                
                state: petData.stage === 0 ? 'idle' : 'walking',
                facingRight: Math.random() > 0.5,
                scaleX: 1,
                scaleY: 1,
                rotation: 0,
                spinSpeed: 0,
                bobOffset: 0,
                isJumping: false,
                stateTimer: 60 + Math.random() * 120,

                // 資源加載
                petImg: new Image(),
                accessoryImgs: { head: new Image(), face: new Image(), back: new Image() },
                imgsLoaded: { body: false, head: false, face: false, back: false }
            };

            // 根據寵物種類、階段與性格解析 WebP 像素圖片
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
            } else { // PUPPY
                if (petData.stage === 1) imageUrl = "/static/pet_system/images/baby_puppy.webp";
                else if (petData.stage === 2) imageUrl = "/static/pet_system/images/growth_puppy.webp";
                else if (petData.stage === 3) imageUrl = "/static/pet_system/images/complete_puppy.webp";
                else if (petData.stage === 4) {
                    if (petData.personality === "CHUBBY") imageUrl = "/static/pet_system/images/pixel_chubby_puppy.webp";
                    else if (petData.personality === "BRAVE") imageUrl = "/static/pet_system/images/pixel_star_puppy.webp";
                    else imageUrl = "/static/pet_system/images/pixel_emerald_puppy.webp";
                }
            }

            petObj.petImg.onload = () => { petObj.imgsLoaded.body = true; };
            petObj.petImg.src = imageUrl;

            // 加載頭飾
            if (petData.equipped_head) {
                petObj.accessoryImgs.head.onload = () => { petObj.imgsLoaded.head = true; };
                petObj.accessoryImgs.head.src = `/static/pet_system/images/${petData.equipped_head}.webp`;
            }
            // 加載臉飾
            if (petData.equipped_face) {
                petObj.accessoryImgs.face.onload = () => { petObj.imgsLoaded.face = true; };
                petObj.accessoryImgs.face.src = `/static/pet_system/images/${petData.equipped_face}.webp`;
            }
            // 加載背飾
            if (petData.equipped_back) {
                petObj.accessoryImgs.back.onload = () => { petObj.imgsLoaded.back = true; };
                petObj.accessoryImgs.back.src = `/static/pet_system/images/${petData.equipped_back}.webp`;
            }

            this.pets.push(petObj);
        });
    }

    handleCanvasClick(e) {
        if (this.pets.length === 0) return;
        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        
        // 從最上層(後加入)的寵物開始判定點擊
        for (let i = this.pets.length - 1; i >= 0; i--) {
            const pet = this.pets[i];
            const dist = Math.hypot(mouseX - pet.x, mouseY - pet.y);
            if (dist <= pet.radius + 15) {
                this.triggerJump(pet);
                break; // 每次點擊只觸發一隻寵物跳躍
            }
        }
    }

    triggerJump(pet) {
        if (pet.stage === 0) return; // 寵物蛋不跳躍
        if (!pet.isJumping) {
            pet.isJumping = true;
            pet.state = 'jumping';
            pet.vy = this.jumpForce;
            // 隨機旋轉
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
                
                // 落地碰撞
                if (pet.y >= this.groundY) {
                    pet.y = this.groundY;
                    pet.isJumping = false;
                    pet.vy = 0;
                    pet.rotation = 0;
                    pet.state = 'idle';
                    pet.stateTimer = 30; // 落地發呆
                }
            } else {
                // 蛋不做位移
                if (pet.stage === 0) {
                    pet.state = 'idle';
                    pet.bobOffset = Math.sin(this.breathPhase) * 2;
                    return;
                }

                // 隨機行為狀態機
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
                
                // 行走與上下顛簸
                if (pet.state === 'walking') {
                    pet.x += pet.vx;
                    pet.bobOffset = Math.sin(this.breathPhase * 2) * 3;
                    
                    // 左右牆碰撞反彈
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
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        if (this.pets.length === 0) {
            // 當前沒有未召喚的寵物
            this.ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
            this.ctx.textAlign = 'center';
            this.ctx.font = 'bold 15px "Inter", sans-serif';
            this.ctx.fillText("培育室目前空空如也", this.canvas.width / 2, this.groundY - 10);
            this.ctx.font = '12px "Inter", sans-serif';
            this.ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
            this.ctx.fillText("已召喚的出戰寵物在全網頁漫遊冒險！未出戰的寵物將會出現在這。", this.canvas.width / 2, this.groundY + 15);
            return;
        }

        // Z-Ordering 深度排序 (縱向位置越靠下的排在越後面繪製，產生前後遮擋深度感)
        const sortedPets = [...this.pets].sort((a, b) => a.y - b.y);

        sortedPets.forEach(pet => {
            // 1. 繪製微光腳底圓形陰影
            const shadowOpacity = Math.max(0.02, 0.12 - (this.groundY - pet.y) / 150);
            const shadowWidth = pet.radius * (1.1 - (this.groundY - pet.y) / 200);
            
            this.ctx.fillStyle = `rgba(0, 0, 0, ${shadowOpacity})`;
            this.ctx.beginPath();
            this.ctx.ellipse(pet.x, this.groundY + pet.radius - 8, shadowWidth, 6, 0, 0, Math.PI * 2);
            this.ctx.fill();

            if (!pet.imgsLoaded.body) {
                // 載入中轉圈圈
                this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
                this.ctx.lineWidth = 3;
                this.ctx.beginPath();
                this.ctx.arc(pet.x, pet.y, 12, this.breathPhase, this.breathPhase + Math.PI * 1.5);
                this.ctx.stroke();
                return;
            }

            // 2. 準備繪製寵物主體與裝配配件
            this.ctx.save();
            this.ctx.translate(pet.x, pet.y + pet.bobOffset);
            this.ctx.rotate(pet.rotation);
            
            if (pet.facingRight) {
                this.ctx.scale(-1, 1);
            }
            
            this.ctx.scale(pet.scaleX, pet.scaleY);
            
            // A. 背部飾品 (天使翅膀、惡魔翅膀)
            if (pet.imgsLoaded.back) {
                this.ctx.drawImage(pet.accessoryImgs.back, -pet.radius, -pet.radius, pet.radius * 2, pet.radius * 2);
            }

            // B. 身體
            this.ctx.drawImage(pet.petImg, -pet.radius, -pet.radius, pet.radius * 2, pet.radius * 2);

            // C. 面部飾品 (墨鏡)
            if (pet.imgsLoaded.face) {
                this.ctx.drawImage(pet.accessoryImgs.face, -pet.radius, -pet.radius, pet.radius * 2, pet.radius * 2);
            }

            // D. 頭部飾品 (草帽、皇冠)
            if (pet.imgsLoaded.head) {
                this.ctx.drawImage(pet.accessoryImgs.head, -pet.radius, -pet.radius, pet.radius * 2, pet.radius * 2);
            }

            this.ctx.restore();

            // 3. 繪製浮動文字標籤 (寵物名與進化形態)
            this.ctx.save();
            const textY = pet.y + pet.bobOffset - pet.radius - 12;
            
            this.ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
            this.ctx.shadowBlur = 3;
            this.ctx.shadowColor = 'rgba(0,0,0,0.1)';
            
            const labelText = `${pet.name} (${pet.stageName})`;
            this.ctx.font = 'bold 11px "Inter", sans-serif';
            const textWidth = this.ctx.measureText(labelText).width;
            
            this.ctx.beginPath();
            this.ctx.roundRect(pet.x - textWidth/2 - 8, textY - 12, textWidth + 16, 18, 8);
            this.ctx.fill();
            
            this.ctx.fillStyle = '#155724'; // 深綠字體
            this.ctx.textAlign = 'center';
            this.ctx.fillText(labelText, pet.x, textY + 1);
            this.ctx.restore();
        });
    }
}
