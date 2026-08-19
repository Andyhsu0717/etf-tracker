const etfs = [
    { id: '00981A', name: '00981A 主動統一台股增長', file: '00981A_holdings.json' },
    { id: '00403A', name: '00403A 統一台股升級50', file: '00403A_holdings.json' },
    { id: '00400A', name: '00400A 國泰台股動能高息', file: '00400A_holdings.json' }
];

let etfData = {};

document.addEventListener('DOMContentLoaded', async () => {
    await loadData();
    renderHome();
    setupEvents();
});

async function loadData() {
    for (const etf of etfs) {
        try {
            // 在 GitHub Pages 環境下直接讀取同一目錄的 JSON
            const res = await fetch(etf.file);
            if (res.ok) {
                etfData[etf.id] = await res.json();
            } else {
                console.warn(`Failed to load ${etf.file}`);
            }
        } catch (err) {
            console.error(`Error loading ${etf.file}:`, err);
        }
    }
}

function renderHome() {
    const container = document.getElementById('etf-cards');
    container.innerHTML = '';

    etfs.forEach(etf => {
        const data = etfData[etf.id];
        if (!data) return; // 沒有資料就不顯示

        const nav = data.current_nav ? data.current_nav.toFixed(4) : '--';
        const navDiff = data.previous_nav && data.current_nav ? (data.current_nav - data.previous_nav) : 0;
        const navSign = navDiff > 0 ? '+' : '';
        const navColor = navDiff > 0 ? 'text-red' : (navDiff < 0 ? 'text-green' : ''); // 台灣習慣紅漲綠跌

        const holdingsCount = Object.keys(data.current || {}).length;

        const card = document.createElement('div');
        card.className = 'card';
        card.onclick = () => showDetail(etf.id);
        
        card.innerHTML = `
            <h2>${etf.name}</h2>
            <p>最後更新: ${data.date}</p>
            <div class="card-stats">
                <div>
                    <div class="text-secondary" style="font-size:0.8rem">最新淨值</div>
                    <div class="stat-value ${navColor}">${nav} ${navDiff !== 0 ? `<span style="font-size:0.9rem">(${navSign}${navDiff.toFixed(4)})</span>` : ''}</div>
                </div>
                <div>
                    <div class="text-secondary" style="font-size:0.8rem">成分股數量</div>
                    <div class="stat-value">${holdingsCount} 檔</div>
                </div>
            </div>
        `;
        container.appendChild(card);
    });
}

function showDetail(etfId) {
    const etf = etfs.find(e => e.id === etfId);
    const data = etfData[etfId];
    if (!data) return;

    // 切換 View
    document.getElementById('home-view').classList.remove('active');
    document.getElementById('detail-view').classList.add('active');
    
    // 設定 Header
    document.getElementById('detail-title').textContent = etf.name;
    document.getElementById('detail-date').textContent = data.date;
    document.getElementById('detail-nav').textContent = data.current_nav ? `淨值: ${data.current_nav.toFixed(4)}` : '';

    // 計算異動
    const changes = compareData(data.previous || {}, data.current || {});
    renderChanges(changes);
    renderHoldings(data.current || {});
}

function setupEvents() {
    document.getElementById('back-btn').addEventListener('click', () => {
        document.getElementById('detail-view').classList.remove('active');
        document.getElementById('home-view').classList.add('active');
    });

    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            // Tab active state
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            
            // Content pane active state
            document.querySelectorAll('.content-pane').forEach(p => p.classList.remove('active'));
            const targetId = e.target.getAttribute('data-target');
            document.getElementById(targetId).classList.add('active');
        });
    });
}

function compareData(prev, curr) {
    const changes = { added: [], removed: [], changed: [], totalBuy: 0, totalSell: 0 };
    
    const prevKeys = new Set(Object.keys(prev));
    const currKeys = new Set(Object.keys(curr));
    
    // Added
    for (const k of currKeys) {
        if (!prevKeys.has(k)) {
            changes.added.push({ code: k, ...curr[k] });
        }
    }
    
    // Removed
    for (const k of prevKeys) {
        if (!currKeys.has(k)) {
            changes.removed.push({ code: k, ...prev[k] });
        }
    }
    
    // Changed
    for (const k of currKeys) {
        if (prevKeys.has(k)) {
            const p = prev[k];
            const c = curr[k];
            const shareDiff = c.share - p.share;
            const weightDiff = c.weight - p.weight;
            
            if (shareDiff !== 0) {
                const price = c.price || 0;
                const tradeVal = shareDiff * price;
                if (tradeVal > 0) changes.totalBuy += tradeVal;
                else changes.totalSell += Math.abs(tradeVal);
                
                changes.changed.push({
                    code: k, name: c.name,
                    shareDiff, weightDiff,
                    prevWeight: p.weight, currWeight: c.weight,
                    price, tradeVal
                });
            }
        }
    }
    
    changes.changed.sort((a, b) => b.weightDiff - a.weightDiff);
    return changes;
}

