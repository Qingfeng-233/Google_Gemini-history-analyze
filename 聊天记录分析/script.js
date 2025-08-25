class DataAnalyzer {
    constructor() {
        this.charts = {};
        this.init();
    }

    init() {
        this.bindEvents();
        this.performAnalysis(); // 初始加载一次默认数据
    }

    bindEvents() {
        document.getElementById('analyzeBtn').addEventListener('click', () => this.performAnalysis());
        document.getElementById('timeRange').addEventListener('change', () => this.performAnalysis());
        document.getElementById('analysisType').addEventListener('change', () => this.performAnalysis());
    }

    async performAnalysis() {
        this.showLoading(true);

        try {
            const analysisType = document.getElementById('analysisType').value;
            const timeRange = document.getElementById('timeRange').value;

            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ timeRange, analysisType }),
            });

            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

            const results = await response.json();

            // 更新所有UI组件
            this.updateOverviewStats(results.overviewStats);
            this.generateWordCloud(results.wordCloud);
            this.generateCharts(results.chartData);
            this.generateDetailedStats(results.detailedStats, results.wordCloud);

        } catch (error) {
            console.error('分析过程出错:', error);
            alert('分析请求失败，请确保后端服务正在运行并检查其输出。');
        } finally {
            this.showLoading(false);
        }
    }

    showLoading(show) {
        document.getElementById('loading').classList.toggle('show', show);
    }

    updateOverviewStats(stats) {
        document.getElementById('totalConversations').textContent = (stats.totalConversations || 0).toLocaleString();
        document.getElementById('avgLength').textContent = (stats.avgLength || 0) + ' 字';
        document.getElementById('topTag').textContent = stats.topTag || 'N/A';
        document.getElementById('timeSpan').textContent = stats.timeSpan || 'N/A';
    }

    generateWordCloud(wordList) {
        const container = document.getElementById('wordcloud');
        if (!wordList || wordList.length === 0) {
            container.innerHTML = '<p class="no-data">暂无数据</p>';
            return;
        }

        const maxFreq = wordList[0][1];
        const minFreq = wordList[wordList.length - 1][1];
        
        // 丰富的颜色数组
        const colors = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
            '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
            '#F8C471', '#82E0AA', '#F1948A', '#85C1E9', '#D7BDE2',
            '#AED6F1', '#A9DFBF', '#F9E79F', '#F5B7B1', '#D2B4DE'
        ];
        
        // 创建网格布局避免重叠
        const gridCols = 12;
        const gridRows = 8;
        const usedPositions = new Set();
        
        // 按频率排序，高频词优先选择位置
        const sortedWords = [...wordList].sort((a, b) => b[1] - a[1]);
        
        container.innerHTML = `
            <div style="
                position: relative;
                width: 100%;
                height: 500px;
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                border-radius: 10px;
                overflow: hidden;
                padding: 20px;
                box-sizing: border-box;
                display: grid;
                grid-template-columns: repeat(${gridCols}, 1fr);
                grid-template-rows: repeat(${gridRows}, 1fr);
                gap: 5px;
            ">
                ${sortedWords.slice(0, 60).map(([word, freq], index) => {
                    // 优化字体大小计算 - 高频词更大，低频词更小
                    const normalizedFreq = (freq - minFreq) / (maxFreq - minFreq);
                    
                    // 使用指数缩放，让高频词显著更大
                    const exponentialScale = Math.pow(normalizedFreq, 0.6); // 指数缩放
                    const size = Math.max(10, Math.min(50, 10 + exponentialScale * 40));
                    
                    // 为前10个高频词额外加大
                    const bonusSize = index < 10 ? size * 1.2 : size;
                    const finalSize = Math.min(50, bonusSize);
                    
                    // 网格位置分配
                    let gridCol, gridRow;
                    let attempts = 0;
                    do {
                        gridCol = Math.floor(Math.random() * gridCols) + 1;
                        gridRow = Math.floor(Math.random() * gridRows) + 1;
                        attempts++;
                    } while (usedPositions.has(`${gridCol}-${gridRow}`) && attempts < 50);
                    
                    usedPositions.add(`${gridCol}-${gridRow}`);
                    
                    // 旋转角度（减少旋转避免混乱）
                    const rotation = [0, 0, 0, 15, -15, 30, -30][Math.floor(Math.random() * 7)];
                    const color = colors[index % colors.length];
                    
                    // 高频词加粗
                    const fontWeight = freq > maxFreq * 0.7 ? 'bold' : 'normal';
                    
                    return `
                        <div style="
                            grid-column: ${gridCol};
                            grid-row: ${gridRow};
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            font-size: ${finalSize}px;
                            color: ${color};
                            font-weight: ${fontWeight};
                            font-family: 'Microsoft YaHei', 'SimHei', Arial, sans-serif;
                            transform: rotate(${rotation}deg);
                            cursor: pointer;
                            transition: all 0.3s ease;
                            text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
                            user-select: none;
                            white-space: nowrap;
                            overflow: hidden;
                        " 
                        class="wordcloud-word-enhanced"
                        data-freq="${freq}"
                        title="${word}: ${freq}次"
                        onmouseover="this.style.transform='rotate(${rotation}deg) scale(1.15)'; this.style.zIndex='1000';"
                        onmouseout="this.style.transform='rotate(${rotation}deg) scale(1)'; this.style.zIndex='auto';"
                        >${word}</div>
                    `;
                }).join('')}
            </div>
        `;
        
        // 添加词云统计信息
        const statsDiv = document.createElement('div');
        statsDiv.style.cssText = `
            margin-top: 10px;
            text-align: center;
            color: #666;
            font-size: 14px;
        `;
        statsDiv.innerHTML = `
            显示前60个高质量词汇 (共${wordList.length}个) | 
            最高频词: "${wordList[0][0]}" (${wordList[0][1]}次) | 
            词频范围: ${minFreq}-${maxFreq}次
        `;
        container.appendChild(statsDiv);
    }

    generateCharts(chartData) {
        this.generateInterestChart(chartData.interestChart);
        this.generateTimeChart(chartData.timeChart);
        this.generateLengthChart(chartData.lengthChart);
    }

    createOrUpdateChart(chartId, type, data, options) {
        const ctx = document.getElementById(chartId).getContext('2d');
        if (this.charts[chartId]) {
            this.charts[chartId].destroy();
        }
        this.charts[chartId] = new Chart(ctx, { type, data, options });
    }

    generateInterestChart(interestData) {
        this.createOrUpdateChart('interestChart', 'doughnut', {
            labels: interestData.map(item => item[0]),
            datasets: [{
                data: interestData.map(item => item[1]),
                backgroundColor: ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe', '#00f2fe', '#43e97b', '#38f9d7', '#ffecd2', '#fcb69f']
            }]
        }, { responsive: true, plugins: { legend: { position: 'bottom' } } });
    }

    generateTimeChart(timeData) {
        this.createOrUpdateChart('timeChart', 'line', {
            labels: timeData.map(item => item[0]),
            datasets: [{
                label: '对话数量',
                data: timeData.map(item => item[1]),
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                fill: true,
                tension: 0.4
            }]
        }, { responsive: true, scales: { y: { beginAtZero: true } } });
    }

    generateLengthChart(lengthData) {
        this.createOrUpdateChart('lengthChart', 'bar', {
            labels: lengthData.labels,
            datasets: [{
                label: '数量',
                data: lengthData.data,
                backgroundColor: 'rgba(102, 126, 234, 0.8)',
                borderColor: '#667eea',
                borderWidth: 1
            }]
        }, { responsive: true, scales: { y: { beginAtZero: true } } });
    }

    generateDetailedStats(detailedStats, wordCloud) {
        this.generateTopWords(wordCloud);
        this.generateTagStats(detailedStats.tagStats);
        this.generateSentimentStats(detailedStats.sentimentStats);
    }

    generateTopWords(wordCloud) {
        const container = document.getElementById('topWords');
        container.innerHTML = wordCloud.slice(0, 20).map(([word, count]) => `
            <div class="word-item">
                <span>${word}</span>
                <span class="word-count">${count}</span>
            </div>
        `).join('');
    }

    generateTagStats(tagStats) {
        const container = document.getElementById('tagStats');
        container.innerHTML = tagStats.map(([tag, count]) => `
            <div class="tag-item">
                <span>${tag}</span>
                <span class="tag-count">${count}</span>
            </div>
        `).join('');
    }

    generateSentimentStats(sentimentStats) {
        const container = document.getElementById('sentimentStats');
        const { positive, neutral, negative } = sentimentStats;
        container.innerHTML = `
            <div class="sentiment-item">
                <span>积极 (${positive.percent}%)</span>
                <div class="sentiment-bar">
                    <div class="sentiment-fill positive" style="width: ${positive.percent}%"></div>
                </div>
                <span>${positive.count}</span>
            </div>
            <div class="sentiment-item">
                <span>中性 (${neutral.percent}%)</span>
                <div class="sentiment-bar">
                    <div class="sentiment-fill neutral" style="width: ${neutral.percent}%"></div>
                </div>
                <span>${neutral.count}</span>
            </div>
            <div class="sentiment-item">
                <span>消极 (${negative.percent}%)</span>
                <div class="sentiment-bar">
                    <div class="sentiment-fill negative" style="width: ${negative.percent}%"></div>
                </div>
                <span>${negative.count}</span>
            </div>
        `;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new DataAnalyzer();
});