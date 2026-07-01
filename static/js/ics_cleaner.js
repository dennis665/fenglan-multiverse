// 處理非同步上傳檔案並解析白名單工作表移除流程
document.addEventListener('DOMContentLoaded', function () {
    const cleanForm = document.getElementById('ics-clean-form');
    if (cleanForm) {
        cleanForm.addEventListener('submit', handleIcsCleanSubmit);
    }
});

// 處理淨化功能發送
async function handleIcsCleanSubmit(e) {
    e.preventDefault();

    const submitBtn = document.getElementById('btn-start-clean');
    const errorBox = document.getElementById('clean-error-msg');
    const errorText = document.getElementById('clean-error-text');
    const successBox = document.getElementById('clean-success-box');
    const terminal = document.getElementById('clean-log-box');

    // * 初始化外觀狀態
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> ${CLEAN_I18N.cleaningText}`;
    errorBox.style.display = 'none';
    successBox.style.display = 'none';

    terminal.innerHTML = `<div class="text-warning">[RUNNING] 正在上傳活頁簿並調用後端核心引擎...</div>`;

    const formData = new FormData();
    formData.append('dirty_excel', document.getElementById('dirty_excel').files[0]);

    try {
        const response = await fetch(CLEAN_CONFIG.cleanUrl, {
            method: "POST",
            body: formData,
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": CLEAN_CONFIG.csrfToken
            }
        });

        const data = await response.json();

        if (data.success) {
            // * 寫入虛擬終端機日誌
            let logHtml = `<div class="text-success">[SUCCESS] 成功讀取 'config' 白名單設定。</div>`;
            logHtml += `<div class="text-success">[SUCCESS] 保留核心表：config, rowNumber。</div>`;

            if (data.removed_sheets && data.removed_sheets.length > 0) {
                logHtml += `<div class="text-danger">[REMOVE] 已成功剔除以下無效工作表：</div>`;
                data.removed_sheets.forEach(s => {
                    logHtml += `<div class="text-white-50 ps-3">➔ Sheet: ${s}</div>`;
                });
            } else {
                logHtml += `<div class="text-info">[INFO] 未發現非白名單工作表，結構完全標準。</div>`;
            }

            terminal.innerHTML = logHtml;

            // * 填入數據並拉出下載區塊
            document.getElementById('lbl-removed-count').innerText = data.removed_count;
            successBox.style.display = 'block';

            // * 自動執行下載
            window.location.href = document.getElementById('btn-download-cleaned').getAttribute('href');
        } else {
            terminal.innerHTML = `<div class="text-danger">[ERROR] 程序被迫中斷。原因：${data.error}</div>`;
            errorText.innerText = data.error;
            errorBox.style.display = 'block';
        }
    } catch (error) {
        console.error("Clean request failed:", error);
        terminal.innerHTML = `<div class="text-danger">[FATAL] 網路連線逾時或後端處理崩潰。</div>`;
        errorText.innerText = "連線伺服器發生異常，請確認檔案大小是否合規。";
        errorBox.style.display = 'block';
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `<i class="fas fa-magic me-1"></i> ${CLEAN_I18N.btnOriginText}`;
    }
}