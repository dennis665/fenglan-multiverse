// 數據比對儀表板核心邏輯
document.addEventListener('DOMContentLoaded', function () {
    // 重新選取檔案即觸發支援重新上傳
    document.querySelectorAll('input[type="file"]').forEach(input => {
        input.addEventListener('change', uploadAndRefresh);
    });

    // 綁定比對按鈕點擊事件
    const compareBtn = document.getElementById('btn-compare');
    if (compareBtn) {
        compareBtn.addEventListener('click', startComparison);
    }
});

// 檔案上傳並重新整理狀態
async function uploadAndRefresh() {
    const formData = new FormData();
    formData.append('action', 'check'); //* 強制指定為檢查動作

    const filesReport = document.querySelector('input[name="files_report"]').files;
    const filesTemplate = document.querySelector('input[name="files_template"]').files;
    const filesDb = document.querySelector('input[name="files_db"]').files;

    if (filesReport.length === 0 && filesTemplate.length === 0 && filesDb.length === 0) return;

    for (let f of filesReport) formData.append('files_report', f);
    for (let f of filesTemplate) formData.append('files_template', f);
    for (let f of filesDb) formData.append('files_db', f);

    try {
        const response = await fetch("", {
            method: "POST",
            body: formData,
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": VERIFY_CONFIG.csrfToken
            }
        });

        const data = await response.json();
        updateUI(data.status_map, data.all_matched, data.errors);
    } catch (error) {
        console.error("Fetch failed:", error);
    }
}

// 更新介面顯示狀態
function updateUI(statusMap, allMatched, errors) {
    const idList = document.getElementById('id-list');
    const checkTableBody = document.querySelector('#check-tab table tbody');
    const compareBtn = document.getElementById('btn-compare');
    const errorMsgContainer = document.getElementById('upload-error-msg');
    const errorText = document.getElementById('error-text');

    const checkIcon = '<i class="fas fa-check-square text-success fs-5"></i>';
    const crossIcon = '<i class="fas fa-window-close text-danger fs-5"></i>';

    // 處理錯誤訊息
    if (errors && errors.length > 0) {
        errorText.innerText = VERIFY_I18N.uploadError + "：" + errors.join(', ');
        errorMsgContainer.style.display = 'block';
    } else {
        errorMsgContainer.style.display = 'none';
    }

    idList.innerHTML = '';
    checkTableBody.innerHTML = '';

    const companies = Object.entries(statusMap);
    if (companies.length === 0) {
        idList.innerHTML = `<div class="p-3 text-muted small text-center">${VERIFY_I18N.noFilesDetected}</div>`;
    } else {
        let accordionHtml = '<div class="accordion accordion-flush" id="companyAccordion">';
        let tableHtml = '';

        companies.forEach(([cno, fids], index) => {
            const isFirst = index === 0;
            let companyAllComplete = true;
            let reportsHtml = '<div class="list-group list-group-flush">';

            Object.entries(fids).forEach(([fid, status]) => {
                const isComplete = status.report && status.template && status.db;
                if (!isComplete) companyAllComplete = false;

                const icon = isComplete
                    ? '<i class="fas fa-check-circle text-success float-end mt-1"></i>'
                    : '<i class="fas fa-exclamation-triangle text-warning float-end mt-1"></i>';

                reportsHtml += `<div class="list-group-item small ps-4 bg-light">${fid} ${VERIFY_I18N.reportText} ${icon}</div>`;

                tableHtml += `
                    <tr>
                        <td class="ps-3"><span class="badge bg-secondary">${cno}</span> ${fid}</td>
                        <td class="text-center">${status.report ? checkIcon : crossIcon}</td>
                        <td class="text-center">${status.template ? checkIcon : crossIcon}</td>
                        <td class="text-center">${status.db ? checkIcon : crossIcon}</td>
                    </tr>`;
            });
            reportsHtml += '</div>';

            const headerIcon = companyAllComplete
                ? '<i class="fas fa-check text-success me-2"></i>'
                : '<i class="fas fa-exclamation text-warning me-2"></i>';

            accordionHtml += `
                <div class="accordion-item">
                    <h2 class="accordion-header" id="heading-${cno}">
                        <button class="accordion-button ${isFirst ? '' : 'collapsed'} py-2 fw-bold" type="button" data-bs-toggle="collapse" data-bs-target="#collapse-${cno}">
                            ${headerIcon} ${VERIFY_I18N.companyText}: ${cno}
                        </button>
                    </h2>
                    <div id="collapse-${cno}" class="accordion-collapse collapse ${isFirst ? 'show' : ''}" data-bs-parent="#companyAccordion">
                        <div class="accordion-body p-0">${reportsHtml}</div>
                    </div>
                </div>`;
        });

        idList.innerHTML = accordionHtml + '</div>';
        checkTableBody.innerHTML = tableHtml;
    }

    compareBtn.disabled = !allMatched;
    if (allMatched) {
        compareBtn.classList.replace('btn-primary', 'btn-success');
    } else {
        compareBtn.classList.replace('btn-success', 'btn-primary');
    }
}

