// 幸運大轉盤核心控制邏輯
let participants = [];
let prizes = [];
let currentRotation = 0;
let recordCount = 0;

// 讀取 Excel 人員名單
const excelInput = document.getElementById('excelInput');
if (excelInput) {
    excelInput.addEventListener('change', function (e) {
        const reader = new FileReader();
        reader.onload = function (e) {
            const data = new Uint8Array(e.target.result);
            const workbook = XLSX.read(data, { type: 'array' });
            const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
            const json = XLSX.utils.sheet_to_json(firstSheet, { header: 1 });
            participants = json.map(row => row[0]).filter(name => name && name !== "姓名" && name !== "Name"); //* 過濾標頭
            document.getElementById('userCount').innerHTML = `<i class="fas fa-check-circle text-success"></i> ${LUCKY_I18N.importSuccess} ${participants.length}`;
        };
        reader.readAsArrayBuffer(e.target.files[0]);
    });
}

// 繪製轉盤邏輯
function drawWheel() {
    const isIgnoreWeight = document.getElementById('ignoreWeight').checked;
    const canvas = document.getElementById('wheelCanvas');
    const ctx = canvas.getContext('2d');
    const names = document.querySelectorAll('.prize-name');
    const weights = document.querySelectorAll('.prize-weight');
    const qtys = document.querySelectorAll('.prize-qty');

    prizes = [];
    names.forEach((n, i) => {
        let q = parseInt(qtys[i].value);
        if (n.value && (q > 0 || q === -1)) {
            prizes.push({
                name: n.value,
                weight: isIgnoreWeight ? 1 : (parseFloat(weights[i].value) || 0)
            });
        }
    });

    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const radius = centerX - 10;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (prizes.length === 0) {
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
        ctx.fillStyle = "#e9ecef";
        ctx.fill();
        ctx.textAlign = "center";
        ctx.fillStyle = "#6c757d";
        ctx.font = "bold 20px Arial";
        ctx.fillText(LUCKY_I18N.wheelEmpty, centerX, centerY);
        return;
    }

    const totalWeight = prizes.reduce((sum, p) => sum + p.weight, 0);
    let startAngle = 0;

    prizes.forEach((prize, i) => {
        const sliceAngle = (prize.weight / totalWeight) * 2 * Math.PI;
        ctx.beginPath();
        ctx.moveTo(centerX, centerY);
        ctx.arc(centerX, centerY, radius, startAngle, startAngle + sliceAngle);
        ctx.closePath();
        ctx.fillStyle = `hsl(${(i * 360) / prizes.length}, 70%, 60%)`; //* 自動配色
        ctx.fill();
        ctx.stroke();

        ctx.save();
        ctx.translate(centerX, centerY);
        ctx.rotate(startAngle + sliceAngle / 2);
        ctx.textAlign = "right";
        ctx.fillStyle = "white";
        ctx.font = "bold 16px Arial";
        ctx.fillText(prize.name, radius - 20, 10);
        ctx.restore();
        startAngle += sliceAngle;
    });
}

// 開始抽獎動畫
function startSpin() {
    if (participants.length === 0) return alert(LUCKY_I18N.importError);

    const isIgnoreWeight = document.getElementById('ignoreWeight').checked;
    const names = document.querySelectorAll('.prize-name');
    const weights = document.querySelectorAll('.prize-weight');
    const qtys = document.querySelectorAll('.prize-qty');

    prizes = [];
    names.forEach((n, i) => {
        let q = parseInt(qtys[i].value);
        if (n.value && (q > 0 || q === -1)) {
            prizes.push({
                name: n.value,
                weight: isIgnoreWeight ? 1 : (parseFloat(weights[i].value) || 0),
                qty: q,
                index: i
            });
        }
    });

    if (prizes.length === 0) return alert(LUCKY_I18N.prizesOut);

    const totalWeight = prizes.reduce((sum, p) => sum + p.weight, 0);
    let random = Math.random() * totalWeight;
    let selectedPrize = null;
    let accumulatedWeight = 0;
    let prizeStartAngle = 0;
    let prizeSliceAngle = 0;

    for (let p of prizes) {
        prizeSliceAngle = (p.weight / totalWeight) * 360;
        if (random < p.weight + accumulatedWeight && !selectedPrize) {
            selectedPrize = p;
            prizeStartAngle = (accumulatedWeight / totalWeight) * 360;
        }
        accumulatedWeight += p.weight;
    }

    if (!selectedPrize) selectedPrize = prizes[prizes.length - 1];

    const canvas = document.getElementById('wheelCanvas');
    const centerOfSlice = prizeStartAngle + (prizeSliceAngle / 2);
    const targetRotation = 270 - centerOfSlice;
    const currentRotationBase = Math.ceil(currentRotation / 360) * 360;
    currentRotation = currentRotationBase + 1800 + targetRotation;

    canvas.style.transform = `rotate(${currentRotation}deg)`;

    const winner = participants[Math.floor(Math.random() * participants.length)];
    const btn = document.getElementById('drawBtn');
    btn.disabled = true;

    setTimeout(() => {
        btn.disabled = false;
        if (selectedPrize.qty !== -1) {
            let newQty = selectedPrize.qty - 1;
            qtys[selectedPrize.index].value = newQty;
            if (newQty === 0) {
                names[selectedPrize.index].closest('tr').classList.add('table-danger');
            }
        }
        drawWheel();
        document.getElementById('resultDisplay').innerHTML = `
            <i class="fas fa-trophy text-warning"></i> ${LUCKY_I18N.congrats} ${winner} ${LUCKY_I18N.won} ${selectedPrize.name}
        `;
        addRecord(winner, selectedPrize.name);
    }, 4000);
}

