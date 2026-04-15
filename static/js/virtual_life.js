// virtual_life.js
document.addEventListener('DOMContentLoaded', () => {
    // UI 綁定 - 大廳與遊戲畫面
    const lobbyScreen = document.getElementById('lobby-screen'); //* 大廳畫面
    const gameScreen = document.getElementById('game-screen'); //* 遊戲畫面
    const btnStart = document.getElementById('btn-start-game'); //* 開始按鈕

    // UI 綁定 - 遊戲內部
    const btnRoll = document.getElementById('btn-roll');
    const diceDisplay = document.getElementById('dice-result');
    const logList = document.getElementById('log-list');
    const boardContainer = document.getElementById('game-board');
    const modal = document.getElementById('action-modal');
    const modalTitle = document.getElementById('modal-title');
    const modalDesc = document.getElementById('modal-desc');
    const modalActions = document.getElementById('modal-actions');
    const monsterHpDisplay = document.getElementById('monster-hp');
    const modalCombatStats = document.getElementById('modal-combat-stats');

    // 在 Modal 內建立戰鬥日誌容器
    const modalLog = document.createElement('ul');
    modalLog.id = 'modal-log';
    modalLog.className = 'text-start list-unstyled small p-2 mt-2 overflow-auto bg-black rounded';
    modalLog.style.maxHeight = '120px';
    modalDesc.parentNode.insertBefore(modalLog, modalCombatStats.nextSibling);

    let isRolling = false;
    let pathCells = [];
    let currentPosIndex = 0;

    // 角色屬性 (整合大廳的初始值)
    let player = {
        level: CSI_CONFIG.currentLevel,
        hpLv: CSI_CONFIG.baseHpLv,
        atkLv: CSI_CONFIG.baseAtkLv,
        coins: CSI_CONFIG.totalCoins,
        maxHp: 100 + (CSI_CONFIG.baseHpLv * 20),
        hp: 100 + (CSI_CONFIG.baseHpLv * 20),
        atkBase: 10 + (CSI_CONFIG.baseAtkLv * 2),
        potions: 2,
        turnsUntilBoss: 15,
        sessionCoins: 0
    };

    const delay = (ms) => new Promise(res => setTimeout(res, ms));

    // ==========================================
    // 1. 局外大廳邏輯 (升級與開始遊戲)
    // ==========================================
    const updateLobbyUI = () => {
        const coinDisplay = document.getElementById('lobby-coins');
        if (coinDisplay) coinDisplay.innerText = player.coins;

        ['hp', 'atk'].forEach(type => {
            const lv = type === 'hp' ? player.hpLv : player.atkLv;
            const lvLbl = document.getElementById(`lbl-${type}-lv`);
            const costLbl = document.getElementById(`cost-${type}`);
            if (lvLbl) lvLbl.innerText = lv;
            if (costLbl) costLbl.innerText = (lv + 1) * 50;
        });
    };
    updateLobbyUI();

    // 處理局外購買加點
    document.querySelectorAll('.btn-buy').forEach(btn => {
        btn.onclick = async (e) => {
            const type = e.currentTarget.dataset.type;
            try {
                const res = await fetch(CSI_CONFIG.upgradeApiUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSI_CONFIG.csrfToken },
                    body: JSON.stringify({ upgrade_type: type })
                });
                const data = await res.json();
                if (data.status === 'success') {
                    if (type === 'hp') player.hpLv = data.new_level;
                    else player.atkLv = data.new_level;
                    player.coins = data.remaining_coins;
                    updateLobbyUI();
                } else {
                    alert("金幣不足！");
                }
            } catch (err) { console.error(err); }
        };
    });

    // 開始遊戲按鈕
    if (btnStart) {
        btnStart.onclick = () => {
            // 重新計算套用最新加點的血量與攻擊
            player.maxHp = 100 + (player.hpLv * 20);
            player.hp = player.maxHp;
            player.atkBase = 10 + (player.atkLv * 2);

            // 切換畫面
            lobbyScreen.classList.remove('active');
            gameScreen.classList.remove('d-none');

            // 啟動地圖生成
            generateMap();
        };
    }

    // 離開遊戲邏輯 (供 HTML 呼叫)
    window.confirmExit = () => {
        if (confirm("確定要放棄本次進度並離開遊戲嗎？")) {
            window.location.href = CSI_CONFIG.lobbyUrl;
        }
    };


    // ==========================================
    // 2. 局內遊戲邏輯 (UI更新、地圖生成)
    // ==========================================
    function updateUI() {
        document.getElementById('ui-level').innerText = player.level;
        document.getElementById('ui-hp').innerText = `${player.hp}/${player.maxHp}`;
        document.getElementById('ui-atk').innerText = `${Math.floor(player.atkBase * 0.8)}-${Math.floor(player.atkBase * 1.2)}`;
        document.getElementById('ui-potions').innerText = player.potions;
        document.getElementById('ui-boss-turns').innerText = player.turnsUntilBoss;
    }

    // 生成手機版地圖 (10x15)
    function generateMap() {
        boardContainer.innerHTML = ''; //* 清空容器
        const cols = 10;
        const rows = 15;
        const pathLen = 75; //* 明確設定路線總長度為 75 格

        let grid = Array(rows).fill().map(() => Array(cols).fill(null));
        let path = [];
        let pathFound = false;

        // 使用深度優先搜尋 (DFS) 配合回溯，尋找一條剛好 75 格且不重複的蜿蜒路徑
        function findPath(x, y) {
            if (pathFound) return;

            path.push({ x: x, y: y }); //* 將當前座標加入路徑
            grid[y][x] = true; //* 標記為已走過，避免路線重疊

            if (path.length === pathLen) {
                pathFound = true; //* 達到 75 格，成功找到路徑
                return;
            }

            // 隨機打亂四個方向，創造自然轉彎的感覺
            let dirs = [{ x: 1, y: 0 }, { x: -1, y: 0 }, { x: 0, y: 1 }, { x: 0, y: -1 }];
            dirs.sort(() => Math.random() - 0.5);

            for (let d of dirs) {
                let nx = x + d.x;
                let ny = y + d.y;

                // 檢查下一步是否在 10x15 範圍內，且還沒走過
                if (nx >= 0 && nx < cols && ny >= 0 && ny < rows && !grid[ny][nx]) {
                    findPath(nx, ny);
                    if (pathFound) return;
                }
            }

            // 如果四周都無路可走且還沒湊滿 75 格，退回上一格 (回溯機制)
            path.pop();
            grid[y][x] = null;
        }

        // 從左上角 (0, 0) 開始產生路徑
        findPath(0, 0);

        if (!pathFound) {
            console.error("無法生成完整路徑，請檢查網格設定");
            return;
        }

        // 賦予格子事件類型與機率設定
        path.forEach((node, index) => {
            if (index === 0) {
                node.type = 'start'; //* 第一格永遠是起點
            } else {
                let r = Math.random();
                if (r < 0.25) node.type = 'monster';      //* 25% 怪物
                else if (r < 0.50) node.type = 'event';   //* 25% 事件
                else if (r < 0.65) node.type = 'shop';    //* 15% 商店
                else node.type = 'empty';                 //* 35% 空地
            }
        });

        // 計算路線的方向箭頭
        for (let i = 0; i < path.length - 1; i++) {
            let c = path[i], n = path[i + 1];
            if (n.x > c.x) c.arrow = '➡️';
            else if (n.x < c.x) c.arrow = '⬅️';
            else if (n.y > c.y) c.arrow = '⬇️';
            else if (n.y < c.y) c.arrow = '⬆️';
        }

        pathCells = path;

        // 建立繪圖用陣列，方便將資料對應到 CSS Grid 座標
        let renderGrid = Array(rows).fill().map(() => Array(cols).fill(null));
        path.forEach((node) => {
            renderGrid[node.y][node.x] = node;
        });

        // 渲染所有的 150 個方格 (包含路徑與草地背景)
        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                let cell = document.createElement('div');
                let node = renderGrid[r][c];

                if (node) {
                    // 如果這格有路線
                    cell.className = `board-cell cell-${node.type}`;
                    cell.id = `grid-${c}-${r}`;
                    cell.style.gridColumn = c + 1;
                    cell.style.gridRow = r + 1;

                    if (node.arrow) cell.innerHTML = `<span class="path-arrow">${node.arrow}</span>`;

                    let icon = document.createElement('span');
                    icon.style.zIndex = '5';
                    if (node.type === 'start') icon.innerText = '🏁';
                    else if (node.type === 'monster') icon.innerText = '👾';
                    else if (node.type === 'shop') icon.innerText = '🏪';
                    else if (node.type === 'event') icon.innerText = '❓';
                    cell.appendChild(icon);
                } else {
                    // 如果這格沒有路線，填入草地背景與隨機植物圖案
                    cell.className = 'board-cell cell-grass';
                    cell.style.gridColumn = c + 1;
                    cell.style.gridRow = r + 1;

                    let icon = document.createElement('span');
                    icon.style.opacity = '0.3'; //* 降低透明度，避免干擾主要路線視線
                    icon.innerText = Math.random() > 0.5 ? '🌿' : '☘️';
                    cell.appendChild(icon);
                }
                boardContainer.appendChild(cell);
            }
        } //* ✅ 正確在這裡關閉 r 迴圈

        // 將玩家棋子放置在起點 (移到迴圈外，確保只產生一個)
        const token = document.createElement('div');
        token.id = 'player-token';
        token.className = 'player-token';
        document.getElementById(`grid-${path[0].x}-${path[0].y}`).appendChild(token);
        updateUI();
    } //* ✅ 🚀 正確在這裡關閉 generateMap 函數！


    function logToModal(msg, cls = 'text-light') {
        const li = document.createElement('li');
        li.className = `mb-1 ${cls}`;
        li.innerText = msg;
        modalLog.prepend(li);
        modalLog.scrollTop = 0;
    }


    // ==========================================
    // 3. 戰鬥邏輯
    // ==========================================
    async function startCombat(isBoss = false) {
        let enemyMaxHp = isBoss ? 200 + (player.level * 50) : 40 + (player.level * 10);
        let enemyAtk = isBoss ? 15 + (player.level * 5) : 6 + (player.level * 2);
        let enemyHp = enemyMaxHp;
        let speed = 1;

        modal.classList.remove('d-none');
        modalCombatStats.classList.remove('d-none');
        modalLog.classList.remove('d-none');
        modalLog.innerHTML = '';
        modalTitle.innerText = isBoss ? "🔥 BOSS 戰" : "⚔️ 戰鬥開始";
        modalDesc.innerText = `敵人攻擊力: ${enemyAtk}`;
        monsterHpDisplay.innerText = `${enemyHp}/${enemyMaxHp}`;

        modalActions.innerHTML = `
        <div class="btn-group w-100">
            <button class="btn btn-sm btn-outline-light s-btn active" data-s="1">1x</button>
            <button class="btn btn-sm btn-outline-light s-btn" data-s="2">2x</button>
            <button class="btn btn-sm btn-outline-light s-btn" data-s="5">5x</button>
        </div>
        `;

        document.querySelectorAll('.s-btn').forEach(b => b.onclick = (e) => {
            document.querySelectorAll('.s-btn').forEach(x => x.classList.remove('active'));
            e.target.classList.add('active');
            speed = parseInt(e.target.dataset.s);
        });

        // 戰鬥迴圈
        while (enemyHp > 0 && player.hp > 0) {
            await delay(800 / speed);
            let pd = Math.floor(player.atkBase * (0.8 + Math.random() * 0.4));
            enemyHp -= pd;
            logToModal(`你造成 ${pd} 傷害`, 'text-warning');
            monsterHpDisplay.innerText = `${Math.max(0, enemyHp)}/${enemyMaxHp}`;
            if (enemyHp <= 0) break;

            await delay(800 / speed);
            let ed = Math.floor(enemyAtk * (0.8 + Math.random() * 0.4));
            player.hp -= ed;
            if (player.hp <= 0 && player.potions > 0) {
                player.potions--;
                player.hp = Math.floor(player.maxHp * 0.5);
                logToModal(`🧪 自動喝水！恢復至 ${player.hp} HP`, 'text-success');
            }
            logToModal(`怪獸攻擊造成 ${ed} 傷害 (剩餘 HP: ${Math.max(0, player.hp)})`, 'text-danger');
            updateUI();
        }

        modalActions.innerHTML = '';
        if (player.hp <= 0) {
            handleGameOver(); //* 玩家死亡
        } else {
            if (isBoss) {
                logToModal("🎉 擊敗 BOSS！", "text-success");
                handleWin(); //* 擊敗 Boss
            } else {
                player.sessionCoins += 1; //* 擊殺一般怪物，局內金幣加 1
                logToModal(`戰鬥勝利！獲得能力提升與 1 金幣。(本局累積: ${player.sessionCoins})`, "text-success");

                player.atkBase += 1;
                player.maxHp += 5;
                player.hp = Math.min(player.maxHp, player.hp + 10);
                updateUI();

                let b = document.createElement('button');
                b.className = 'btn btn-primary w-100 fw-bold';
                b.innerText = '關閉並繼續';
                b.onclick = () => {
                    modal.classList.add('d-none');
                    isRolling = false;
                    btnRoll.disabled = false;
                    if (player.turnsUntilBoss <= 0) startCombat(true);
                };
                modalActions.appendChild(b);
            }
        }
    }

    // ==========================================
    // 4. 視窗關閉與事件流程控制
    // ==========================================
    function closeModal() {
        modal.classList.add('d-none');
        modalLog.classList.add('d-none'); //* 關閉時隱藏日誌
        modalLog.innerHTML = '';
        isRolling = false;
        btnRoll.disabled = false;

        // 每次關閉視窗時，檢查是否該打 Boss 了
        if (player.turnsUntilBoss <= 0) {
            startCombat(true);
        }
    }

    function triggerShop() {
        modal.classList.remove('d-none');
        modalCombatStats.classList.add('d-none'); //* 隱藏戰鬥血條
        modalLog.classList.add('d-none'); //* 隱藏戰鬥日誌

        modalTitle.innerText = "🏪 雜貨商人";
        modalDesc.innerText = "這裡有些好東西，你需要什麼？";
        modalActions.innerHTML = ''; //* 清空按鈕

        let btnBuyWep = document.createElement('button');
        btnBuyWep.className = 'btn btn-danger m-1 flex-fill';
        btnBuyWep.innerText = '買武器 (ATK+5)';
        btnBuyWep.onclick = () => {
            player.atkBase += 5;
            updateUI();
            closeModal();
        };

        let btnBuyPot = document.createElement('button');
        btnBuyPot.className = 'btn btn-success m-1 flex-fill';
        btnBuyPot.innerText = '買藥水 (1瓶)';
        btnBuyPot.onclick = () => {
            player.potions++;
            updateUI();
            closeModal();
        };

        let btnLeave = document.createElement('button');
        btnLeave.className = 'btn btn-secondary m-1 flex-fill';
        btnLeave.innerText = '離開';
        btnLeave.onclick = closeModal;

        let btnGroup = document.createElement('div');
        btnGroup.className = 'd-flex w-100 gap-2';
        btnGroup.append(btnBuyWep, btnBuyPot, btnLeave);
        modalActions.appendChild(btnGroup);
    }

    function triggerEvent() {
        modal.classList.remove('d-none');
        modalCombatStats.classList.add('d-none');
        modalLog.classList.add('d-none');

        let r = Math.random();
        if (r < 0.50) {
            // 50% 機率增加 2 點攻擊
            let atkGain = 2;
            player.atkBase += atkGain;
            modalTitle.innerText = "⚔️ 磨刀石";
            modalDesc.innerText = `你在路邊撿到一塊磨刀石，攻擊力永久提升 ${atkGain} 點！`;
        } else if (r < 0.75) {
            // 25% 補血泉水
            let hpGain = 25;
            player.hp = Math.min(player.maxHp, player.hp + hpGain);
            modalTitle.innerText = "✨ 癒合泉水";
            modalDesc.innerText = `清澈的泉水洗淨了你的傷口，恢復了 ${hpGain} 點生命！`;
        } else {
            // 25% 扣血陷阱
            let dmg = 20;
            player.hp -= dmg;
            modalTitle.innerText = "💥 隱藏陷阱";
            modalDesc.innerText = `你不小心踩到了地刺，失去了 ${dmg} 點生命！`;
        }

        modalActions.innerHTML = '';
        let btnOk = document.createElement('button');
        btnOk.className = 'btn btn-primary w-100 fw-bold';
        btnOk.innerText = '確定';

        btnOk.onclick = () => {
            if (player.hp <= 0) {
                handleGameOver();
            } else {
                closeModal();
            }
        };

        modalActions.appendChild(btnOk);
        updateUI();
    }

    async function handleWin() {
        try {
            const res = await fetch(CSI_CONFIG.saveApiUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSI_CONFIG.csrfToken },
                body: JSON.stringify({
                    is_win: true,
                    level: player.level,
                    kill_coins: player.sessionCoins //* 傳送擊殺金幣
                })
            });
            const d = await res.json();
            modalDesc.innerHTML = `<h4 class="text-warning">獲得 ${d.earned_coins} 金幣！</h4>`;
            let b = document.createElement('button');
            b.className = 'btn btn-success w-100';
            b.innerText = '進入下一關';
            b.onclick = () => window.location.reload();
            modalActions.appendChild(b);
        } catch (e) { console.error(e); }
    }

    // 遊戲失敗結算
    async function handleGameOver() {
        modalTitle.innerText = "💀 戰敗";
        modalDesc.innerHTML = "正在結算本次戰鬥收益...";
        modalActions.innerHTML = ''; //* 結算中先清空按鈕

        try {
            // 向後端發送戰敗結算請求，存入擊殺金幣
            const res = await fetch(CSI_CONFIG.saveApiUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSI_CONFIG.csrfToken },
                body: JSON.stringify({
                    is_win: false,
                    level: player.level,
                    kill_coins: player.sessionCoins //* 傳送死前累積的擊殺金幣
                })
            });
            const d = await res.json();

            modalDesc.innerHTML = `你倒下了...<br><span class="text-warning">但帶回了 ${d.earned_coins} 金幣</span>`;

            let btnExit = document.createElement('button');
            btnExit.className = 'btn btn-danger w-100 fw-bold mt-3';
            btnExit.innerText = '返回大廳';
            btnExit.onclick = () => window.location.href = CSI_CONFIG.lobbyUrl;
            modalActions.appendChild(btnExit);

        } catch (e) {
            console.error(e);
            // 發生錯誤的備用逃生方案
            let btnExit = document.createElement('button');
            btnExit.className = 'btn btn-danger w-100 fw-bold';
            btnExit.innerText = '返回大廳';
            btnExit.onclick = () => window.location.href = CSI_CONFIG.lobbyUrl;
            modalActions.appendChild(btnExit);
        }
    }


    // ==========================================
    // 5. 擲骰子主控制迴圈
    // ==========================================
    if (btnRoll) {
        btnRoll.onclick = async () => {
            if (isRolling) return;
            isRolling = true;
            btnRoll.disabled = true;
            player.turnsUntilBoss--;
            updateUI();

            let dice = Math.floor(Math.random() * 6) + 1;
            diceDisplay.innerText = dice;

            const token = document.getElementById('player-token');
            for (let i = 0; i < dice; i++) {
                currentPosIndex = (currentPosIndex + 1) % pathCells.length;
                await delay(200);
                let n = pathCells[currentPosIndex];
                document.getElementById(`grid-${n.x}-${n.y}`).appendChild(token);
            }

            // 觸發該格事件 (補回完整的格子判定)
            let type = pathCells[currentPosIndex].type;
            if (type === 'monster') {
                startCombat(false); //* 遇到怪物，開戰
            } else if (type === 'shop') {
                triggerShop();      //* 遇到商店，開啟購買視窗
            } else if (type === 'event') {
                triggerEvent();     //* 遇到問號，開啟事件視窗
            } else {
                // 如果是空地或起點，解除按鈕鎖定，並檢查是否該打 Boss
                await delay(300);
                isRolling = false;
                btnRoll.disabled = false;
                if (player.turnsUntilBoss <= 0) startCombat(true);
            }
        };
    }
});