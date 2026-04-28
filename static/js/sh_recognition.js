// 世祥辨識前端互動
document.addEventListener('DOMContentLoaded', function () {
    // 辨識按鈕防呆邏輯
    const form = document.getElementById('image-recognition-form');
    const btn = document.getElementById('recognize-submit-btn');
    const loading = document.getElementById('recognize-loading');

    if (form && btn) {
        form.addEventListener('submit', function () {
            btn.disabled = true;
            btn.style.backgroundColor = '#6c757d';
            btn.innerText = '辨識中...';
            if (loading) {
                loading.style.display = 'block';
            }
        });
    }

    // 清單頁面：全選/取消全選邏輯
    const selectAllCheckbox = document.getElementById('select-all-checkbox');
    const recordCheckboxes = document.querySelectorAll('.record-checkbox');

    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function () {
            recordCheckboxes.forEach(function (checkbox) {
                checkbox.checked = selectAllCheckbox.checked;
            });
        });
    }

    // 清單頁面：刪除確認防呆邏輯
    const deleteBtn = document.getElementById('delete-btn');
    const deleteForm = document.getElementById('delete-records-form');

    if (deleteBtn && deleteForm) {
        deleteBtn.addEventListener('click', function () {
            // 檢查是否有任何 checkbox 被選取
            let isAnyChecked = false;
            recordCheckboxes.forEach(function (checkbox) {
                if (checkbox.checked) isAnyChecked = true;
            });

            if (!isAnyChecked) {
                alert('請先勾選至少一筆要刪除的資料！');
                return;
            }

            // 原生 JavaScript 確認對話框
            if (confirm('確定要刪除選取的紀錄嗎？（連同結果圖片實體檔案也會被清除）')) {
                deleteForm.submit();
            }
        });
    }
});