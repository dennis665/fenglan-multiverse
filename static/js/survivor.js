document.addEventListener('DOMContentLoaded', () => {
    // ==========================================
    // 0. 全螢幕自適應縮放機制 (完美融入各種螢幕)
    // ==========================================
    const container = document.getElementById('game-container');
    function resizeGame() {
        // 計算寬高比縮放率，讓 800x600 塞進螢幕
        const scale = Math.min(window.innerWidth / 800, window.innerHeight / 600);
        container.style.transform = `scale(${scale})`;
    }
    window.addEventListener('resize', resizeGame);
    resizeGame(); // 初始化執行

    // ==========================================
    // 0.5 全螢幕隱形浮動搖桿 (Global Swipe)
    // ==========================================
    const gameUiLayer = document.getElementById('game-ui-layer');
    let touchStartX = 0;
    let touchStartY = 0;
    let joyVec = { x: 0, y: 0 };
    let isTouching = false;

    if (gameUiLayer) {
        // 手指按下的瞬間，將該點設為虛擬搖桿的「中心點」
        gameUiLayer.addEventListener('touchstart', (e) => {
            e.preventDefault();
            const touch = e.touches[0];
            touchStartX = touch.clientX;
            touchStartY = touch.clientY;
            joyVec = { x: 0, y: 0 };
            isTouching = true;
        }, { passive: false });

        // 手指滑動時，計算與中心點的距離與角度
        gameUiLayer.addEventListener('touchmove', (e) => {
            if (!isTouching) return;
            e.preventDefault();
            const touch = e.touches[0];
            let dx = touch.clientX - touchStartX;
            let dy = touch.clientY - touchStartY;

            // 設定手指滑動多少像素(例如 40px) 角色會達到最高速
            const maxRadius = 40; 
            const distance = Math.hypot(dx, dy);

            if (distance > 0) {
                let speedFactor = Math.min(distance / maxRadius, 1.0); // 確保速度不會超過 1
                joyVec = {
                    x: (dx / distance) * speedFactor,
                    y: (dy / distance) * speedFactor
                };
            }
        }, { passive: false });

        // 手指放開，角色停止
        const endTouch = (e) => {
            e.preventDefault();
            isTouching = false;
            joyVec = { x: 0, y: 0 };
        };

        gameUiLayer.addEventListener('touchend', endTouch);
        gameUiLayer.addEventListener('touchcancel', endTouch);
    }

    // ==========================================
    // 1. 基礎設定與 DOM 元素獲取
    // ==========================================
    const csrfToken = document.getElementById('csrfToken').value;

    const lobbyScreen = document.getElementById('lobby-screen');
    const gameContainer = document.getElementById('game-container');
    const hpBar = document.getElementById('hp-bar');
    const xpBar = document.getElementById('xp-bar');
    const levelVal = document.getElementById('level-val');
    const timeVal = document.getElementById('time-val');
    const killVal = document.getElementById('kill-val');

    // ==========================================
    // 2. 關卡與圖鑑資料載入
    // ==========================================
    const levels = JSON.parse(document.getElementById('levelsData').textContent);
    const dbMonsters = JSON.parse(document.getElementById('monstersData').textContent);
    let currentLevel = levels[0];

    // 動態生成關卡選單
    const levelSelect = document.getElementById('levelSelect');
    levels.forEach(lvl => {
        let opt = document.createElement('option');
        opt.value = lvl.id;
        opt.textContent = `${lvl.name} (🕒 ${lvl.time_limit}秒 | 💰 獎勵 ${lvl.win_bonus}G)`;
        levelSelect.appendChild(opt);
    });
    levelSelect.addEventListener('change', (e) => {
        currentLevel = levels.find(l => l.id == e.target.value) || levels[0];
    });

    // 預先載入圖片資源 (玩家大頭貼 & 怪物圖鑑)
    const imageCache = {};
    const playerAvatarUrl = document.getElementById('playerAvatarUrl').value;
    const playerImg = new Image();
    if (playerAvatarUrl) playerImg.src = playerAvatarUrl;

    dbMonsters.forEach(m => {
        if (m.img_url) {
            const img = new Image();
            img.src = m.img_url;
            imageCache[m.id] = img;
        }
    });

    // ==========================================
    // 3. 大廳升級與購買邏輯
    // ==========================================
    const updateCosts = () => {
        ['hp', 'atk', 'speed'].forEach(type => {
            const lvl = parseInt(document.getElementById(`lbl-${type}-lvl`).innerText);
            document.getElementById(`cost-${type}`).innerText = (lvl + 1) * 50;
        });
    };
    updateCosts();

    document.querySelectorAll('.btn-buy').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const type = e.target.dataset.type;
            try {
                const response = await fetch('/games/api/survivor/upgrade/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                    body: JSON.stringify({ upgrade_type: type })
                });
                const data = await response.json();
                if (data.status === 'success') {
                    document.getElementById(`lbl-${type}-lvl`).innerText = data.new_level;
                    document.getElementById('display-coins').innerText = data.remaining_coins;
                    document.getElementById(`base${type.charAt(0).toUpperCase() + type.slice(1)}Level`).value = data.new_level;
                    updateCosts();
                } else {
                    alert(data.message);
                }
            } catch (err) { console.error('Upgrade Error:', err); }
        });
    });

    // ==========================================
    // 4. 遊戲引擎與控制設定
    // ==========================================
    const keys = {};
    window.addEventListener('keydown', e => {
        if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Space"].includes(e.code)) e.preventDefault();

        // 按下 P 或 Esc 可以快速暫停
        if (e.code === 'KeyP' || e.code === 'Escape') {
            togglePause();
        }

        keys[e.code] = true;
    });
    window.addEventListener('keyup', e => keys[e.code] = false);

    const canvas = document.getElementById('gameCanvas');
    const ctx = canvas.getContext('2d');
    canvas.width = 800;
    canvas.height = 600;

    let gameState = 'stopped';
    let gameTime = 0, killCount = 0, lastEnemySpawnTime = 0;
    let player, enemies, projectiles, expGems, startTime, lastTime, pauseStartTime = 0;

    // ==========================================
    // 5. 類別定義：玩家 (Player)
    // ==========================================
    class Player {
        constructor() {
            this.x = canvas.width / 2;
            this.y = canvas.height / 2;
            this.radius = 12;

            // 套用局外成長數值
            const baseHpLvl = parseInt(document.getElementById('baseHpLevel').value) || 0;
            const baseAtkLvl = parseInt(document.getElementById('baseAtkLevel').value) || 0;
            const baseSpeedLvl = parseInt(document.getElementById('baseSpeedLevel').value) || 0;

            this.maxHp = 100 + (baseHpLvl * 20);
            this.hp = this.maxHp;
            this.atkPower = 10 + (baseAtkLvl * 2);
            this.speed = 3 + (baseSpeedLvl * 0.3);

            this.level = 1;
            this.xp = 0;
            this.xpToNext = 10;

            this.weapons = [{ cd: 600, lastShot: 0, damage: 15 }];
            this.isDead = false;
            this.hitCooldown = 0; // 受傷無敵冷卻

            // 🚀 新增多發射擊機率
            this.multishotChance = 0.0;
        }

        update() {
            let dx = 0, dy = 0;
            if (keys['ArrowUp'] || keys['KeyW']) dy -= 1;
            if (keys['ArrowDown'] || keys['KeyS']) dy += 1;
            if (keys['ArrowLeft'] || keys['KeyA']) dx -= 1;
            if (keys['ArrowRight'] || keys['KeyD']) dx += 1;

            // 整合搖桿輸入 (如果搖桿有動，就覆蓋鍵盤)
            if (joyVec.x !== 0 || joyVec.y !== 0) {
                dx = joyVec.x;
                dy = joyVec.y;
            }

            if (dx !== 0 || dy !== 0) {
                // 如果是鍵盤輸入，需要標準化 (避免斜走變快)
                // 但如果是搖桿，已經是平滑的 0~1 向量，就不用硬性標準化為 1
                const mag = Math.hypot(dx, dy);
                if (mag > 1) { 
                    dx /= mag; dy /= mag; 
                }
                this.x += dx * this.speed;
                this.y += dy * this.speed;
            }

            // 邊界限制
            this.x = Math.max(this.radius, Math.min(canvas.width - this.radius, this.x));
            this.y = Math.max(this.radius, Math.min(canvas.height - this.radius, this.y));

            // 無敵冷卻遞減
            if (this.hitCooldown > 0) this.hitCooldown--;

            this.autoAttack();
        }

        autoAttack() {
            const now = Date.now();
            this.weapons.forEach(w => {
                if (now - w.lastShot > w.cd) {
                    let target = null, minDist = 400;
                    enemies.forEach(e => {
                        const d = Math.hypot(e.x - this.x, e.y - this.y);
                        if (d < minDist) { minDist = d; target = e; }
                    });

                    if (target) {
                        const angle = Math.atan2(target.y - this.y, target.x - this.x);

                        // 發射第一發子彈
                        projectiles.push({
                            x: this.x, y: this.y,
                            vx: Math.cos(angle) * 8, vy: Math.sin(angle) * 8,
                            damage: w.damage + this.atkPower, active: true
                        });

                        // 🚀 判定多重射擊機率發射第二發 (稍微偏移角度)
                        if (Math.random() < this.multishotChance) {
                            const angle2 = angle + 0.26; // 約 15 度
                            projectiles.push({
                                x: this.x, y: this.y,
                                vx: Math.cos(angle2) * 8, vy: Math.sin(angle2) * 8,
                                damage: w.damage + this.atkPower, active: true
                            });
                        }

                        w.lastShot = now;
                    }
                }
            });
        }

        draw() {
            ctx.save();
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);

            // 有大頭貼就裁切繪製，沒有就畫綠點
            if (playerImg.src && playerImg.complete) {
                ctx.clip();
                ctx.drawImage(playerImg, this.x - this.radius, this.y - this.radius, this.radius * 2, this.radius * 2);
            } else {
                ctx.fillStyle = (this.hitCooldown > 0 && Math.floor(Date.now() / 100) % 2) ? 'white' : '#4caf50';
                ctx.fill();
            }

            ctx.lineWidth = 2;
            ctx.strokeStyle = '#fff';
            ctx.stroke();
            ctx.restore();
        }

        takeDamage(amount) {
            if (this.isDead || this.hitCooldown > 0) return;
            this.hp -= amount;
            this.hitCooldown = 15;

            if (this.hp <= 0 && !this.isDead) {
                this.hp = 0;
                this.isDead = true;
                triggerGameOver();
            }
        }

        gainXp(amount) {
            this.xp += amount;
            if (this.xp >= this.xpToNext) {
                this.level++;
                this.xp -= this.xpToNext;
                this.xpToNext = Math.floor(this.xpToNext * 1.5);
                triggerLevelUp();
            }
        }
    }

    // ==========================================
    // 6. 類別定義：怪物 (Enemy)
    // ==========================================
    class Enemy {
        constructor() {
            const template = dbMonsters.length > 0 ? dbMonsters[Math.floor(Math.random() * dbMonsters.length)] : null;

            this.dbId = template ? template.id : null;
            this.radius = template ? template.size : 12;

            // 套用關卡難度倍率
            this.speed = ((template ? template.speed : 1.5) + Math.random() * 0.5) * currentLevel.stat_mult;
            this.hp = (template ? template.hp : 10) * currentLevel.stat_mult;
            this.damage = (template ? template.atk : 5) * currentLevel.stat_mult;
            this.active = true;

            const edge = Math.floor(Math.random() * 4);
            if (edge === 0) { this.x = Math.random() * canvas.width; this.y = -20; }
            else if (edge === 1) { this.x = canvas.width + 20; this.y = Math.random() * canvas.height; }
            else if (edge === 2) { this.x = Math.random() * canvas.width; this.y = canvas.height + 20; }
            else { this.x = -20; this.y = Math.random() * canvas.height; }
        }

        draw() {
            ctx.save();
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);

            if (this.dbId && imageCache[this.dbId] && imageCache[this.dbId].complete) {
                ctx.clip();
                ctx.drawImage(imageCache[this.dbId], this.x - this.radius, this.y - this.radius, this.radius * 2, this.radius * 2);
            } else {
                ctx.fillStyle = '#f44336';
                ctx.fill();
            }
            ctx.restore();
        }
    }

    // ==========================================
    // 7. 核心遊戲流程
    // ==========================================
    function initGame() {
        player = new Player();
        enemies = [];
        projectiles = [];
        expGems = [];
        killCount = 0;
        startTime = Date.now();
        lastTime = startTime;
        gameState = 'playing';

        updateUI();
        requestAnimationFrame(gameLoop);
    }

    function updateUI() {
        if (!player) return;
        hpBar.style.width = `${Math.max(0, (player.hp / player.maxHp) * 100)}%`;
        xpBar.style.width = `${Math.max(0, (player.xp / player.xpToNext) * 100)}%`;
        levelVal.innerText = player.level;
        killVal.innerText = killCount;

        const mins = Math.floor(gameTime / 60).toString().padStart(2, '0');
        const secs = Math.floor(gameTime % 60).toString().padStart(2, '0');
        timeVal.innerText = `${mins}:${secs}`;
    }

    function gameLoop() {
        if (gameState !== 'playing') return;

        const now = Date.now();
        gameTime = Math.floor((now - startTime) / 1000);

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // --- 破關判定 ---
        if (gameTime >= currentLevel.time_limit) {
            triggerWin();
            return;
        }

        // --- 怪物生成 ---
        let spawnInterval = (1500 / currentLevel.spawn_rate_mult) - (gameTime * 5);
        if (enemies.length < 100 && now - lastEnemySpawnTime > Math.max(200, spawnInterval)) {
            enemies.push(new Enemy());
            lastEnemySpawnTime = now;
        }

        // --- 玩家更新 ---
        player.update();
        player.draw();

        // --- 經驗寶石邏輯 ---
        expGems.forEach(gem => {
            if (!gem.active) return;
            const dist = Math.hypot(player.x - gem.x, player.y - gem.y);

            // 磁鐵吸收
            if (dist < 100) {
                const angle = Math.atan2(player.y - gem.y, player.x - gem.x);
                gem.x += Math.cos(angle) * 7;
                gem.y += Math.sin(angle) * 7;
            }

            // 吃到寶石
            if (dist < player.radius + 8) {
                gem.active = false;
                player.gainXp(5);
            } else {
                ctx.fillStyle = '#4da6ff';
                ctx.beginPath(); ctx.arc(gem.x, gem.y, 4, 0, Math.PI * 2); ctx.fill();
            }
        });

        // --- 子彈邏輯 ---
        projectiles.forEach(p => {
            p.x += p.vx; p.y += p.vy;
            ctx.fillStyle = 'yellow';
            ctx.beginPath(); ctx.arc(p.x, p.y, 4, 0, Math.PI * 2); ctx.fill();

            enemies.forEach(e => {
                if (p.active && e.active && Math.hypot(p.x - e.x, p.y - e.y) < e.radius + 4) {
                    e.hp -= p.damage;
                    p.active = false;
                    if (e.hp <= 0) {
                        e.active = false;
                        killCount++;
                        // 70% 機率掉落寶石
                        if (Math.random() > 0.3) expGems.push({ x: e.x, y: e.y, active: true });
                    }
                }
            });
            if (p.x < 0 || p.x > canvas.width || p.y < 0 || p.y > canvas.height) p.active = false;
        });

        // --- 怪物移動與攻擊 ---
        enemies.forEach(e => {
            if (!e.active) return;
            const ang = Math.atan2(player.y - e.y, player.x - e.x);
            e.x += Math.cos(ang) * e.speed;
            e.y += Math.sin(ang) * e.speed;

            e.draw(); // 使用圖鑑內的圖或預設紅圈

            // 撞擊玩家
            if (!player.isDead && Math.hypot(player.x - e.x, player.y - e.y) < player.radius + e.radius) {
                player.takeDamage(e.damage);
            }
        });

        // --- 陣列清理 (非常重要，防止卡死) ---
        enemies = enemies.filter(e => e.active);
        projectiles = projectiles.filter(p => p.active);
        expGems = expGems.filter(g => g.active);

        updateUI();
        requestAnimationFrame(gameLoop);
    }

    // ==========================================
    // 8. 狀態切換與結算函式
    // ==========================================

    // 🚀 全域的升級池設定
    const UPGRADE_POOL = [
        { id: 'hp', name: '急救包', desc: '恢復 30% 最大生命', color: 'success' },
        { id: 'atk', name: '攻擊強化', desc: '攻擊力 +2', color: 'danger' },
        { id: 'cd', name: '攻速提升', desc: '射擊間隔 -10%', color: 'info' },
        { id: 'multishot', name: '雙重射擊', desc: '連射兩發機率 +15%', color: 'warning' },
        { id: 'speed', name: '輕盈步伐', desc: '移動速度 +5%', color: 'primary' },
        { id: 'maxhp', name: '強健體魄', desc: '血量上限 +20', color: 'secondary' }
    ];

    // 切換暫停狀態邏輯
    window.togglePause = function() {
        // 只能在「遊玩中」或「暫停中」切換，避免在升級或死亡畫面亂按
        if (gameState === 'playing') {
            gameState = 'paused';
            pauseStartTime = Date.now();
            document.getElementById('pause-screen').classList.add('active');
            document.getElementById('btn-pause').innerHTML = '<i class="fas fa-play fs-6"></i>';
        } 
        else if (gameState === 'paused') {
            gameState = 'playing';

            // 校正時間差，讓遊戲完美接續
            const pauseDuration = Date.now() - pauseStartTime;
            startTime += pauseDuration;
            lastEnemySpawnTime += pauseDuration;

            document.getElementById('pause-screen').classList.remove('active');
            document.getElementById('btn-pause').innerHTML = '<i class="fas fa-pause fs-6"></i>';
            requestAnimationFrame(gameLoop);
        }
    };

    function triggerLevelUp() {
        gameState = 'leveling';
        lastTime = Date.now(); // 記錄進入升級選單的時刻

        // 洗牌並抽出 3 個隨機選項
        const shuffled = [...UPGRADE_POOL].sort(() => 0.5 - Math.random());
        const selectedOptions = shuffled.slice(0, 3);

        const container = document.getElementById('upgrade-options-container');
        container.innerHTML = '';

        selectedOptions.forEach(opt => {
            container.innerHTML += `
                <div class="upgrade-card bg-dark text-white p-3 border border-secondary rounded text-center shadow-lg" style="cursor:pointer; width: 220px;" onclick="applyInGameUpgrade('${opt.id}')">
                    <h4 class="text-${opt.color} fw-bold mt-2 mb-2">${opt.name}</h4>
                    <p class="text-light fs-6 mb-0" style="letter-spacing: 1px;">${opt.desc}</p>
                </div>
            `;
        });

        document.getElementById('upgrade-screen').classList.add('active');
    }

    // 🚀 套用升級效果
    window.applyInGameUpgrade = function (type) {
        if (type === 'hp') {
            player.hp = Math.min(player.maxHp, player.hp + player.maxHp * 0.3);
        }
        if (type === 'atk') player.atkPower += 2;
        if (type === 'cd') player.weapons[0].cd *= 0.9;
        if (type === 'multishot') player.multishotChance += 0.15;
        if (type === 'speed') player.speed *= 1.05;
        if (type === 'maxhp') player.maxHp += 20;

        document.getElementById('upgrade-screen').classList.remove('active');
        gameState = 'playing';

        // 校正時間差，讓遊戲完美接續
        const pauseDuration = Date.now() - lastTime;
        startTime += pauseDuration;
        lastEnemySpawnTime += pauseDuration;

        requestAnimationFrame(gameLoop);
    };

    async function triggerGameOver() {
        gameState = 'gameover';
        const screen = document.getElementById('gameover-screen');
        screen.classList.add('active');
        screen.querySelector('h1').innerText = "存活失敗";
        screen.querySelector('h1').className = "text-danger display-3 fw-bold mb-3";
        document.getElementById('final-stats').innerText = `生存時間: ${gameTime}秒 | 擊殺: ${killCount}`;

        await sendGameResult(false, 0);
    }

    async function triggerWin() {
        gameState = 'win';
        const screen = document.getElementById('gameover-screen');
        screen.classList.add('active');
        screen.querySelector('h1').innerText = "🎉 關卡破關！";
        screen.querySelector('h1').className = "text-success display-3 fw-bold mb-3";
        document.getElementById('final-stats').innerText = `存活: ${gameTime}秒 | 擊殺: ${killCount} | 獎勵: ${currentLevel.win_bonus}G`;

        await sendGameResult(true, currentLevel.win_bonus);
    }

    async function sendGameResult(isWin, winBonus) {
        try {
            const response = await fetch('/games/api/survivor/save/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({
                    time: gameTime, level: player.level, kills: killCount,
                    is_win: isWin, win_bonus: winBonus
                })
            });
            const data = await response.json();
            if (data.status === 'success') {
                document.getElementById('reward-stats').innerText = `結算獲得金幣: +${data.earned_coins} (目前總額: ${data.total_coins})`;
                if (data.is_new_record) document.getElementById('reward-stats').innerText += ' 🏆 新存活紀錄！';
            }
        } catch (err) { console.error('紀錄上傳失敗', err); }
    }

    // ==========================================
    // 9. 按鈕綁定
    // ==========================================
    // 大廳按鈕啟動邏輯修改 (要把 UI Layer 叫出來)
    document.getElementById('btn-start-game').addEventListener('click', () => {
        document.getElementById('lobby-screen').classList.remove('active');
        document.getElementById('game-ui-layer').classList.remove('d-none');
        initGame();
    });

    document.getElementById('btn-return-lobby').addEventListener('click', () => location.reload());

    // 暫停按鈕事件綁定
    const btnPause = document.getElementById('btn-pause');
    const btnResume = document.getElementById('btn-resume');
    if (btnPause) btnPause.addEventListener('click', togglePause);
    if (btnResume) btnResume.addEventListener('click', togglePause);
});