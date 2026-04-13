// 處理 PDF 開新分頁邏輯
function openPDFInNewTab(fileUrl) {

    // 使用 window.open 開啟新分頁，第二個參數 '_blank' 代表新分頁
    window.open(fileUrl, '_blank');

    console.log("已在新分頁載入檔案：" + fileUrl); //* 除錯紀錄
}