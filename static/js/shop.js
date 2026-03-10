// 點數商城互動邏輯
let currentForm = null;

// 確認兌換彈窗處理
function confirmRedeem(prodId, prodName, price, btnElement) {
    currentForm = btnElement.closest('form'); //* 記錄當前提交的表單
    const modalProdName = document.getElementById('modal-prod-name');
    if (modalProdName) {
        modalProdName.innerText = prodName;
    }

    const confirmModal = new bootstrap.Modal(document.getElementById('confirmModal'));
    confirmModal.show();
}

document.addEventListener("DOMContentLoaded", function () {
    // 綁定最終確認按鈕
    const finalConfirmBtn = document.getElementById('final-confirm-btn');
    if (finalConfirmBtn) {
        finalConfirmBtn.addEventListener('click', function () {
            if (currentForm) {
                currentForm.submit();
            }
        });
    }

    // 成功訊息自動彈出邏輯
    const successModalEl = document.getElementById('successModal');
    if (successModalEl) {
        const successModal = new bootstrap.Modal(successModalEl);
        successModal.show();
    }

    // 紅利點數動態計算邏輯
    const bonusInputs = document.querySelectorAll('.bonus-input');
    bonusInputs.forEach(input => {
        input.addEventListener('input', function () {
            let val = parseInt(this.value) || 0;
            const price = parseInt(this.getAttribute('data-price'));
            const maxBonus = parseInt(this.getAttribute('data-max-bonus'));
            const maxAllowed = Math.min(price, maxBonus); //* 不可超過商品售價或持有紅利

            if (val > maxAllowed) this.value = maxAllowed;
            if (val < 0) this.value = 0;

            const remainDeposit = price - (parseInt(this.value) || 0);
            const summarySpan = this.closest('form').querySelector('.deposit-calc');
            if (summarySpan) {
                summarySpan.innerText = remainDeposit;
            }
        });
    });
});