// 投資組合儀表板核心邏輯
document.addEventListener('DOMContentLoaded', function () {

    // AI 規劃表單提交動畫
    const aiForm = document.querySelector("form[action*='ai_plan']"); //* 抓取 AI 規劃表單
    if (aiForm) {
        aiForm.addEventListener('submit', function () {
            const btn = document.getElementById('ai-submit-btn');
            const btnIcon = document.getElementById('btn-icon');
            const btnSpinner = document.getElementById('btn-spinner');
            const btnText = document.getElementById('btn-text');

            btn.disabled = true;
            btn.classList.add('opacity-75');
            btnIcon.classList.add('d-none');
            btnSpinner.classList.remove('d-none');
            // 💡 從 HTML 傳入的配置讀取翻譯
            btnText.textContent = INVEST_CONFIG.trans.aiPlanning;
        });
    }

    // Chart.js 全域顏色配置
    const colors = [
        'rgba(54, 162, 235, 0.7)', 'rgba(255, 99, 132, 0.7)', 'rgba(255, 206, 86, 0.7)',
        'rgba(75, 192, 192, 0.7)', 'rgba(153, 102, 255, 0.7)', 'rgba(255, 159, 64, 0.7)',
        'rgba(199, 199, 199, 0.7)', 'rgba(83, 102, 255, 0.7)', 'rgba(40, 159, 64, 0.7)',
        'rgba(210, 199, 199, 0.7)'
    ];

    // 繪製資產配置圓餅圖
    const pieCtx = document.getElementById('portfolioPieChart');
    if (pieCtx && INVEST_CONFIG.chartData.pieLabels.length > 0) {
        new Chart(pieCtx, {
            type: 'doughnut',
            data: {
                labels: INVEST_CONFIG.chartData.pieLabels,
                datasets: [{
                    data: INVEST_CONFIG.chartData.pieData,
                    backgroundColor: colors,
                    borderWidth: 1
                }]
            },
            options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
        });
    }

    // 通用條型圖繪製函式
    function createBarChart(canvasId, labels, data, labelName, color, isHorizontal = false) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: labelName,
                    data: data,
                    backgroundColor: color,
                    borderRadius: 4
                }]
            },
            options: {
                indexAxis: isHorizontal ? 'y' : 'x',
                responsive: true,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: false } }
            }
        });
    }

    // 初始化市場數據圖表
    createBarChart('gainersChart', INVEST_CONFIG.chartData.gainersLabels, INVEST_CONFIG.chartData.gainersData, INVEST_CONFIG.trans.changePercent, 'rgba(220, 53, 69, 0.7)', true);
    createBarChart('losersChart', INVEST_CONFIG.chartData.losersLabels, INVEST_CONFIG.chartData.losersData, INVEST_CONFIG.trans.changePercent, 'rgba(25, 135, 84, 0.7)', true);
    createBarChart('highPriceChart', INVEST_CONFIG.chartData.highPriceLabels, INVEST_CONFIG.chartData.highPriceData, INVEST_CONFIG.trans.price, 'rgba(255, 193, 7, 0.7)');
    createBarChart('lowPriceChart', INVEST_CONFIG.chartData.lowPriceLabels, INVEST_CONFIG.chartData.lowPriceData, INVEST_CONFIG.trans.price, 'rgba(13, 110, 253, 0.7)');

    // 搜尋框事件監聽
    const searchInput = document.getElementById('stockSearchInput');
    if (searchInput) {
        searchInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                searchStockHistory();
            }
        });
    }
});

// 歷史走勢圖全域變數與函式
let lineChartInstance = null;

function showHistoryChart(symbol) {
    if (!symbol) return;

    const modal = new bootstrap.Modal(document.getElementById('historyChartModal'));
    modal.show();

    document.getElementById('historyModalTitle').textContent = `${INVEST_CONFIG.trans.loadingData} ${symbol}...`;

    fetch(`/invest/api/history/${symbol}/`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                document.getElementById('historyModalTitle').textContent = `❌ ${INVEST_CONFIG.trans.failedLoad} ${data.error}`;
                return;
            }

            document.getElementById('historyModalTitle').textContent = `📈 ${data.symbol} ${data.name} (${INVEST_CONFIG.trans.trend6m})`;

            const ctx = document.getElementById('stockLineChart').getContext('2d');

            if (lineChartInstance) {
                lineChartInstance.destroy();
            }

            lineChartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.dates,
                    datasets: [{
                        label: INVEST_CONFIG.trans.closePrice,
                        data: data.prices,
                        borderColor: 'rgba(54, 162, 235, 1)',
                        backgroundColor: 'rgba(54, 162, 235, 0.1)',
                        borderWidth: 2,
                        pointRadius: 0,
                        pointHoverRadius: 6,
                        fill: true,
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    interaction: { mode: 'index', intersect: false },
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { min: Math.min(...data.prices) * 0.95 }
                    }
                }
            });
        })
        .catch(error => {
            console.error('Error fetching data:', error);
            document.getElementById('historyModalTitle').textContent = `❌ ${INVEST_CONFIG.trans.networkError}`;
        });
}

function searchStockHistory() {
    const inputVal = document.getElementById('stockSearchInput').value.trim();
    if (inputVal) {
        showHistoryChart(inputVal);
    } else {
        alert(INVEST_CONFIG.trans.enterSymbolAlert);
    }
}