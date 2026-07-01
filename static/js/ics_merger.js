// 處理 ICS 多活頁簿樣式合併與非同步下載
document.addEventListener('DOMContentLoaded', function () {
    const mergeForm = document.getElementById('ics-merge-form');
    if (mergeForm) {
        mergeForm.addEventListener('submit', handleIcsMergeSubmit);
    }
});

// 處理表單發送非同步請求
async function handleIcsMergeSubmit(e) {
    e.preventDefault();

    const submitBtn = document.getElementById('btn-start-merge');
    const errorBox = document.getElementById('merge-error-msg');
    const errorText = document.getElementById('merge-error-text');
    const downloadBox = document.getElementById('success-download-box');

    // * 切換按鈕載入狀態避免重複點擊
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> ${ICS_I18N.mergingText}`;
    errorBox.style.display = 'none';
    downloadBox.style.display = 'none';

    const formData = new FormData();
    formData.append('main_excel', document.getElementById('main_excel').files[0]);
    formData.append('sub_excel', document.getElementById('sub_excel').files[0]);

    try {
        const response = await fetch(ICS_CONFIG.mergeUrl, {
            method: "POST",
            body: formData,
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": ICS_CONFIG.csrfToken
            }
        });

        const data = await response.json();

        if (data.success) {
            // * 合併完成，顯示下載區塊並自動觸發瀏覽器下載
            downloadBox.style.display = 'block';
            window.location.href = document.getElementById('btn-download-file').getAttribute('href');
        } else {
            errorText.innerText = data.error;
            errorBox.style.display = 'block';
        }
    } catch (error) {
        console.error("Merge request failed:", error);
        errorText.innerText = "連線伺服器發生異常，請重新再試。";
        errorBox.style.display = 'block';
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `<i class="fas fa-compress-alt me-1"></i> ${ICS_I18N.btnOriginText}`;
    }
}