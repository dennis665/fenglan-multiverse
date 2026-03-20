// AI 教材大腦前端互動邏輯

// ==========================================
// 頁面初始化與基礎互動 (檔案上傳、Markdown 等)
// ==========================================
document.addEventListener('DOMContentLoaded', function () {
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('materialFile');
    const fileNameDisplay = document.getElementById('fileNameDisplay');

    // ... [保留原本上傳檔案區塊的邏輯不變] ...
    if (uploadZone && fileInput) {
        uploadZone.addEventListener('click', () => fileInput.click());
        uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadZone.classList.add('dragover');
        });
        uploadZone.addEventListener('dragleave', () => {
            uploadZone.classList.remove('dragover');
        });
        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadZone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                fileInput.files = e.dataTransfer.files;
                updateFileName();
            }
        });
        fileInput.addEventListener('change', updateFileName);
    }
    function updateFileName() {
        if (fileInput.files.length > 0) {
            fileNameDisplay.textContent = fileInput.files[0].name;
            fileNameDisplay.classList.add('text-primary', 'fw-bold');
        }
    }

    // 清除 AI 產生的選項前綴空白
    document.querySelectorAll('.opt-text').forEach(el => {
        el.textContent = el.textContent.trim();
    });

    // 初始化作答進度
    if (document.getElementById('total-q')) {
        updateQuizProgress();
    }

    // 處理「訓練 AI」按鈕的防呆與 Loading 狀態
    const trainForms = document.querySelectorAll('.train-ai-form');
    trainForms.forEach(form => {
        form.addEventListener('submit', function (e) {
            const btn = this.querySelector('.train-btn');
            if (btn.disabled) { e.preventDefault(); return; }
            const icon = btn.querySelector('.btn-icon');
            const spinner = btn.querySelector('.btn-spinner');
            const text = btn.querySelector('.btn-text');
            btn.disabled = true;
            btn.classList.replace('btn-outline-primary', 'btn-primary');
            if (icon) icon.classList.add('d-none');
            if (spinner) spinner.classList.remove('d-none');
            if (text && typeof STUDY_BRAIN_I18N !== 'undefined') {
                text.textContent = STUDY_BRAIN_I18N.trainingText;
            }
        });
    });

    // 啟動 Markdown 解析
    const rawMarkdownInput = document.getElementById('raw-markdown');
    const contentDiv = document.getElementById('summary-content');
    if (contentDiv && rawMarkdownInput && rawMarkdownInput.value) {
        const rawMarkdown = rawMarkdownInput.value;
        let cleanedText = rawMarkdown.trimStart();
        cleanedText = cleanedText.replace(/\u00A0/g, " ");
        if (typeof marked !== 'undefined') {
            contentDiv.innerHTML = marked.parse(cleanedText);
        } else {
            console.error("Marked.js is not loaded.");
        }
    }

    // 初始化 AI 深度解析的 Modal 實例
    if (document.getElementById('deepAnalysisModal')) {
        deepAnalysisModal = new bootstrap.Modal(document.getElementById('deepAnalysisModal'));
    }

    // ==========================================
    // 🌟 新增：測驗自動存檔與還原系統 (LocalStorage)
    // ==========================================
    const quizForm = document.getElementById('quizForm');
    const clearBtn = document.getElementById('clearProgressBtn');

    // 從網址列或隱藏欄位中取得 Material ID 當作存檔 Key
    // 我們抓 form 的 action URL 裡面的 ID 來用，這樣最穩
    let storageKey = 'quiz_progress_unknown';
    if (quizForm && quizForm.action) {
        const urlParts = quizForm.action.split('/');
        // 假設 URL 格式為 /study_brain/api/submit_quiz/15/
        const idPart = urlParts[urlParts.length - 2];
        if (!isNaN(idPart)) storageKey = `quiz_progress_record_${idPart}`;
    }

    if (quizForm) {
        // --- 還原上次作答進度 ---
        const savedProgress = localStorage.getItem(storageKey);
        if (savedProgress) {
            try {
                const answers = JSON.parse(savedProgress);
                for (const [qName, qValue] of Object.entries(answers)) {
                    const qIndex = qName.split('_')[1];
                    if (!qIndex) continue;

                    // 尋找畫面上對應的那一題選項並模擬點擊
                    const optionDiv = document.querySelector(`.q-opt-${qIndex}[data-value="${CSS.escape(qValue)}"]`);
                    if (optionDiv) {
                        optionDiv.click(); // 這會觸發下方的 selectOption()
                    }
                }
            } catch (e) {
                console.error("讀取存檔失敗", e);
            }
        }

        // --- 使用者每次點擊選項時，自動存檔 ---
        quizForm.addEventListener('click', function (e) {
            const clickedOption = e.target.closest('.quiz-option');
            if (clickedOption) {
                // 延遲一點點，等 hidden input 被寫入後再抓取
                setTimeout(() => {
                    const currentAnswers = {};
                    const hiddenInputs = quizForm.querySelectorAll('input[type="hidden"][name^="question_"]');
                    hiddenInputs.forEach(input => {
                        if (input.value) {
                            currentAnswers[input.name] = input.value;
                        }
                    });
                    localStorage.setItem(storageKey, JSON.stringify(currentAnswers));
                }, 50);
            }
        });

        // --- 送出考卷時清空存檔 ---
        quizForm.addEventListener('submit', function () {
            localStorage.removeItem(storageKey);
        });
    }

    // --- 清除按鈕邏輯 ---
    if (clearBtn) {
        clearBtn.addEventListener('click', function () {
            if (confirm('🚨 確定要清除目前所有已點選的答案，並重新開始作答嗎？')) {
                localStorage.removeItem(storageKey);
                window.location.reload();
            }
        });
    }
});

