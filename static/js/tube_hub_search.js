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

    // 下載表單送出邏輯升級
    const btnDownload = document.getElementById('btnDownload');
    if (btnDownload) {
        btnDownload.addEventListener('click', async () => {
            btnDownload.disabled = true;
            btnDownload.innerText = '處理中，這可能需要幾分鐘...';

            const formData = new URLSearchParams();

            try {
                formData.append('url', document.getElementById('selectedUrl').value);
                formData.append('title', document.getElementById('selectedTitle').value);
                formData.append('category', document.getElementById('category').value);
                formData.append('personal_notes', document.getElementById('personalNotes').value);

                //* 傳遞資料夾與公開狀態
                formData.append('folder_name', document.getElementById('folderName').value);
                formData.append('is_public', document.getElementById('isPublic').checked);

                const response = await fetch('/tube_hub/download/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: formData.toString()
                });
                const data = await response.json();

                if (data.status === 'success') {
                    window.location.href = `/tube_hub/player/${data.resource_id}/`;
                } else {
                    alert('處理失敗: ' + data.message);
                }
            } catch (error) {
                console.error(error);
                alert('發生系統錯誤，請查看 Console。');
            } finally {
                btnDownload.disabled = false;
                btnDownload.innerText = '確認下載並自動分析字幕';
            }
        });
    }

    // 處理社群公開資源的一鍵收藏
    document.querySelectorAll('.btn-collect').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const resourceId = e.currentTarget.dataset.id;
            e.currentTarget.disabled = true;
            e.currentTarget.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 處理中...';

            const formData = new URLSearchParams();
            formData.append('resource_id', resourceId);

            try {
                const response = await fetch('/tube_hub/collect_public_resource/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: formData.toString()
                });
                const data = await response.json();

                if (data.status === 'success') {
                    window.location.href = `/tube_hub/player/${data.resource_id}/`;
                } else {
                    alert('收藏失敗: ' + (data.message || '未知錯誤'));
                    e.currentTarget.disabled = false;
                    e.currentTarget.innerHTML = '<i class="fas fa-bookmark"></i> 收藏';
                }
            } catch (error) {
                console.error(error);
                alert('系統發生錯誤。');
                e.currentTarget.disabled = false;
            }
        });
    });

    // 處理「我的收藏」移除邏輯 (含垃圾回收)
    document.querySelectorAll('.btn-delete-resource').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            // 避免點擊事件冒泡觸發其他動作 (例如點到外層的 <a> 標籤)
            e.preventDefault();
            e.stopPropagation();

            if (!confirm('確定要從您的收藏中移除此資源嗎？\n(若無其他人收藏，伺服器將會清除該檔案以釋放空間)')) {
                return;
            }

            const resourceId = e.currentTarget.dataset.id;
            const listItem = e.currentTarget.closest('.list-group-item'); //* 取得整列元素
            const originalHtml = e.currentTarget.innerHTML;

            e.currentTarget.disabled = true;
            e.currentTarget.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

            const formData = new URLSearchParams();
            formData.append('resource_id', resourceId);

            try {
                const response = await fetch('/tube_hub/delete_resource/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: formData.toString()
                });
                const data = await response.json();

                if (data.status === 'success') {
                    // 畫面動畫移除該列
                    listItem.style.transition = 'opacity 0.3s ease';
                    listItem.style.opacity = '0';
                    setTimeout(() => {
                        listItem.remove();

                        //* 如果清單空了，顯示提示訊息
                        const listGroup = document.querySelector('.col-md-6 .list-group');
                        if (listGroup && listGroup.children.length === 0) {
                            listGroup.innerHTML = '<p class="text-muted text-center py-3 bg-secondary rounded" id="emptyCollectionMsg">尚無個人收藏</p>';
                        }
                    }, 300);
                } else {
                    alert('移除失敗: ' + (data.message || '未知錯誤'));
                    e.currentTarget.disabled = false;
                    e.currentTarget.innerHTML = originalHtml;
                }
            } catch (error) {
                console.error(error);
                alert('系統發生錯誤。');
                e.currentTarget.disabled = false;
                e.currentTarget.innerHTML = originalHtml;
            }
        });
    });

    // 處理事後設定「公開/私有」狀態
    document.querySelectorAll('.public-toggle-switch').forEach(switchBtn => {
        switchBtn.addEventListener('change', async (e) => {
            const resourceId = e.target.dataset.id;
            const isPublic = e.target.checked;

            const formData = new URLSearchParams();
            formData.append('resource_id', resourceId);
            formData.append('is_public', isPublic);

            try {
                const response = await fetch('/tube_hub/toggle_public/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: formData.toString()
                });
                const data = await response.json();

                if (data.status !== 'success') {
                    alert('狀態更新失敗: ' + (data.message || '未知錯誤'));
                    // 失敗時把開關切回原本的狀態
                    e.target.checked = !isPublic;
                }
            } catch (error) {
                console.error(error);
                alert('系統發生錯誤。');
                // 失敗時把開關切回原本的狀態
                e.target.checked = !isPublic;
            }
        });
    });

    // 處理「移動資源到指定資料夾」邏輯
    document.querySelectorAll('.btn-move-to-folder').forEach(item => {
        item.addEventListener('click', async (e) => {
            e.preventDefault();
            const resourceId = e.currentTarget.dataset.resourceId;
            const folderId = e.currentTarget.dataset.folderId; // 如果是空的，代表移回根目錄

            const formData = new URLSearchParams();
            formData.append('resource_id', resourceId);
            formData.append('folder_id', folderId);

            try {
                const response = await fetch('/tube_hub/move_resource/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: formData.toString()
                });
                const data = await response.json();

                if (data.status === 'success') {
                    // 移動成功後重新整理頁面，以更新折疊清單的顯示狀態
                    window.location.reload();
                } else {
                    alert('移動失敗: ' + (data.message || '未知錯誤'));
                }
            } catch (error) {
                console.error(error);
                alert('系統發生錯誤。');
            }
        });
    });
});