// 新增中獎紀錄
function addRecord(winner, prizeName) {
    const recordBody = document.getElementById('recordBody');
    const noRecord = document.getElementById('noRecord');
    if (noRecord) noRecord.remove();

    recordCount++;
    const now = new Date();
    const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;

    const newRow = `
        <tr class="animate__animated animate__fadeInDown">
            <td>${recordCount}</td>
            <td>${timeStr}</td>
            <td class="fw-bold">${winner}</td>
            <td><span class="badge bg-info text-dark">${prizeName}</span></td>
        </tr>
    `;

    participants = participants.filter(p => p !== winner);
    document.getElementById('userCount').innerText = `${LUCKY_I18N.remainingPeople}：${participants.length}`;
    recordBody.insertAdjacentHTML('afterbegin', newRow);
}

// 匯出 Excel
function exportToExcel() {
    const rows = document.querySelectorAll('#recordBody tr:not(#noRecord)');
    if (rows.length === 0) return alert(LUCKY_I18N.noRecordExport);

    const data = [LUCKY_I18N.excelHeaders];
    rows.forEach(row => {
        const cols = row.querySelectorAll('td');
        data.push([cols[0].innerText, cols[1].innerText, cols[2].innerText, cols[3].innerText]);
    });

    const worksheet = XLSX.utils.aoa_to_sheet(data);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, LUCKY_I18N.excelSheetName);
    XLSX.writeFile(workbook, `LuckyDraw_Result.xlsx`);
}

// UI 輔助功能
function addPrizeRow() {
    const tbody = document.querySelector('#prizeTable tbody');
    const newRow = document.createElement('tr');
    newRow.innerHTML = `
        <td><input type="text" class="form-control form-control-sm prize-name" placeholder="${LUCKY_I18N.prizePlaceholder}"></td>
        <td><input type="number" class="form-control form-control-sm prize-weight" value="10"></td>
        <td><input type="number" class="form-control form-control-sm prize-qty" value="-1"></td>
        <td><button class="btn btn-sm text-danger" onclick="this.closest('tr').remove(); drawWheel();"><i class="fas fa-times"></i></button></td>
    `;
    tbody.appendChild(newRow);
    drawWheel();
}

function clearRecords() {
    if (confirm(LUCKY_I18N.confirmClear)) {
        document.getElementById('recordBody').innerHTML = `
            <tr id="noRecord">
                <td colspan="4" class="text-center text-muted py-3">${LUCKY_I18N.noRecordsYet}</td>
            </tr>
        `;
        recordCount = 0;
    }
}

function updateExcelName() {
    const input = document.getElementById('excelInput');
    const fileNameDisplay = document.getElementById('excel-file-name');
    if (input.files.length > 0) {
        fileNameDisplay.innerText = input.files[0].name;
        fileNameDisplay.classList.remove('text-muted');
    }
}

// 事件監聽初始化
document.addEventListener('input', (e) => {
    if (e.target.classList.contains('prize-name') || e.target.classList.contains('prize-weight')) {
        drawWheel();
    }
});

window.onload = drawWheel;