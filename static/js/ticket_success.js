// 發文取號成功頁面互動邏輯
function copyToClipboard() {
    const serialElement = document.getElementById('serialNumber'); //* 抓取序號元素
    if (!serialElement) return;

    const serial = serialElement.innerText.trim();
    navigator.clipboard.writeText(serial).then(() => {
        // 💡 使用從 HTML 傳入的翻譯文字
        alert(LEDGER_I18N.copySuccess + ': ' + serial);
    });
}

// 註冊列印快捷鍵或按鈕行為
document.addEventListener('DOMContentLoaded', () => {
    // * 可以在這裡加入自動列印或其他初始邏輯
});