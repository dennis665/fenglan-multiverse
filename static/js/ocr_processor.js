// OCR 影像辨識前端邏輯控制
document.addEventListener('DOMContentLoaded', function () {
    // 💡 改用 ID 抓取表單，更精準
    const ocrForm = document.getElementById('ocrForm');
    const submitBtn = document.getElementById('submitBtn');
    const imageInput = document.getElementById('imageInput');
    const previewContainer = document.getElementById('previewContainer');
    const imagePreview = document.getElementById('imagePreview');

    // 表單送出驗證與狀態控制
    if (ocrForm) {
        ocrForm.addEventListener('submit', function (e) {
            // 先強制攔截瀏覽器的預設送出行為！
            e.preventDefault();

            // 防呆：沒選圖不給送
            if (!imageInput.files || imageInput.files.length === 0) {
                alert("請先選擇要辨識的圖片！");
                return false;
            }

            // 因為已經攔截了，現在修改 UI 絕對會成功顯示
            submitBtn.disabled = true;
            submitBtn.classList.remove('btn-primary');
            submitBtn.classList.add('btn-secondary');
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>辨識中，請稍候...';

            // 讓畫面有極短暫的時間渲染(10毫秒)，然後手動把表單推出去
            setTimeout(() => {
                ocrForm.submit();
            }, 10);
        });
    }

    // 選擇檔案即時預覽
    if (imageInput) {
        imageInput.addEventListener('change', function (event) {
            const file = event.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function (e) {
                    imagePreview.src = e.target.result;
                    previewContainer.classList.remove('d-none');
                    // 當重新選擇圖片時，確保按鈕是可點擊狀態
                    if (submitBtn.disabled) {
                        submitBtn.disabled = false;
                        submitBtn.classList.remove('btn-secondary');
                        submitBtn.classList.add('btn-primary');
                        submitBtn.innerHTML = '<i class="fas fa-search me-2"></i>開始辨識';
                    }
                }
                reader.readAsDataURL(file);
            } else {
                // 如果使用者取消選擇，隱藏預覽
                previewContainer.classList.add('d-none');
            }
        });
    }
});

// 一鍵複製文字功能
window.copyToClipboard = function () {
    const copyText = document.getElementById("ocrResultText");
    if (!copyText) return;

    copyText.select();
    copyText.setSelectionRange(0, 99999); // 支援行動裝置

    navigator.clipboard.writeText(copyText.value).then(() => {
        alert("✅ 文字已成功複製到剪貼簿！");
    }).catch(err => {
        console.error('無法複製文字: ', err);
        alert("❌ 複製失敗，請手動複製。");
    });
};