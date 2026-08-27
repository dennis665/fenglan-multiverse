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

// -------------------------------------------------------------------
// 雙股走勢與績效比對核心變數與函式
// -------------------------------------------------------------------
let compareChartInstance = null;
let currentCompareData = null;
let currentComparePeriod = '6mo';
let currentCompareMode = 'pct'; // 'pct' 或 'price'

document.addEventListener('DOMContentLoaded', function () {
    const periodBtns = document.querySelectorAll('.compare-period-btn');
    periodBtns.forEach(btn => {
        btn.addEventListener('click', function () {
            periodBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            currentComparePeriod = this.getAttribute('data-period') || '6mo';
            executeStockComparison();
        });
    });

    if (document.getElementById('compareStock1') && document.getElementById('compareStock2')) {
        executeStockComparison();
    }
});

function executeStockComparison() {
    const s1 = document.getElementById('compareStock1')?.value.trim();
    const s2 = document.getElementById('compareStock2')?.value.trim();

    if (!s1 || !s2) {
        alert('請輸入或選擇兩檔股票代碼！');
        return;
    }

    const container = document.getElementById('compareResultContainer');
    const loading = document.getElementById('compareLoading');
    const btn = document.getElementById('btnStartCompare');

    if (loading) loading.classList.remove('d-none');
    if (container) container.classList.add('d-none');
    if (btn) btn.disabled = true;

    fetch(`/invest/api/compare/?symbol1=${encodeURIComponent(s1)}&symbol2=${encodeURIComponent(s2)}&period=${currentComparePeriod}`)
        .then(response => response.json())
        .then(data => {
            if (btn) btn.disabled = false;
            if (loading) loading.classList.add('d-none');

            if (data.error) {
                alert(`❌ 雙股比對失敗：${data.error}`);
                return;
            }

            currentCompareData = data;
            if (container) container.classList.remove('d-none');
            renderCompareStatsCards(data);
            renderCompareChart(currentCompareMode);
        })
        .catch(err => {
            console.error('Comparison API error:', err);
            if (btn) btn.disabled = false;
            if (loading) loading.classList.add('d-none');
            alert('❌ 連線伺服器失敗，請稍後再試！');
        });
}

function renderCompareStatsCards(data) {
    if (!data) return;

    document.getElementById('statStock1Name').textContent = `${data.stock1.name}`;
    document.getElementById('statStock1Symbol').textContent = `${data.stock1.symbol}`;
    document.getElementById('statStock1Price').textContent = `NT$ ${data.stock1.latest_price}`;

    const ret1El = document.getElementById('statStock1Return');
    ret1El.textContent = `${data.stock1.total_return > 0 ? '+' : ''}${data.stock1.total_return}%`;
    ret1El.className = `fw-bold fs-6 ${data.stock1.total_return > 0 ? 'text-danger' : (data.stock1.total_return < 0 ? 'text-success' : 'text-dark')}`;

    document.getElementById('statStock1Range').textContent = `$${data.stock1.high_price} / $${data.stock1.low_price}`;

    document.getElementById('statStock2Name').textContent = `${data.stock2.name}`;
    document.getElementById('statStock2Symbol').textContent = `${data.stock2.symbol}`;
    document.getElementById('statStock2Price').textContent = `NT$ ${data.stock2.latest_price}`;

    const ret2El = document.getElementById('statStock2Return');
    ret2El.textContent = `${data.stock2.total_return > 0 ? '+' : ''}${data.stock2.total_return}%`;
    ret2El.className = `fw-bold fs-6 ${data.stock2.total_return > 0 ? 'text-danger' : (data.stock2.total_return < 0 ? 'text-success' : 'text-dark')}`;

    document.getElementById('statStock2Range').textContent = `$${data.stock2.high_price} / $${data.stock2.low_price}`;
}

function switchCompareChartMode(mode) {
    currentCompareMode = mode;
    if (currentCompareData) {
        renderCompareChart(mode);
    }
}

function renderCompareChart(mode = 'pct') {
    if (!currentCompareData) return;

    const ctx = document.getElementById('compareLineChart')?.getContext('2d');
    if (!ctx) return;

    if (compareChartInstance) {
        compareChartInstance.destroy();
    }

    const data = currentCompareData;
    const isPct = (mode === 'pct');

    const dataset1 = {
        label: `${data.stock1.symbol} ${data.stock1.name}`,
        data: isPct ? data.pct1 : data.prices1,
        borderColor: 'rgba(13, 110, 253, 1)',
        backgroundColor: 'rgba(13, 110, 253, 0.05)',
        borderWidth: 2.5,
        pointRadius: 0,
        pointHoverRadius: 6,
        fill: false,
        tension: 0.1,
        yAxisID: 'y'
    };

    const dataset2 = {
        label: `${data.stock2.symbol} ${data.stock2.name}`,
        data: isPct ? data.pct2 : data.prices2,
        borderColor: 'rgba(220, 53, 69, 1)',
        backgroundColor: 'rgba(220, 53, 69, 0.05)',
        borderWidth: 2.5,
        pointRadius: 0,
        pointHoverRadius: 6,
        fill: false,
        tension: 0.1,
        yAxisID: isPct ? 'y' : 'y2'
    };

    const scalesConfig = {
        x: {
            grid: { display: false },
            ticks: { maxTicksLimit: 12 }
        },
        y: {
            type: 'linear',
            display: true,
            position: 'left',
            title: {
                display: true,
                text: isPct ? '累積漲跌幅 (%)' : `${data.stock1.symbol} 股價 ($)`
            },
            ticks: {
                callback: function (value) {
                    return isPct ? `${value}%` : `$${value}`;
                }
            }
        }
    };

    if (!isPct) {
        scalesConfig.y2 = {
            type: 'linear',
            display: true,
            position: 'right',
            title: {
                display: true,
                text: `${data.stock2.symbol} 股價 ($)`
            },
            grid: { drawOnChartArea: false },
            ticks: {
                callback: function (value) {
                    return `$${value}`;
                }
            }
        };
    }

    compareChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.dates,
            datasets: [dataset1, dataset2]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            const val = context.parsed.y;
                            const idx = context.dataIndex;
                            if (isPct) {
                                const rawPrice = context.datasetIndex === 0 ? data.prices1[idx] : data.prices2[idx];
                                return ` ${context.dataset.label}: ${val > 0 ? '+' : ''}${val}% (股價: $${rawPrice})`;
                            } else {
                                return ` ${context.dataset.label}: $${val}`;
                            }
                        }
                    }
                }
            },
            scales: scalesConfig
        }
    });
}