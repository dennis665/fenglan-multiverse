document.addEventListener('DOMContentLoaded', () => {
    const board = document.getElementById('game-board');
    const classModal = document.getElementById('class-modal');

    let currentFloor = 1;
    let isAnimating = false; //* 防止戰鬥動畫期間玩家亂動
    let mapData = {};
    let mapStates = {}; //* 儲存各地圖被吃掉或打開的物件

    let player = {
        classType: '', level: 1, hp: 0, atk: 0, def: 0, exp: 0, yellowKeys: 0, blueKeys: 0,
        x: 0, y: 0
    };

    const outHp = MT_CONFIG.baseHpLv * 50;
    const outAtk = MT_CONFIG.baseAtkLv * 5;
    const outDef = MT_CONFIG.baseDefLv * 5;

    const delay = (ms) => new Promise(res => setTimeout(res, ms));

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
                cell.className = 'mt-cell cell-floor'; //* 預設基底都是地板

                // 🚀 取得自訂圖片資料
                let customImg = MT_CONFIG.resourcesData[val];
                let monsterData = MT_CONFIG.monstersData[val];

                if (val === 1) {
                    // 牆壁：如果有自訂圖則用圖片鋪滿，否則用預設 CSS
                    if (customImg) {
                        cell.style.backgroundImage = `url('${customImg}')`;
                        cell.style.backgroundSize = 'cover';
                    } else {
                        cell.className = 'mt-cell cell-wall';
                    }
                } else if (val === 0 && customImg) {
                    // 地板：如果有自訂圖，覆蓋預設地板
                    cell.style.backgroundImage = `url('${customImg}')`;
                    cell.style.backgroundSize = 'cover';
                } else if (val >= 30) {
                    // 怪物：優先使用怪物圖鑑的圖片，若無則降級找自訂資源表，最後預設
                    let mImg = monsterData?.img || customImg;
                    if (mImg) {
                        cell.innerHTML = `<img src="${mImg}" class="img-sprite img-monster" title="${monsterData?.name || '怪物'}">`;
                    } else {
                        cell.innerHTML = '<span class="img-monster">👾</span>';
                    }
                } else if (customImg && val !== 2) {
                    // 道具、門、樓梯：有自訂圖片則直接顯示圖片 (排除起點標記 2)
                    cell.innerHTML = `<img src="${customImg}" class="img-sprite">`;
                } else {
                    // 預設 Emoji 與 CSS 材質 (完全沒有自訂圖片時的 Fallback)
                    if (val === 3) cell.innerHTML = '⬆️';
                    else if (val === 4) cell.innerHTML = '⬇️';
                    else if (val === 10) cell.innerHTML = '🟨';
                    else if (val === 11) cell.className = 'mt-cell door-yellow';
                    else if (val === 12) cell.innerHTML = '🟦';
                    else if (val === 13) cell.className = 'mt-cell door-blue';
                    else if (val === 20) cell.innerHTML = '🧪';
                    else if (val === 21) cell.innerHTML = '🔴';
                    else if (val === 22) cell.innerHTML = '🔵';
                }

                // 🚀 定位邏輯 (讀檔時不覆寫座標)
                if (val === 2) {
                    if (!isLoadSave) { player.x = x; player.y = y; }
                    saveTileState(x, y, 0); // 起點標記處理後抹除
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

    // 🚀 繪製玩家 (支援依據所選職業自動切換圖片)
    function drawPlayer() {
        let old = document.getElementById('p-token');
        if (old) old.remove();
        let target = document.getElementById(`c-${player.x}-${player.y}`);

        // 1. 建立職業與後台 tile_id 的對應表
        const classImageMapping = {
            'tank': MT_CONFIG.resourcesData[201],    //* 對應聖騎士 (ID: 201)
            'warrior': MT_CONFIG.resourcesData[202], //* 對應戰士 (ID: 202)
            'mage': MT_CONFIG.resourcesData[203]     //* 對應魔法師 (ID: 203)
        };

        // 2. 判斷要使用哪張圖片
        // 優先找對應職業的圖片 -> 找不到就找代碼 2 的共用圖片 -> 再找不到就用預設的 Emoji
        let playerImg = classImageMapping[player.classType] || MT_CONFIG.resourcesData[2];

        let playerHtml = playerImg
            ? `<img src="${playerImg}" style="width:100%; height:100%; object-fit:contain; filter: drop-shadow(0px 3px 2px rgba(0,0,0,0.5));">`
            : `🧑`; //* 備用的 Emoji

        if (target) {
            target.innerHTML += `<div id="p-token" style="position:absolute; width:80%; height:80%; font-size:clamp(1rem, 4vw, 1.5rem); z-index:10; display:flex; justify-content:center; align-items:center; transition: 0.1s;">${playerHtml}</div>`;
        }
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
    // 新增：樓層圖鑑與戰鬥預測系統
    // ==========================================
    const handbookModal = document.getElementById('handbook-modal');
    const handbookContent = document.getElementById('handbook-content');
    const btnHandbook = document.getElementById('btn-handbook');

    // 固定道具與環境的文字說明
    const itemDict = {
        3: { name: "上樓梯", desc: "往上一層" },
        4: { name: "下樓梯", desc: "回下一層" },
        10: { name: "黃色鑰匙", desc: "可以開啟一扇黃色門" },
        11: { name: "黃色門", desc: "需要消耗一把黃鑰匙才能開啟" },
        12: { name: "藍色鑰匙", desc: "可以開啟一扇藍色門" },
        13: { name: "藍色門", desc: "需要消耗一把藍鑰匙才能開啟" },
        20: { name: "生命藥水", desc: "恢復 200 點生命值" },
        21: { name: "力量寶石", desc: "提升 3 點攻擊力" },
        22: { name: "防禦寶石", desc: "提升 3 點防禦力" }
    };

    if (btnHandbook) {
        btnHandbook.onclick = () => {
            if (!player.classType || player.hp <= 0) return; // 還沒選職業或已死亡則不開啟
            renderHandbook();
            handbookModal.classList.remove('d-none');
        };
    }

    function renderHandbook() {
        handbookContent.innerHTML = '';

        // 1. 掃描當前樓層所有尚未消失的圖磚
        let currentUniqueTiles = new Set();
        let layout = mapData[currentFloor];
        let state = mapStates[currentFloor] || {};

        for (let y = 0; y < 15; y++) {
            for (let x = 0; x < 10; x++) {
                let stateKey = `${x}-${y}`;
                let val = state[stateKey] !== undefined ? state[stateKey] : layout[y][x];
                // 排除空地(0)、牆壁(1)、起點(2)
                if (val > 2) currentUniqueTiles.add(val);
            }
        }

        let tilesArray = Array.from(currentUniqueTiles).sort((a, b) => a - b);
        if (tilesArray.length === 0) {
            handbookContent.innerHTML = '<p class="text-center text-secondary my-4">本層已經被清空了！</p>';
            return;
        }

        // 2. 生成每一項的圖鑑卡片
        tilesArray.forEach(val => {
            let customImg = MT_CONFIG.resourcesData[val];
            let html = '';

            // 判斷是道具還是怪物
            if (val < 30) {
                // --- 道具/物件卡片 ---
                let info = itemDict[val] || { name: "未知物品", desc: "沒有說明" };
                let iconHtml = customImg ? `<img src="${customImg}" style="width:40px; height:40px; object-fit:contain;">` : `<span style="font-size:30px;">❓</span>`;

                // 補上預設的 Emoji (如果沒上傳圖片)
                if (!customImg) {
                    if (val === 3) iconHtml = '⬆️'; else if (val === 4) iconHtml = '⬇️';
                    else if (val === 10) iconHtml = '🟨'; else if (val === 11) iconHtml = '🚪';
                    else if (val === 12) iconHtml = '🟦'; else if (val === 13) iconHtml = '🚪';
                    else if (val === 20) iconHtml = '🧪'; else if (val === 21) iconHtml = '🔴';
                    else if (val === 22) iconHtml = '🔵';
                    iconHtml = `<span style="font-size:30px;">${iconHtml}</span>`;
                }

                html = `
                <div class="card bg-black border-secondary mb-2">
                    <div class="card-body p-2 d-flex align-items-center">
                        <div class="me-3 d-flex justify-content-center align-items-center" style="width: 50px; height: 50px; background-color:#222; border-radius:8px;">
                            ${iconHtml}
                        </div>
                        <div>
                            <h6 class="text-light fw-bold m-0 mb-1">${info.name}</h6>
                            <small class="text-secondary">${info.desc}</small>
                        </div>
                    </div>
                </div>`;
            } else {
                // --- 怪物卡片 (包含戰鬥預測) ---
                let m = MT_CONFIG.monstersData[val];
                if (!m) return;

                let mImg = m.img || customImg;
                let iconHtml = mImg ? `<img src="${mImg}" style="width:40px; height:40px; object-fit:contain;">` : `<span style="font-size:30px;">👾</span>`;

                // 核心演算法：傷害預測
                let pDmg = player.atk - m.def; // 玩家對怪物的單次傷害
                let mDmg = Math.max(0, m.atk - player.def); // 怪物對玩家的單次傷害
                let statusHtml = '';

                if (pDmg <= 0) {
                    statusHtml = `<span class="badge bg-danger fs-6 text-white">無法破防 (傷害 0)</span>`;
                } else {
                    // 計算擊殺所需次數 (無條件進位)
                    let hitsNeeded = Math.ceil(m.hp / pDmg);
                    // 玩家先手，所以怪物攻擊次數是 hitsNeeded - 1
                    let totalDmgTaken = (hitsNeeded - 1) * mDmg;

                    if (player.hp <= totalDmgTaken) {
                        statusHtml = `<span class="badge bg-danger fs-6">打不過 (預估損血: ${totalDmgTaken})</span>`;
                    } else {
                        statusHtml = `<span class="badge bg-success fs-6 text-white">可以戰勝 (預估損血: ${totalDmgTaken})</span>`;
                    }
                }

                html = `
                <div class="card bg-black border-danger mb-2">
                    <div class="card-body p-2">
                        <div class="d-flex align-items-center mb-2">
                            <div class="me-3 d-flex justify-content-center align-items-center" style="width: 50px; height: 50px; background-color:#222; border-radius:8px;">
                                ${iconHtml}
                            </div>
                            <div class="flex-grow-1">
                                <h6 class="text-danger fw-bold m-0 mb-1">${m.name}</h6>
                                ${statusHtml}
                            </div>
                        </div>
                        <div class="row g-1 text-center small fw-bold">
                            <div class="col-3"><span class="text-success">❤️ ${m.hp}</span></div>
                            <div class="col-3"><span class="text-danger">⚔️ ${m.atk}</span></div>
                            <div class="col-3"><span class="text-info">🛡️ ${m.def}</span></div>
                            <div class="col-3"><span class="text-warning">⭐ ${m.exp}</span></div>
                        </div>
                    </div>
                </div>`;
            }

            handbookContent.innerHTML += html;
        });
    }

    // ==========================================
    // 3. 移動與精算戰鬥邏輯
    // ==========================================

    // 加上 async 關鍵字，並阻擋動畫期間的操作
    window.triggerMove = async function (dx, dy) {
        if (!player.classType || player.hp <= 0 || isAnimating) return; //* 鎖定操作

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

        // 🚀 建立一個專門把格子變回「自訂地板」的函式 (解決破圖問題)
        const turnIntoFloor = (x, y) => {
            saveTileState(x, y, 0);
            let c = document.getElementById(`c-${x}-${y}`);
            c.className = 'mt-cell cell-floor';
            c.innerHTML = '';

            // 鋪上自訂地板圖片 (如果有的話)
            let floorImg = MT_CONFIG.resourcesData[0];
            if (floorImg) {
                c.style.backgroundImage = `url('${floorImg}')`;
                c.style.backgroundSize = 'cover';
            } else {
                c.style.backgroundImage = ''; // 清除可能殘留的背景
            }
        };

        // 戰鬥精算與動畫
        if (val >= 30) {
            let m = MT_CONFIG.monstersData[val];
            let pDmg = player.atk - m.def;
            if (pDmg <= 0) { alert("攻擊力不足，無法破防！"); return; }

            let mDmg = Math.max(0, m.atk - player.def);
            let hitsNeeded = Math.ceil(m.hp / pDmg);
            let totalDmgTaken = (hitsNeeded - 1) * mDmg;

            if (player.hp <= totalDmgTaken) { alert(`打不過！預計損失 ${totalDmgTaken} HP`); return; }

            // 準備圖片資料與最大血量
            let customImg = MT_CONFIG.resourcesData[val];
            let mImgUrl = m.img || customImg;
            let mHtml = mImgUrl ? `<img src="${mImgUrl}" style="width:100%; height:100%; object-fit:contain; filter:drop-shadow(0 3px 2px rgba(0,0,0,0.5));">` : '👾';

            const classImageMapping = {
                'tank': MT_CONFIG.resourcesData[201],
                'warrior': MT_CONFIG.resourcesData[202],
                'mage': MT_CONFIG.resourcesData[203]
            };
            let pImgUrl = classImageMapping[player.classType] || MT_CONFIG.resourcesData[2];
            let pHtml = pImgUrl ? `<img src="${pImgUrl}" style="width:100%; height:100%; object-fit:contain; filter:drop-shadow(0 3px 2px rgba(0,0,0,0.5));">` : '🧑';

            // 鎖定控制權，開始播放戰鬥動畫
            isAnimating = true;
            try {
                await playBattleAnimation(
                    { name: player.classType.toUpperCase(), hp: player.hp, maxHp: player.hp, atk: player.atk, def: player.def, html: pHtml },
                    { name: m.name, hp: m.hp, maxHp: m.hp, atk: m.atk, def: m.def, html: mHtml }
                );
            } catch (e) { console.error(e); } finally { isAnimating = false; } // 確保動畫出錯也會解除鎖定

            // 扣血結算
            player.hp -= totalDmgTaken;
            player.exp += m.exp;
            checkLevelUp();

            if (val === 35) {
                alert("🎉 恭喜通關！");
                checkReward(currentFloor, true);
            }

            // 🚀 戰鬥結束後，將怪物的格子變回地板並移動玩家
            turnIntoFloor(nx, ny);

            player.x = nx; player.y = ny;
            drawPlayer();
            updateUI();

            return; // 戰鬥分支已處理完畢，提早結束函數
        }

        // 非戰鬥的物品與門處理 (撿鑰匙、開門等)
        if (val !== 0 && val !== 2) {
            turnIntoFloor(nx, ny); // 🚀 同樣呼叫還原地板的函式
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

    // ==========================================
    // 5. 戰鬥動畫系統
    // ==========================================
    async function playBattleAnimation(pStats, mStats) {
        const modal = document.getElementById('battle-modal');
        modal.classList.remove('d-none');

        // 初始化 UI 與圖片
        document.getElementById('battle-player-img').innerHTML = pStats.html;
        document.getElementById('battle-monster-img').innerHTML = mStats.html;
        document.getElementById('battle-player-name').innerText = pStats.name;
        document.getElementById('battle-monster-name').innerText = mStats.name;

        let currentPhp = pStats.hp;
        let currentMhp = mStats.hp;

        // 更新血量條的內部函數
        const updateHpUi = () => {
            document.getElementById('battle-player-hp-text').innerText = Math.max(0, currentPhp);
            document.getElementById('battle-monster-hp-text').innerText = Math.max(0, currentMhp);
            let pPct = Math.max(0, (currentPhp / pStats.maxHp) * 100);
            let mPct = Math.max(0, (currentMhp / mStats.maxHp) * 100);
            document.getElementById('battle-player-hp-bar').style.width = `${pPct}%`;
            document.getElementById('battle-monster-hp-bar').style.width = `${mPct}%`;
        };
        updateHpUi();

        await delay(600); // 讓玩家看一下雙方陣勢

        let pDmg = Math.max(1, pStats.atk - mStats.def);
        let mDmg = Math.max(0, mStats.atk - pStats.def);

        const pNode = document.getElementById('battle-player-img');
        const mNode = document.getElementById('battle-monster-img');

        // 飄字控制函數
        function showDmgText(targetNode, dmg) {
            let floatEl = document.createElement('div');
            floatEl.className = 'dmg-float';
            floatEl.innerText = `-${dmg}`;
            targetNode.appendChild(floatEl);
            setTimeout(() => floatEl.remove(), 800);
        }

        // 自動回合制動畫迴圈
        while (currentMhp > 0 && currentPhp > 0) {
            // 玩家攻擊回合
            pNode.classList.add('anim-attack-right');
            await delay(120); // 衝刺瞬間
            mNode.classList.add('anim-hurt');
            showDmgText(mNode, pDmg);
            currentMhp -= pDmg;
            updateHpUi();
            await delay(130); // 收招
            pNode.classList.remove('anim-attack-right');
            mNode.classList.remove('anim-hurt');

            if (currentMhp <= 0) break; // 怪物死掉就提早結束

            // 怪物反擊回合
            mNode.classList.add('anim-attack-left');
            await delay(120);
            pNode.classList.add('anim-hurt');
            showDmgText(pNode, mDmg);
            currentPhp -= mDmg;
            updateHpUi();
            await delay(130);
            mNode.classList.remove('anim-attack-left');
            pNode.classList.remove('anim-hurt');
        }

        await delay(600); // 戰鬥結束稍微停留一下，看清楚結算血量
        modal.classList.add('d-none');
    }

    initGame();
});