function renderChanges(changes) {
    // Summary Cards
    const summaryContainer = document.getElementById('summary-cards');
    const netTrade = changes.totalBuy - changes.totalSell;
    
    summaryContainer.innerHTML = `
        <div class="summary-card">
            <span class="label">總買進金額 (估)</span>
            <span class="value text-red">${formatMoney(changes.totalBuy)}</span>
        </div>
        <div class="summary-card">
            <span class="label">總賣出金額 (估)</span>
            <span class="value text-green">${formatMoney(changes.totalSell)}</span>
        </div>
        <div class="summary-card" style="border-color: ${netTrade > 0 ? 'var(--red)' : (netTrade < 0 ? 'var(--green)' : 'var(--border)')}">
            <span class="label">淨買賣金額 (估)</span>
            <span class="value ${netTrade > 0 ? 'text-red' : (netTrade < 0 ? 'text-green' : '')}">${netTrade > 0 ? '+' : ''}${formatMoney(netTrade)}</span>
        </div>
    `;

    // Sections visibility
    const noChanges = changes.added.length === 0 && changes.removed.length === 0 && changes.changed.length === 0;
    document.getElementById('no-changes-msg').style.display = noChanges ? 'block' : 'none';
    
    document.getElementById('added-section').style.display = changes.added.length ? 'block' : 'none';
    document.getElementById('removed-section').style.display = changes.removed.length ? 'block' : 'none';
    document.getElementById('changed-section').style.display = changes.changed.length ? 'block' : 'none';

    // Added
    document.getElementById('added-list').innerHTML = changes.added.map(st => 
        `<li><strong>${st.name}</strong> <span>(權重: ${st.weight}%, ${formatNumber(st.share)} 股)</span></li>`
    ).join('');

    // Removed
    document.getElementById('removed-list').innerHTML = changes.removed.map(st => 
        `<li><strong>${st.name}</strong> <span>(原權重: ${st.weight}%, 原股數: ${formatNumber(st.share)} 股)</span></li>`
    ).join('');

    // Changed Table
    document.getElementById('changed-tbody').innerHTML = changes.changed.map(st => {
        const sign = st.shareDiff > 0 ? '+' : '';
        const colorClass = st.shareDiff > 0 ? 'bg-red-soft' : 'bg-green-soft'; // 紅漲綠跌概念
        const actionText = st.shareDiff > 0 ? '買進' : '賣出';
        
        return `
            <tr>
                <td><strong>${st.name}</strong></td>
                <td><span class="${colorClass}">${sign}${formatNumber(st.shareDiff)} 股</span></td>
                <td>${st.prevWeight.toFixed(2)}% ➔ ${st.currWeight.toFixed(2)}% <span class="text-secondary">(${st.weightDiff > 0 ? '+' : ''}${st.weightDiff.toFixed(2)}%)</span></td>
                <td>${st.price > 0 ? st.price.toFixed(2) : '-'}</td>
                <td>${actionText}約 ${formatMoney(Math.abs(st.tradeVal))}</td>
            </tr>
        `;
    }).join('');
}

function renderHoldings(current) {
    const arr = Object.values(current).sort((a, b) => b.weight - a.weight);
    document.getElementById('holdings-tbody').innerHTML = arr.map((st, i) => `
        <tr>
            <td class="text-secondary">#${i + 1}</td>
            <td><strong>${st.name}</strong></td>
            <td>${st.weight.toFixed(2)}%</td>
            <td>${formatNumber(st.share)}</td>
            <td>${st.price > 0 ? st.price.toFixed(2) : '-'}</td>
            <td>${st.amount > 0 ? formatMoney(st.amount) : '-'}</td>
        </tr>
    `).join('');
}

// Helpers
function formatNumber(num) {
    return Number(num).toLocaleString('en-US');
}

function formatMoney(num) {
    if (num === 0) return '0';
    if (Math.abs(num) >= 10000) {
        return `${formatNumber(Math.round(num / 10000))} 萬`;
    }
    return formatNumber(Math.round(num));
}
