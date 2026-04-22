document.addEventListener('DOMContentLoaded', function () {
    // ==========================================
    // 圖片處理邏輯
    // ==========================================
    const imageForm = document.getElementById('image-compress-form');
    const imageInput = document.querySelector('input[name="image"]');
    const scaleInput = document.querySelector('input[name="scale_percent"]');
    const estBox = document.getElementById('pixel-estimation');

    let originalWidth = 0;
    let originalHeight = 0;

    if (imageInput) {
        imageInput.addEventListener('change', function (e) {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function (event) {
                    const img = new Image();
                    img.onload = function () {
                        originalWidth = img.width;
                        originalHeight = img.height;
                        updateEstimation();
                    };
                    img.src = event.target.result;
                };
                reader.readAsDataURL(file);
            }
        });
    }

    if (scaleInput) {
        scaleInput.addEventListener('input', updateEstimation);
    }

    function updateEstimation() {
        const scale = parseInt(scaleInput.value) || 100;
        if (originalWidth > 0 && originalHeight > 0) {
            const targetWidth = Math.round(originalWidth * (scale / 100));
            const targetHeight = Math.round(originalHeight * (scale / 100));

            document.getElementById('est-width').innerText = targetWidth;
            document.getElementById('est-height').innerText = targetHeight;

            if (scale !== 100) estBox.classList.remove('d-none');
            else estBox.classList.add('d-none');
        }
    }

    if (imageForm) {
        imageForm.addEventListener('submit', function () {
            const btn = document.getElementById('image-submit-btn');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 圖片處理中...';
            document.getElementById('image-result-container')?.classList.add('d-none');
            const formCont = document.getElementById('image-form-container');
            if (formCont.classList.contains('col-md-5')) {
                formCont.classList.remove('col-md-5');
                formCont.classList.add('col-md-8');
            }
        });
    }

    // ==========================================
    // 影片片段編輯與裁切邏輯 (全新實作)
    // ==========================================

    //* 隱藏 Django 表單中用不到的舊版時間欄位 (我們改用動態產生的)
    const oldStartGroup = document.getElementById('div_id_start_time');
    const oldDurationGroup = document.getElementById('div_id_duration');
    if (oldStartGroup) oldStartGroup.style.display = 'none';
    if (oldDurationGroup) oldDurationGroup.style.display = 'none';

    const videoInput = document.querySelector('input[name="videos"]');
    const fragmentContainer = document.getElementById('video-fragments-list');

    if (videoInput && fragmentContainer) {
        videoInput.addEventListener('change', function (e) {
            fragmentContainer.innerHTML = ''; //* 清除舊片段
            const files = e.target.files;

            Array.from(files).forEach((file, index) => {
                const url = URL.createObjectURL(file);
                const card = document.createElement('div');
                card.className = 'card mb-3 border-primary fragment-card shadow-sm';
                card.innerHTML = `
                    <div class="card-header bg-light d-flex justify-content-between align-items-center py-2">
                        <h6 class="mb-0 text-primary"><i class="fas fa-film me-2"></i>片段: ${file.name}</h6>
                        <div>
                            <button type="button" class="btn btn-sm btn-outline-secondary py-0" onclick="moveFragment(this, -1)" title="上移">▲</button>
                            <button type="button" class="btn btn-sm btn-outline-secondary py-0" onclick="moveFragment(this, 1)" title="下移">▼</button>
                        </div>
                    </div>
                    <div class="card-body p-2">
                        <div class="row g-2">
                            <div class="col-md-5">
                                <video id="v-preview-${index}" src="${url}" controls class="w-100 rounded bg-dark" style="height:140px; object-fit:contain;"></video>
                            </div>
                            <div class="col-md-7 d-flex flex-column justify-content-center">
                                <input type="hidden" name="f_idx[]" value="${index}">
                                
                                <div class="input-group input-group-sm mb-2">
                                    <span class="input-group-text bg-success text-white">起點 A</span>
                                    <input type="number" step="0.1" name="f_start[]" id="start-${index}" class="form-control" value="0">
                                    <button type="button" class="btn btn-outline-success" onclick="setVideoTime(${index}, 'start')">目前畫面</button>
                                </div>
                                
                                <div class="input-group input-group-sm">
                                    <span class="input-group-text bg-danger text-white">終點 B</span>
                                    <input type="number" step="0.1" name="f_end[]" id="end-${index}" class="form-control" value="0">
                                    <button type="button" class="btn btn-outline-danger" onclick="setVideoTime(${index}, 'end')">目前畫面</button>
                                </div>
                                <small class="text-muted mt-1" style="font-size: 0.75rem;">提示: 若終點為 0 代表取至影片結束</small>
                            </div>
                        </div>
                    </div>
                `;
                fragmentContainer.appendChild(card);
            });
        });
    }

    const videoForm = document.getElementById('video-compress-form');
    if (videoForm) {
        videoForm.addEventListener('submit', function () {
            const btn = document.getElementById('video-submit-btn');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-grow spinner-grow-sm"></span> 影片轉碼與拼接中...';
            document.getElementById('video-result-container')?.classList.add('d-none');
            const formCont = document.getElementById('video-form-container');
            if (formCont.classList.contains('col-md-5')) {
                formCont.classList.remove('col-md-5');
                formCont.classList.add('col-md-8');
            }
        });
    }
});

// ==========================================
// 全域輔助函式 (供 onclick 呼叫)
// ==========================================

/* 抓取當前影片播放秒數 */
window.setVideoTime = function (index, type) {
    const video = document.getElementById(`v-preview-${index}`);
    const input = document.getElementById(`${type}-${index}`);
    if (video && input) {
        input.value = video.currentTime.toFixed(2);
    }
};

/* 調整片段上下順序 */
window.moveFragment = function (btn, direction) {
    const card = btn.closest('.fragment-card');
    const container = document.getElementById('video-fragments-list');
    if (direction === -1 && card.previousElementSibling) {
        container.insertBefore(card, card.previousElementSibling);
    } else if (direction === 1 && card.nextElementSibling) {
        container.insertBefore(card.nextElementSibling, card);
    }
};