// 執行比對動作
async function startComparison() {
    const btn = document.getElementById('btn-compare');
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm"></span> ${VERIFY_I18N.comparing}`;

    const formData = new FormData();
    formData.append('action', 'compare');

    // 收集比對規則開關狀態並傳遞給後端
    formData.append('rule_str_match', document.getElementById('ruleStrMatch').checked);
    formData.append('rule_date_check', document.getElementById('ruleDateCheck').checked);
    formData.append('rule_empty_zero', document.getElementById('ruleEmptyZero').checked);
    formData.append('rule_tolerance', document.getElementById('ruleTolerance').checked);

    document.querySelectorAll('input[type="file"]').forEach(input => {
        for (let file of input.files) { formData.append(input.name, file); }
    });

    try {
        const response = await fetch("", {
            method: "POST",
            body: formData,
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": VERIFY_CONFIG.csrfToken
            }
        });

        const data = await response.json();
        if (data.action === "compare_results") {
            renderResults(data.diff_results);
            const resultTab = new bootstrap.Tab(document.querySelector('button[data-bs-target="#result-tab"]'));
            resultTab.show();
        }
    } catch (error) {
        alert(VERIFY_I18N.compareFailed);
    } finally {
        btn.disabled = false;
        btn.innerHTML = VERIFY_I18N.btnStartCompare;
    }
}

// 渲染比對結果清單
function renderResults(diffResults) {
    const resultContainer = document.querySelector('#result-tab .list-group');
    resultContainer.innerHTML = '';

    if (diffResults.length === 0) {
        resultContainer.innerHTML = `<div class="p-4 text-center text-muted">${VERIFY_I18N.noComparisonData}</div>`;
        return;
    }

    diffResults.forEach(res => {
        let downloadBtn = '';
        let diffText = '';
        let badgeHTML = '';
        let titleClass = 'text-dark';

        // 是否為 Schema 欄位比對錯誤
        if (res.schema_error) {
            titleClass = 'text-danger';
            diffText = '無法進行比對：報表與 Schema 欄位名稱完全無法對應';
            badgeHTML = `<span class="badge bg-danger me-3">欄位對應錯誤</span>`;
            downloadBtn = `<span class="text-danger small"><i class="fas fa-times-circle me-1"></i>設定異常</span>`;
        }
        // 有發現資料差異
        else if (res.diff_count > 0) {
            titleClass = 'text-danger';
            diffText = VERIFY_I18N.detectedDiff.replace('{count}', res.diff_count);
            badgeHTML = `<span class="badge bg-danger me-3">${VERIFY_I18N.hasDiff}</span>`;
            downloadBtn = `
                <a href="/download-diff-csv/${res.cno}/${res.fid}/" target="_blank" class="btn btn-sm btn-outline-danger">
                    <i class="fas fa-download me-1"></i>${VERIFY_I18N.downloadDiff}
                </a>`;
        }
        // 資料完全一致
        else {
            diffText = VERIFY_I18N.consistentWithDb;
            badgeHTML = `<span class="badge bg-success me-3">${VERIFY_I18N.fullyMatched}</span>`;
            downloadBtn = `<span class="text-success small"><i class="fas fa-check-double me-1"></i>${VERIFY_I18N.dataConsistent}</span>`;
        }

        resultContainer.innerHTML += `
            <div class="list-group-item d-flex justify-content-between align-items-center p-3">
                <div>
                    <span class="fw-bold ${titleClass}">${VERIFY_I18N.companyText} ${res.cno} - ${VERIFY_I18N.reportText} ${res.fid}</span>
                    <div class="small text-muted">${diffText}</div>
                </div>
                <div class="d-flex align-items-center">
                    ${badgeHTML}
                    ${downloadBtn}
                </div>
            </div>`;
    });
}