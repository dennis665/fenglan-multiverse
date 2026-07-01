// 處理跨工作表設定指標矩陣的非同步交叉核對
document.addEventListener('DOMContentLoaded', function () {
    const validatorForm = document.getElementById('ics-validator-form');
    if (validatorForm) {
        validatorForm.addEventListener('submit', handleIcsValidation);
    }
});

// 處理非同步驗證發送
async function handleIcsValidation(e) {
    e.preventDefault();

    const submitBtn = document.getElementById('btn-start-validate');
    const errorBox = document.getElementById('validator-error-box');
    const errorText = document.getElementById('validator-error-text');
    const consoleBox = document.getElementById('validator-result-box');

    // * 切換為載入狀態
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> ${VALIDATOR_I18N.runningText}`;
    errorBox.style.display = 'none';
    consoleBox.innerHTML = `<div class="text-warning">[RUNNING] 正在提取 config 及 rowNumber 進行矩陣映射比對...</div>`;

    const formData = new FormData();
    formData.append('check_excel', document.getElementById('check_excel').files[0]);

    try {
        const response = await fetch(VALIDATOR_CONFIG.url, {
            method: "POST",
            body: formData,
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": VALIDATOR_CONFIG.csrfToken
            }
        });

        const data = await response.json();

        if (data.success) {
            if (data.valid) {
                // * 驗證完全正確
                consoleBox.innerHTML = `
                    <div class="text-success fw-bold">✔ [SUCCESS] ${data.message}</div>
                    <div class="text-white-50">➔ 所有資料區塊皆至少含有一行有效數值。</div>
                    <div class="text-white-50">➔ Tag 與 rowNumber 對應完全吻合。</div>
                `;
            } else {
                // * 發現指標結構錯誤
                let errorHtml = `<div class="text-danger fw-bold">❌ [FAILED] 偵測到結構或資料關聯性錯誤：</div>`;
                data.errors.forEach(err => {
                    errorHtml += `<div class="text-white ps-2">⚠ ${err}</div>`;
                });
                consoleBox.innerHTML = errorHtml;
            }
        } else {
            consoleBox.innerHTML = `<div class="text-danger">[ERROR] 驗證被迫中斷：${data.error}</div>`;
            errorText.innerText = data.error;
            errorBox.style.display = 'block';
        }
    } catch (error) {
        console.error("Validation request failed:", error);
        consoleBox.innerHTML = `<div class="text-danger">[FATAL] 網路連線逾時，或上傳檔案過大導致後端解析超時。</div>`;
        errorText.innerText = "伺服器處理連線異常，請確認檔案結構。";
        errorBox.style.display = 'block';
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `<i class="fas fa-check-circle me-1"></i> ${VALIDATOR_I18N.btnOriginText}`;
    }
}