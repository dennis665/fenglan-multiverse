document.addEventListener('DOMContentLoaded', () => {
    const btnSearch = document.getElementById('btnSearch');
    const searchInput = document.getElementById('searchInput');
    const resultsContainer = document.getElementById('searchResults');
    const formContainer = document.getElementById('downloadFormContainer');

    if (btnSearch) {
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
                        div.className = 'list-group-item bg-dark text-white border-secondary list-group-item-action p-3';

                        let subBadgeHTML = '';
                        if (item.subtitles && item.subtitles.length > 0) {
                            const displayLangs = item.subtitles.slice(0, 3).join(', ');
                            const hasMore = item.subtitles.length > 3 ? ', ...' : '';
                            subBadgeHTML = `<span class="badge bg-success ms-2"><i class="fas fa-closed-captioning"></i> ${displayLangs}${hasMore}</span>`;
                        } else {
                            subBadgeHTML = `<span class="badge bg-secondary ms-2"><i class="fas fa-closed-captioning text-muted"></i> 無字幕</span>`;
                        }

                        div.innerHTML = `
                            <div class="row align-items-center g-3">
                                <div class="col-auto position-relative">
                                    <img src="${item.thumbnail}" class="rounded shadow-sm" style="width: 140px; height: 78px; object-fit: cover;">
                                    <span class="badge bg-black text-white position-absolute bottom-0 end-0 mb-1 me-3 opacity-75">${item.duration}</span>
                                </div>
                                <div class="col text-truncate">
                                    <h6 class="text-truncate fw-bold mb-1 text-info">${item.title}</h6>
                                    <div class="d-flex align-items-center mt-1">
                                        <small class="text-muted text-truncate" style="max-width: 200px;">${item.url}</small>
                                        ${subBadgeHTML} 
                                    </div>
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
    }

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
                alert('發生系統錯誤。');
            } finally {
                btnDownload.disabled = false;
                btnDownload.innerText = '確認下載並自動分析字幕';
            }
        });
    }

    // 更新資料夾數量標籤 (DOM 即時更新用)
    function updateFolderCounts() {
        document.querySelectorAll('.accordion-item').forEach(item => {
            const count = item.querySelectorAll('.list-group-item').length;
            const badge = item.querySelector('.folder-count');
            if (badge) badge.textContent = count;
        });
    }

    // 採用事件委派處理「移除」、「公開切換」與「移動」操作
    // 這樣即使 DOM 被移動，事件仍然有效
    document.addEventListener('click', async (e) => {
        // 處理社群收藏
        if (e.target.closest('.btn-collect')) {
            const btn = e.target.closest('.btn-collect');
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

            const formData = new URLSearchParams();
            formData.append('resource_id', btn.dataset.id);

            try {
                const response = await fetch('/tube_hub/collect_public_resource/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: formData.toString()
                });
                const data = await response.json();
                if (data.status === 'success') window.location.href = `/tube_hub/player/${data.resource_id}/`;
                else alert('收藏失敗');
            } catch (error) {
                console.error(error);
            }
        }

        // 處理移除個人收藏
        if (e.target.closest('.btn-delete-resource')) {
            e.preventDefault();
            if (!confirm('確定要從您的收藏中移除此資源嗎？')) return;

            const btn = e.target.closest('.btn-delete-resource');
            const listItem = btn.closest('.list-group-item');
            const originalHtml = btn.innerHTML;

            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

            const formData = new URLSearchParams();
            formData.append('resource_id', btn.dataset.id);

            try {
                const response = await fetch('/tube_hub/delete_resource/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: formData.toString()
                });
                const data = await response.json();

                if (data.status === 'success') {
                    listItem.style.transition = 'opacity 0.3s ease';
                    listItem.style.opacity = '0';
                    setTimeout(() => {
                        listItem.remove();
                        updateFolderCounts(); //* 重新計算數量
                    }, 300);
                } else {
                    alert('移除失敗');
                    btn.disabled = false;
                    btn.innerHTML = originalHtml;
                }
            } catch (error) {
                console.error(error);
                btn.disabled = false;
            }
        }

        // 處理移動資源 (即時 DOM 更新)
        if (e.target.closest('.btn-move-to-folder')) {
            e.preventDefault();
            const btn = e.target.closest('.btn-move-to-folder');
            const resourceId = btn.dataset.resourceId;
            const targetFolderId = btn.dataset.folderId;
            const listItem = btn.closest('.list-group-item');

            const formData = new URLSearchParams();
            formData.append('resource_id', resourceId);
            formData.append('folder_id', targetFolderId);

            try {
                const response = await fetch('/tube_hub/move_resource/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: formData.toString()
                });
                const data = await response.json();

                if (data.status === 'success') {
                    // 視覺化 DOM 搬移
                    listItem.style.transition = 'opacity 0.3s ease';
                    listItem.style.opacity = '0';

                    setTimeout(() => {
                        // 重置下拉選單的 active 狀態
                        listItem.querySelectorAll('.btn-move-to-folder').forEach(a => a.classList.remove('active'));
                        btn.classList.add('active');

                        let targetContainer;
                        if (!targetFolderId) {
                            // 移至最外層
                            targetContainer = document.getElementById('root-resource-list');
                            // 改背景顏色適應外層
                            listItem.classList.remove('bg-black');
                            listItem.classList.add('bg-secondary');
                        } else {
                            // 移至特定資料夾內部
                            targetContainer = document.querySelector(`.folder-resource-list[data-folder-id="${targetFolderId}"]`);
                            // 改背景顏色適應內層
                            listItem.classList.remove('bg-secondary');
                            listItem.classList.add('bg-black');
                        }

                        if (targetContainer) {
                            targetContainer.appendChild(listItem);
                            updateFolderCounts(); //* 更新資料夾數量標籤
                        }

                        listItem.style.opacity = '1';
                    }, 300);
                } else {
                    alert('移動失敗');
                }
            } catch (error) {
                console.error(error);
                alert('系統發生錯誤。');
            }
        }
    });

    // 採用事件委派處理「公開/私有」開關的 Change 事件
    document.addEventListener('change', async (e) => {
        if (e.target.classList.contains('public-toggle-switch')) {
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
                    alert('狀態更新失敗');
                    e.target.checked = !isPublic; // 恢復原狀
                }
            } catch (error) {
                console.error(error);
                e.target.checked = !isPublic;
            }
        }
    });
});