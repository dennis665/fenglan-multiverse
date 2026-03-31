// survivor.js
document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('gameCanvas');
    const ctx = canvas.getContext('2d');

    // ==========================================
    // 0. 原生全螢幕畫布重置
    // ==========================================
    function resizeGame() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    window.addEventListener('resize', resizeGame);
    window.addEventListener('orientationchange', () => setTimeout(resizeGame, 100));
    resizeGame();

    // ==========================================
    // 0.5 全螢幕隱形浮動搖桿
    // ==========================================
    const gameUiLayer = document.getElementById('game-ui-layer');
    let touchStartX = 0, touchStartY = 0;
    let joyVec = { x: 0, y: 0 };
    let isTouching = false;

    if (gameUiLayer) {
        gameUiLayer.addEventListener('touchstart', (e) => {
            e.preventDefault();
            const touch = e.touches[0];
            touchStartX = touch.clientX;
            touchStartY = touch.clientY;
            joyVec = { x: 0, y: 0 };
            isTouching = true;
        }, { passive: false });

        gameUiLayer.addEventListener('touchmove', (e) => {
            if (!isTouching) return;
            e.preventDefault();
            const touch = e.touches[0];
            let dx = touch.clientX - touchStartX;
            let dy = touch.clientY - touchStartY;
            const maxRadius = 40; 
            const distance = Math.hypot(dx, dy);

            if (distance > 0) {
                let speedFactor = Math.min(distance / maxRadius, 1.0);
                joyVec = { x: (dx / distance) * speedFactor, y: (dy / distance) * speedFactor };
            }
        }, { passive: false });

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
    const hpBar = document.getElementById('hp-bar');
    const xpBar = document.getElementById('xp-bar');
    const levelVal = document.getElementById('level-val');
    const timeVal = document.getElementById('time-val');
    const killVal = document.getElementById('kill-val');

    const levels = JSON.parse(document.getElementById('levelsData').textContent);
    const dbMonsters = JSON.parse(document.getElementById('monstersData').textContent);
    let currentLevel = levels[0];

    const levelSelect = document.getElementById('levelSelect');
    levels.forEach(lvl => {
        let opt = document.createElement('option');
        opt.value = lvl.id;
        opt.textContent = `${lvl.name} (🕒 ${lvl.time_limit}秒 | 💰 ${lvl.win_bonus}G)`;
        levelSelect.appendChild(opt);
    });
    levelSelect.addEventListener('change', (e) => {
        currentLevel = levels.find(l => l.id == e.target.value) || levels[0];
    });

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
    // 3. 大廳升級邏輯
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
                } else { alert(data.message); }
            } catch (err) { console.error('Upgrade Error:', err); }
        });
    });

    // ==========================================
    // 4. 遊戲引擎基礎變數
    // ==========================================
    const keys = {};
    window.addEventListener('keydown', e => {
        if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Space"].includes(e.code)) e.preventDefault();
        if (e.code === 'KeyP' || e.code === 'Escape') togglePause();
        keys[e.code] = true;
    });
    window.addEventListener('keyup', e => keys[e.code] = false);

    let gameState = 'stopped';
    let gameTime = 0, killCount = 0, lastEnemySpawnTime = 0;
    let player, enemies, projectiles, expGems, startTime, lastTime, pauseStartTime = 0;

    // ==========================================
    // 5. 類別定義：玩家 (Player) 支援屬性分區
    // ==========================================
    class Player {
        constructor() {
            this.x = canvas.width / 2;
            this.y = canvas.height / 2;
            this.radius = 12;

            const outHpLvl = parseInt(document.getElementById('baseHpLevel').value) || 0;
            const outAtkLvl = parseInt(document.getElementById('baseAtkLevel').value) || 0;
            const outSpeedLvl = parseInt(document.getElementById('baseSpeedLevel').value) || 0;

            // 🚀 分區記錄：基礎(base) / 局外(out) / 局內(in)
            // 將移速(moveSpeed)與攻速(atkSpeed)明確拆分
            this.baseStats = { hp: 100, atk: 10, moveSpeed: 3.0, atkSpeed: 1.0, multishot: 0 };
            this.outStats =  { hp: outHpLvl * 20, atk: outAtkLvl * 2, moveSpeed: outSpeedLvl * 0.3, atkSpeed: 0, multishot: 0 };
            
            // 局內的移速採用乘法倍率(1.0起跳)，攻速採用百分比加成(0.15代表+15%)
            this.inStats =   { hp: 0, atk: 0, moveSpeedMult: 1.0, atkSpeedAdd: 0, multishot: 0 }; 

            // 武器改為記錄 baseCD，實際 CD 會由攻速計算
            this.weapons = [{ baseCD: 600, lastShot: 0, damage: 15 }];
            
            this.calcStats();
            this.hp = this.maxHp;
            
            this.level = 1;
            this.xp = 0;
            this.xpToNext = 10;
            this.isDead = false;
            this.hitCooldown = 0;
        }

        // 計算當前總屬性
        calcStats() {
            this.maxHp = this.baseStats.hp + this.outStats.hp + this.inStats.hp;
            this.atkPower = this.baseStats.atk + this.outStats.atk + this.inStats.atk;
            this.moveSpeed = (this.baseStats.moveSpeed + this.outStats.moveSpeed) * this.inStats.moveSpeedMult;
            this.atkSpeed = this.baseStats.atkSpeed + this.outStats.atkSpeed + this.inStats.atkSpeedAdd;
            this.multishotChance = this.baseStats.multishot + this.outStats.multishot + this.inStats.multishot;
        }

        update() {
            let dx = 0, dy = 0;
            if (keys['ArrowUp'] || keys['KeyW']) dy -= 1;
            if (keys['ArrowDown'] || keys['KeyS']) dy += 1;
            if (keys['ArrowLeft'] || keys['KeyA']) dx -= 1;
            if (keys['ArrowRight'] || keys['KeyD']) dx += 1;

            if (joyVec.x !== 0 || joyVec.y !== 0) {
                dx = joyVec.x; dy = joyVec.y;
            }

            if (dx !== 0 || dy !== 0) {
                const mag = Math.hypot(dx, dy);
                if (mag > 1) { dx /= mag; dy /= mag; }
                this.x += dx * this.moveSpeed;
                this.y += dy * this.moveSpeed;
            }

            this.x = Math.max(this.radius, Math.min(canvas.width - this.radius, this.x));
            this.y = Math.max(this.radius, Math.min(canvas.height - this.radius, this.y));

            if (this.hitCooldown > 0) this.hitCooldown--;
            this.autoAttack();
        }

        autoAttack() {
            const now = Date.now();
            this.weapons.forEach(w => {
                // 🚀 動態計算當前冷卻時間：基礎冷卻 / 攻擊速度比例
                // 例如 600ms / 1.15 = 521ms (變快)
                const currentCD = w.baseCD / this.atkSpeed;

                if (now - w.lastShot > currentCD) {
                    let target = null, minDist = Math.max(canvas.width, canvas.height);
                    enemies.forEach(e => {
                        const d = Math.hypot(e.x - this.x, e.y - this.y);
                        if (d < minDist) { minDist = d; target = e; }
                    });

                    if (target) {
                        const angle = Math.atan2(target.y - this.y, target.x - this.x);
                        projectiles.push({
                            x: this.x, y: this.y,
                            vx: Math.cos(angle) * 8, vy: Math.sin(angle) * 8,
                            damage: w.damage + this.atkPower, active: true
                        });

                        if (Math.random() < this.multishotChance) {
                            const angle2 = angle + 0.26;
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

        if (gameTime >= currentLevel.time_limit) {
            triggerWin();
            return;
        }

        let spawnInterval = (1500 / currentLevel.spawn_rate_mult) - (gameTime * 5);
        if (enemies.length < 120 && now - lastEnemySpawnTime > Math.max(150, spawnInterval)) {
            enemies.push(new Enemy());
            lastEnemySpawnTime = now;
        }

        player.update();
        player.draw();

        expGems.forEach(gem => {
            if (!gem.active) return;
            const dist = Math.hypot(player.x - gem.x, player.y - gem.y);

            if (dist < 120) {
                const angle = Math.atan2(player.y - gem.y, player.x - gem.x);
                gem.x += Math.cos(angle) * 7;
                gem.y += Math.sin(angle) * 7;
            }

            if (dist < player.radius + 10) {
                gem.active = false;
                player.gainXp(5);
            } else {
                ctx.fillStyle = '#4da6ff';
                ctx.beginPath(); ctx.arc(gem.x, gem.y, 4, 0, Math.PI * 2); ctx.fill();
            }
        });

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
                        if (Math.random() > 0.3) expGems.push({ x: e.x, y: e.y, active: true });
                    }
                }
            });
            if (p.x < 0 || p.x > canvas.width || p.y < 0 || p.y > canvas.height) p.active = false;
        });

        enemies.forEach(e => {
            if (!e.active) return;
            const ang = Math.atan2(player.y - e.y, player.x - e.x);
            e.x += Math.cos(ang) * e.speed;
            e.y += Math.sin(ang) * e.speed;

            e.draw();

            if (!player.isDead && Math.hypot(player.x - e.x, player.y - e.y) < player.radius + e.radius) {
                player.takeDamage(e.damage);
            }
        });

        enemies = enemies.filter(e => e.active);
        projectiles = projectiles.filter(p => p.active);
        expGems = expGems.filter(g => g.active);

        updateUI();
        requestAnimationFrame(gameLoop);
    }

    // ==========================================
    // 8. 升級與 UI 控制
    // ==========================================
    const UPGRADE_POOL = [
        { id: 'hp', name: '急救包', desc: '恢復 30% 最大生命', color: 'success' },
        { id: 'atk', name: '攻擊強化', desc: '攻擊力 +2', color: 'danger' },
        { id: 'cd', name: '攻速提升', desc: '攻擊速度 +15%', color: 'info' }, // 🚀 文字修正為攻擊速度
        { id: 'multishot', name: '雙重射擊', desc: '連射兩發機率 +15%', color: 'warning' },
        { id: 'speed', name: '輕盈步伐', desc: '移動速度 +5%', color: 'primary' },
        { id: 'maxhp', name: '強健體魄', desc: '血量上限 +20', color: 'secondary' }
    ];

    window.togglePause = function() {
        if (gameState === 'playing') {
            gameState = 'paused';
            pauseStartTime = Date.now();
            
            if (player) {
                const b = player.baseStats, o = player.outStats, i = player.inStats;
                
                // HP
                document.getElementById('d-base-hp').innerText = b.hp;
                document.getElementById('d-out-hp').innerText = `+${o.hp}`;
                document.getElementById('d-in-hp').innerText = `+${i.hp}`;
                document.getElementById('d-total-hp').innerText = player.maxHp;
                
                // ATK
                document.getElementById('d-base-atk').innerText = b.atk;
                document.getElementById('d-out-atk').innerText = `+${o.atk}`;
                document.getElementById('d-in-atk').innerText = `+${i.atk}`;
                document.getElementById('d-total-atk').innerText = player.atkPower;
                
                // MOVE SPEED
                document.getElementById('d-base-spd').innerText = b.moveSpeed.toFixed(1);
                document.getElementById('d-out-spd').innerText = `+${o.moveSpeed.toFixed(1)}`;
                document.getElementById('d-in-spd').innerText = `x${i.moveSpeedMult.toFixed(2)}`;
                document.getElementById('d-total-spd').innerText = player.moveSpeed.toFixed(1);
                
                // 🚀 ATTACK SPEED (轉換為百分比顯示)
                document.getElementById('d-base-atkspd').innerText = `${Math.round(b.atkSpeed * 100)}%`;
                document.getElementById('d-out-atkspd').innerText = `+${Math.round(o.atkSpeed * 100)}%`;
                document.getElementById('d-in-atkspd').innerText = `+${Math.round(i.atkSpeedAdd * 100)}%`;
                document.getElementById('d-total-atkspd').innerText = `${Math.round(player.atkSpeed * 100)}%`;

                // MULTISHOT
                document.getElementById('d-base-multi').innerText = `${b.multishot * 100}%`;
                document.getElementById('d-out-multi').innerText = `+${o.multishot * 100}%`;
                document.getElementById('d-in-multi').innerText = `+${Math.round(i.multishot * 100)}%`;
                document.getElementById('d-total-multi').innerText = `${Math.round(player.multishotChance * 100)}%`;
            }

            document.getElementById('pause-screen').classList.add('active');
            document.getElementById('btn-pause').innerHTML = '<i class="fas fa-play fs-5 text-white"></i>';
        } 
        else if (gameState === 'paused') {
            gameState = 'playing';
            const pauseDuration = Date.now() - pauseStartTime;
            startTime += pauseDuration;
            lastEnemySpawnTime += pauseDuration;

            document.getElementById('pause-screen').classList.remove('active');
            document.getElementById('btn-pause').innerHTML = '<i class="fas fa-pause fs-5 text-white"></i>';
            requestAnimationFrame(gameLoop);
        }
    };

    function triggerLevelUp() {
        gameState = 'leveling';
        lastTime = Date.now(); 

        const shuffled = [...UPGRADE_POOL].sort(() => 0.5 - Math.random());
        const selectedOptions = shuffled.slice(0, 3);
        const container = document.getElementById('upgrade-options-container');
        container.innerHTML = '';

        selectedOptions.forEach(opt => {
            container.innerHTML += `
                <div class="upgrade-card bg-dark text-white p-3 border border-secondary rounded shadow-lg" onclick="applyInGameUpgrade('${opt.id}')">
                    <h5 class="text-${opt.color} fw-bold mt-1 mb-2">${opt.name}</h5>
                    <p class="text-light small mb-0">${opt.desc}</p>
                </div>
            `;
        });
        document.getElementById('upgrade-screen').classList.add('active');
    }

    // 套用升級效果
    window.applyInGameUpgrade = function (type) {
        if (type === 'atk') player.inStats.atk += 2;
        if (type === 'cd') player.inStats.atkSpeedAdd += 0.15; // 🚀 攻速 +15%
        if (type === 'multishot') player.inStats.multishot += 0.15;
        if (type === 'speed') player.inStats.moveSpeedMult *= 1.05; // 移速 x1.05
        if (type === 'maxhp') player.inStats.hp += 20;
        
        player.calcStats();
        
        if (type === 'hp') {
            player.hp = Math.min(player.maxHp, player.hp + player.maxHp * 0.3);
        }

        document.getElementById('upgrade-screen').classList.remove('active');
        gameState = 'playing';

        const pauseDuration = Date.now() - lastTime;
        startTime += pauseDuration;
        lastEnemySpawnTime += pauseDuration;
        requestAnimationFrame(gameLoop);
    };

    // ==========================================
    // 9. 結算與按鈕事件
    // ==========================================
    async function triggerGameOver() {
        gameState = 'gameover';
        const screen = document.getElementById('gameover-screen');
        screen.classList.add('active');
        screen.querySelector('h1').innerText = "存活失敗";
        screen.querySelector('h1').className = "text-danger display-4 fw-bold mb-3";
        document.getElementById('final-stats').innerText = `生存時間: ${gameTime}秒 | 擊殺: ${killCount}`;
        await sendGameResult(false, 0);
    }

    async function triggerWin() {
        gameState = 'win';
        const screen = document.getElementById('gameover-screen');
        screen.classList.add('active');
        screen.querySelector('h1').innerText = "🎉 關卡破關！";
        screen.querySelector('h1').className = "text-success display-4 fw-bold mb-3";
        document.getElementById('final-stats').innerText = `存活: ${gameTime}秒 | 擊殺: ${killCount} | 獎勵: ${currentLevel.win_bonus}G`;
        await sendGameResult(true, currentLevel.win_bonus);
    }

    async function sendGameResult(isWin, winBonus) {
        try {
            const response = await fetch('/games/api/survivor/save/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ time: gameTime, level: player.level, kills: killCount, is_win: isWin, win_bonus: winBonus })
            });
            const data = await response.json();
            if (data.status === 'success') {
                document.getElementById('reward-stats').innerText = `金幣: +${data.earned_coins} (總額: ${data.total_coins})`;
                if (data.is_new_record) document.getElementById('reward-stats').innerText += '\n🏆 新存活紀錄！';
            }
        } catch (err) { console.error('紀錄上傳失敗', err); }
    }

    document.getElementById('btn-start-game').addEventListener('click', () => {
        document.getElementById('lobby-screen').classList.remove('active');
        document.getElementById('game-ui-layer').classList.remove('d-none');
        initGame();
    });
    document.getElementById('btn-return-lobby').addEventListener('click', () => location.reload());

    const bindMenuButton = (element, callback) => {
        if (!element) return;
        const execute = (e) => { e.preventDefault(); e.stopPropagation(); callback(); };
        element.addEventListener('click', execute);
        element.addEventListener('touchend', execute);
    };

    bindMenuButton(document.getElementById('btn-pause'), togglePause);
    bindMenuButton(document.getElementById('btn-resume'), togglePause);
    bindMenuButton(document.getElementById('btn-quit'), () => {
        gameState = 'stopped';
        window.location.reload();
    });
});