// ==========================================
// 測驗互動邏輯 (選項點擊、進度條更新、表單提交)
// ==========================================

// 測驗選項點擊與提交邏輯
function selectOption(questionId, optionElement) {
    // 移除同題目其他選項的選取狀態
    const options = document.querySelectorAll(`.q-opt-${questionId}`);
    options.forEach(opt => opt.classList.remove('selected'));

    // 標記當前選取的選項
    optionElement.classList.add('selected');

    // 將選取的值寫入隱藏的 input 以供表單提交
    const hiddenInput = document.getElementById(`input-q-${questionId}`);
    if (hiddenInput) {
        hiddenInput.value = optionElement.dataset.value.trim();
    }

    // 觸發更新作答進度計算
    updateQuizProgress();
}

// 更新已作答與未作答數量計算邏輯 (並控制按鈕解鎖)
function updateQuizProgress() {
    const totalEl = document.getElementById('total-q');
    const answeredEl = document.getElementById('answered-q');
    const unansweredEl = document.getElementById('unanswered-q');

    // 取得提交按鈕與警告文字
    const submitBtn = document.getElementById('submit-quiz-btn');
    const submitWarning = document.getElementById('submit-warning');

    if (!totalEl || !answeredEl || !unansweredEl) return;

    const totalQuestions = parseInt(totalEl.innerText) || 0;
    // 準確計算畫面上被標記為 'selected' 的選項數量
    const answeredQuestions = document.querySelectorAll('.quiz-option.selected').length;
    const unansweredQuestions = totalQuestions - answeredQuestions;

    // 更新進度條數字
    answeredEl.innerText = answeredQuestions;
    unansweredEl.innerText = unansweredQuestions;

    // 驗證邏輯：如果未答題數為 0，且總題數大於 0，就解鎖按鈕
    if (submitBtn) {
        if (unansweredQuestions === 0 && totalQuestions > 0) {
            submitBtn.disabled = false;
            submitBtn.classList.remove('disabled');
            if (submitWarning) submitWarning.style.display = 'none'; // 隱藏警告
        } else {
            submitBtn.disabled = true;
            submitBtn.classList.add('disabled');
            if (submitWarning) submitWarning.style.display = 'block'; // 顯示警告
        }
    }
}

// 鎖定按鈕並顯示載入中動畫 (防連點機制，針對呼叫 AI 擴充題目)
function showLoadingState(form) {
    const generateBtn = document.getElementById('generate-btn');
    const backBtn = document.getElementById('back-btn');

    if (generateBtn) {
        // 使用 setTimeout 確保表單能順利送出後再鎖定按鈕
        setTimeout(() => {
            generateBtn.disabled = true;
            generateBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>AI 訓練中，請稍候...';

            if (backBtn) {
                backBtn.classList.add('disabled');
                backBtn.style.pointerEvents = 'none';
            }
        }, 0);
    }
    return true;
}

// ==========================================
// AI 深度解析與不計分練習邏輯
// ==========================================

