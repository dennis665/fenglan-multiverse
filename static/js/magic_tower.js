document.addEventListener('DOMContentLoaded', () => {
    const board = document.getElementById('game-board');
    const classModal = document.getElementById('class-modal');

    let currentFloor = 1;
    let mapData = {};
    let mapStates = {}; //* 儲存各地圖被吃掉或打開的物件

    let player = {
        classType: '', level: 1, hp: 0, atk: 0, def: 0, exp: 0, yellowKeys: 0, blueKeys: 0,
        x: 0, y: 0
    };

    const outHp = MT_CONFIG.baseHpLv * 50;
    const outAtk = MT_CONFIG.baseAtkLv * 5;
    const outDef = MT_CONFIG.baseDefLv * 5;

    // ==========================================
    // 1. 初始化與存檔讀取 (修復卡牆壁 Bug)
    // ==========================================
    function initGame() {
        mapData = JSON.parse(JSON.stringify(MT_CONFIG.floorsData));

        if (MT_CONFIG.saveData) {
            let s = MT_CONFIG.saveData;
            player = {
                classType: s.class_type, level: s.level, hp: s.hp, atk: s.atk, def: s.def,
                exp: s.exp, yellowKeys: s.yellow_keys, blueKeys: s.blue_keys,
                x: 0, y: 0
            };
            currentFloor = s.current_floor;
            mapStates = s.map_states || {};

            // 🚀 從 mapStates 中還原玩家的精確座標
            if (mapStates.player_x !== undefined) player.x = mapStates.player_x;
            if (mapStates.player_y !== undefined) player.y = mapStates.player_y;

            loadMap(currentFloor, false, true); //* 標記為 true 代表是「讀檔載入」
        } else {
            classModal.classList.remove('d-none');
        }
    }

    window.selectClass = function (type) {
        player.classType = type;
        if (type === 'tank') { player.hp = 2000; player.atk = 10; player.def = 25; }
        else if (type === 'warrior') { player.hp = 1000; player.atk = 15; player.def = 10; }
        else if (type === 'mage') { player.hp = 500; player.atk = 25; player.def = 5; }

        player.hp += outHp; player.atk += outAtk; player.def += outDef;

        classModal.classList.add('d-none');
        loadMap(1, false, false);
    };

    // ==========================================
    // 2. 地圖渲染系統
    // ==========================================
    function loadMap(floor, isGoingDown, isLoadSave = false) {
        currentFloor = floor;
        let layout = mapData[floor];
        let state = mapStates[floor] || {};
        board.innerHTML = '';

        for (let y = 0; y < 15; y++) {
            for (let x = 0; x < 10; x++) {
                let val = layout[y][x];
                let stateKey = `${x}-${y}`;
                if (state[stateKey] !== undefined) val = state[stateKey];

                let cell = document.createElement('div');
                cell.id = `c-${x}-${y}`;
                cell.className = 'mt-cell cell-floor';

                if (val === 1) cell.className = 'mt-cell cell-wall';
                else if (val === 3) cell.innerHTML = '⬆️';
                else if (val === 4) cell.innerHTML = '⬇️';
                else if (val === 10) cell.innerHTML = '🟨';
                else if (val === 11) cell.className = 'mt-cell door-yellow';
                else if (val === 12) cell.innerHTML = '🟦';
                else if (val === 13) cell.className = 'mt-cell door-blue';
                else if (val === 20) cell.innerHTML = '🧪';
                else if (val === 21) cell.innerHTML = '🔴';
                else if (val === 22) cell.innerHTML = '🔵';
                else if (val >= 30) {
                    let mInfo = MT_CONFIG.monstersData[val];
                    if (mInfo && mInfo.img) {
                        cell.innerHTML = `<img src="${mInfo.img}" class="img-sprite img-monster" title="${mInfo.name}">`;
                    } else {
                        cell.innerHTML = '<span class="img-monster">👾</span>';
                    }
                }

                // 🚀 定位邏輯優化 (讀檔時不覆寫座標)
                if (val === 2) {
                    if (!isLoadSave) { player.x = x; player.y = y; }
                    saveTileState(x, y, 0); //* 無論如何起點都要抹除
                } else if (!isLoadSave && isGoingDown && val === 3) {
                    player.x = x; player.y = y;
                } else if (!isLoadSave && !isGoingDown && val === 4 && player.x === 0 && player.y === 0) {
                    player.x = x; player.y = y;
                }

                board.appendChild(cell);
            }
        }
        drawPlayer();
        updateUI();
    }

    function saveTileState(x, y, val) {
        if (!mapStates[currentFloor]) mapStates[currentFloor] = {};
        mapStates[currentFloor][`${x}-${y}`] = val;
    }

    function drawPlayer() {
        let old = document.getElementById('p-token');
        if (old) old.remove();
        let target = document.getElementById(`c-${player.x}-${player.y}`);
        if (target) target.innerHTML += `<div id="p-token" style="position:absolute; font-size:1.5rem; z-index:10; transition:0.1s;">🧑</div>`;
    }

    function updateUI() {
        document.getElementById('ui-floor').innerText = currentFloor;
        document.getElementById('ui-class').innerText = player.classType.toUpperCase();
        document.getElementById('ui-level').innerText = player.level;
        document.getElementById('ui-hp').innerText = player.hp;
        document.getElementById('ui-atk').innerText = player.atk;
        document.getElementById('ui-def').innerText = player.def;
        document.getElementById('ui-exp').innerText = player.exp;
        document.getElementById('ui-ykey').innerText = player.yellowKeys;
        document.getElementById('ui-bkey').innerText = player.blueKeys;
    }

    // ==========================================
    // 3. 移動與精算戰鬥邏輯
    // ==========================================

    // 將移動邏輯獨立，提供鍵盤與手機按鈕共用
    window.triggerMove = function (dx, dy) {
        if (!player.classType || player.hp <= 0) return;

        let nx = player.x + dx;
        let ny = player.y + dy;
        if (nx < 0 || nx >= 10 || ny < 0 || ny >= 15) return;

        let stateKey = `${nx}-${ny}`;
        let val = mapStates[currentFloor]?.[stateKey] ?? mapData[currentFloor][ny][nx];

        if (val === 1) return; //* 撞牆

        // 上下樓
        if (val === 3) {
            checkReward(currentFloor);
            loadMap(currentFloor + 1, false, false);
            return;
        }
        if (val === 4) { loadMap(currentFloor - 1, true, false); return; }

        // 開門
        if (val === 11) {
            if (player.yellowKeys <= 0) return;
            player.yellowKeys--;
        } else if (val === 13) {
            if (player.blueKeys <= 0) return;
            player.blueKeys--;
        }
        // 道具
        else if (val === 10) player.yellowKeys++;
        else if (val === 12) player.blueKeys++;
        else if (val === 20) player.hp += 200;
        else if (val === 21) player.atk += 3;
        else if (val === 22) player.def += 3;

        // 戰鬥精算
        else if (val >= 30) {
            let m = MT_CONFIG.monstersData[val];
            let pDmg = player.atk - m.def;
            if (pDmg <= 0) { alert("攻擊力不足，無法破防！"); return; }

            let mDmg = m.atk - player.def;
            if (mDmg < 0) mDmg = 0;

            let hitsNeeded = Math.ceil(m.hp / pDmg);
            let totalDmgTaken = (hitsNeeded - 1) * mDmg;

            if (player.hp <= totalDmgTaken) { alert(`打不過！預計損失 ${totalDmgTaken} HP`); return; }

            player.hp -= totalDmgTaken;
            player.exp += m.exp;
            checkLevelUp();

            if (val === 35) {
                alert("🎉 恭喜通關！");
                checkReward(currentFloor, true);
            }
        }

        if (val !== 0 && val !== 2) {
            saveTileState(nx, ny, 0);
            let c = document.getElementById(`c-${nx}-${ny}`);
            c.className = 'mt-cell cell-floor';
            c.innerHTML = '';
        }

        player.x = nx; player.y = ny;
        drawPlayer();
        updateUI();
    };

    // 鍵盤監聽呼叫 triggerMove
    window.addEventListener('keydown', (e) => {
        // 防止網頁跟著上下捲動
        if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
            e.preventDefault();
        }

        if (e.key === 'ArrowUp') triggerMove(0, -1);
        else if (e.key === 'ArrowDown') triggerMove(0, 1);
        else if (e.key === 'ArrowLeft') triggerMove(-1, 0);
        else if (e.key === 'ArrowRight') triggerMove(1, 0);
    });

    function checkLevelUp() {
        let req = player.level * 20;
        if (player.exp >= req) {
            player.exp -= req;
            player.level++;
            player.hp += 100; player.atk += 2; player.def += 2;
            alert(`升級了！目前等級: ${player.level}`);
            updateUI();
        }
    }

    function checkReward(floor, isBoss = false) {
        let cleared = MT_CONFIG.saveData ? MT_CONFIG.saveData.cleared_floors : [];
        if (!cleared.includes(floor)) {
            fetch(MT_CONFIG.rewardApi, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': MT_CONFIG.csrfToken },
                body: JSON.stringify({ floor: floor, is_boss: isBoss })
            });
            if (MT_CONFIG.saveData) MT_CONFIG.saveData.cleared_floors.push(floor);
        }
    }

    // ==========================================
    // 4. API 儲存與重置
    // ==========================================
    document.getElementById('btn-save').onclick = async () => {
        let cleared = MT_CONFIG.saveData ? MT_CONFIG.saveData.cleared_floors : [];

        // 🚀 將當前座標存入 mapStates 中 (不更動後端資料庫設計)
        mapStates.player_x = player.x;
        mapStates.player_y = player.y;

        try {
            let res = await fetch(MT_CONFIG.saveApi, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': MT_CONFIG.csrfToken },
                body: JSON.stringify({
                    class_type: player.classType, level: player.level, hp: player.hp,
                    atk: player.atk, def: player.def, exp: player.exp,
                    yellow_keys: player.yellowKeys, blue_keys: player.blueKeys,
                    current_floor: currentFloor, map_states: mapStates, cleared_floors: cleared
                })
            });
            let d = await res.json();
            if (d.status === 'success') alert("存檔成功！下次進入將從這裡開始。");
        } catch (e) { console.error(e); }
    };

    document.getElementById('btn-reset').onclick = async () => {
        if (confirm("確定要重置魔塔進度嗎？這會清除目前的狀態，但可以重新獲得通關獎勵。")) {
            await fetch(MT_CONFIG.resetApi, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': MT_CONFIG.csrfToken }
            });
            window.location.reload();
        }
    };

    initGame();
});