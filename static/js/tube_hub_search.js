document.addEventListener('DOMContentLoaded', () => {
    const btnSearch = document.getElementById('btnSearch'); //* 取得搜尋按鈕
    const searchInput = document.getElementById('searchInput'); //* 取得輸入框
    const resultsContainer = document.getElementById('searchResults'); //* 取得結果列表容器
    const formContainer = document.getElementById('downloadFormContainer'); //* 取得表單容器

    btnSearch.addEventListener('click', async () => {
        const query = searchInput.value.trim();
        if (!query) return;

        btnSearch.disabled = true;
        btnSearch.innerText = '搜尋中...';

        try {
            const response = await fetch(`/tube_hub/?q=${encodeURIComponent(query)}`);
            const data = await response.json();

            resultsContainer.innerHTML = '';
            if (data.status === 'success') {
                data.data.forEach(item => {
                    const div = document.createElement('div');
                    //* 調整外框 padding 讓內容有呼吸空間
                    div.className = 'list-group-item bg-dark text-white border-secondary list-group-item-action p-3';

                    //* 加入預覽圖、時間標籤與標題排版
                    div.innerHTML = `
                        <div class="row align-items-center g-3">
                            <div class="col-auto position-relative">
                                <img src="${item.thumbnail}" class="rounded shadow-sm" style="width: 140px; height: 78px; object-fit: cover;" alt="預覽圖">
                                <span class="badge bg-black text-white position-absolute bottom-0 end-0 mb-1 me-3 opacity-75">${item.duration}</span>
                            </div>
                            <div class="col text-truncate">
                                <h6 class="text-truncate fw-bold mb-1 text-info" title="${item.title}">${item.title}</h6>
                                <small class="text-muted text-truncate d-block">${item.url}</small>
                            </div>
                            <div class="col-auto">
                                <button class="btn btn-info btn-select px-4 fw-bold text-dark rounded-pill" data-url="${item.url}" data-title="${item.title}">選取</button>
                            </div>
                        </div>
                    `;
                    resultsContainer.appendChild(div);
                });

                document.querySelectorAll('.btn-select').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        document.getElementById('selectedUrl').value = e.target.dataset.url;
                        document.getElementById('selectedTitle').value = e.target.dataset.title;
                        formContainer.classList.remove('d-none');
                        window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
                    });
                });
            } else {
                resultsContainer.innerHTML = `<div class="text-center text-danger p-3">搜尋失敗：${data.message}</div>`;
            }
        } catch (error) {
            console.error(error);
        } finally {
            btnSearch.disabled = false;
            btnSearch.innerText = '搜尋';
        }
    });

    document.getElementById('btnDownload').addEventListener('click', async () => {
        const btnDownload = document.getElementById('btnDownload'); //* 取得下載按鈕
        btnDownload.disabled = true; //* 防止重複點擊
        btnDownload.innerText = '處理中，這可能需要幾分鐘...'; //* 更新按鈕文字狀態

        const formData = new URLSearchParams(); //* 建立表單資料物件

        try {
            // 將取值動作移入 try 區塊內，避免未預期的錯誤導致按鈕卡死
            formData.append('url', document.getElementById('selectedUrl').value);
            formData.append('title', document.getElementById('selectedTitle').value);
            // 修改這裡：對應 HTML 上的 category，並移除不存在的元素
            formData.append('category', document.getElementById('category').value);
            formData.append('personal_notes', document.getElementById('personalNotes').value);

            const response = await fetch('/tube_hub/download/', { //* 發送下載 POST 請求
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: formData.toString()
            });
            const data = await response.json(); //* 解析回傳資料

            if (data.status === 'success') {
                window.location.href = `/tube_hub/player/${data.resource_id}/`; //* 成功後跳轉至播放頁
            } else {
                alert('處理失敗: ' + data.message); //* 失敗提示
            }
        } catch (error) {
            console.error(error); //* 捕捉並列印錯誤
            alert('發生系統錯誤，請查看 Console。');
        } finally {
            btnDownload.disabled = false; //* 恢復按鈕狀態
            btnDownload.innerText = '確認下載並自動分析字幕'; //* 恢復按鈕文字 (建議與 HTML 統一)
        }
    });
});