let deepAnalysisModal;

function openDeepAnalysis(analysisId, questionIndex, btnElement) {
    if (!deepAnalysisModal) return;

    deepAnalysisModal.show();

    const loadingZone = document.getElementById('da-loading');
    const contentZone = document.getElementById('da-content');
    const expZone = document.getElementById('da-explanation');
    const practiceZone = document.getElementById('da-practice-zone');

    // 重置 Modal 狀態
    loadingZone.classList.remove('d-none');
    contentZone.classList.add('d-none');
    expZone.innerHTML = '';
    practiceZone.innerHTML = '';

    // 發送 API 請求
    fetch(`/study_brain/api/analysis/${analysisId}/deep_analysis/${questionIndex}/`)
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // 如果是新生成的，把外面的按鈕偷換成 "AI 教學" 樣式
                if (data.is_new && btnElement) {
                    btnElement.className = 'btn btn-sm btn-info rounded-pill fw-bold text-white shadow-sm';
                    btnElement.innerHTML = '<i class="fas fa-chalkboard-teacher me-1"></i>AI 教學';
                }

                // 渲染 Markdown 解析
                expZone.innerHTML = typeof marked !== 'undefined' ? marked.parse(data.concept_explanation) : data.concept_explanation;

                // 渲染 3 題練習題
                let practiceHtml = '';
                data.practice_questions.forEach((q, idx) => {
                    practiceHtml += `
                    <div class="card shadow-sm mb-4 border-0 bg-light">
                        <div class="card-body p-4">
                            <h6 class="fw-bold text-dark mb-3"><span class="text-success me-1">練習 ${idx + 1}.</span> ${q.question}</h6>
                            <div class="row g-2">
                    `;

                    const letters = ['A', 'B', 'C', 'D'];
                    q.options.forEach((opt, optIdx) => {
                        // 判斷這個選項是否為正確答案 (簡單比對字串)
                        const isCorrect = (q.answer.includes(opt) || opt.includes(q.answer)) ? 'true' : 'false';

                        practiceHtml += `
                                <div class="col-12">
                                    <div class="p-3 border rounded bg-white mini-opt" style="cursor: pointer; transition: 0.2s;" 
                                         onclick="checkMiniAnswer(this, ${isCorrect}, 'mini-exp-${idx}')">
                                        <span class="fw-bold text-success me-2">${letters[optIdx]}.</span> ${opt}
                                    </div>
                                </div>
                        `;
                    });

                    practiceHtml += `
                            </div>
                            <div id="mini-exp-${idx}" class="mt-3 p-3 bg-white border-start border-4 border-success rounded d-none shadow-sm">
                                <span class="badge bg-success mb-2">正確解答</span>
                                <p class="mb-0 fw-bold">${q.answer}</p>
                                <hr class="my-2">
                                <span class="badge bg-secondary mb-2">AI 解析</span>
                                <p class="mb-0 small text-muted">${q.explanation}</p>
                            </div>
                        </div>
                    </div>
                    `;
                });

                practiceZone.innerHTML = practiceHtml;

                // 切換顯示
                loadingZone.classList.add('d-none');
                contentZone.classList.remove('d-none');
            } else {
                alert('載入失敗：' + data.message);
                deepAnalysisModal.hide();
            }
        })
        .catch(err => {
            console.error(err);
            alert('系統連線異常，請稍後再試！');
            deepAnalysisModal.hide();
        });
}

// 跳窗內的不計分測驗對答案邏輯
function checkMiniAnswer(element, isCorrect, expId) {
    // 找到同題目的所有選項，鎖定不給點，並取消樣式
    const siblings = element.parentElement.parentElement.querySelectorAll('.mini-opt');
    siblings.forEach(el => {
        el.style.pointerEvents = 'none'; // 鎖定
        el.classList.remove('border-primary', 'bg-white');
    });

    // 依據對錯給予顏色回饋
    if (isCorrect) {
        element.classList.add('bg-success', 'text-white', 'border-success');
    } else {
        element.classList.add('bg-danger', 'text-white', 'border-danger');
    }

    // 展開解析
    const expDiv = document.getElementById(expId);
    if (expDiv) {
        expDiv.classList.remove('d-none');
        // 用一點動畫效果展現
        expDiv.style.opacity = 0;
        setTimeout(() => expDiv.style.opacity = 1, 50);
    }
}