/**
 * UI state manager — handles DOM interactions, form bindings, and display updates.
 */
const UI = (() => {
    let currentSymbol = 'NOVA';
    let currentSide = 'buy';
    let prices = {};
    let taskData = null;
    let taskTimer = null;

    function init() {
        _bindAuthTabs();
        _bindTradeTabs();
        _bindTradeType();
        _bindZoomButtons();
        _bindFaucetButtons();
    }

    // ── Auth ──

    function _bindAuthTabs() {
        document.querySelectorAll('#auth-tabs .tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('#auth-tabs .tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                const target = tab.dataset.tab;
                document.getElementById('login-form').classList.toggle('hidden', target !== 'login');
                document.getElementById('register-form').classList.toggle('hidden', target !== 'register');
            });
        });
    }

    function showApp() {
        document.getElementById('auth-modal').classList.add('hidden');
        document.getElementById('app').classList.remove('hidden');
    }

    function showAuth() {
        document.getElementById('auth-modal').classList.remove('hidden');
        document.getElementById('app').classList.add('hidden');
    }

    function setUser(username, balance) {
        document.getElementById('user-name').textContent = username;
        updateBalance(balance);
    }

    function updateBalance(balance) {
        document.getElementById('user-balance').textContent = `¤${Number(balance).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
    }

    function showAuthError(formId, msg) {
        document.getElementById(formId).textContent = msg;
    }

    // ── Assets ──

    function renderAssets(assets) {
        const list = document.getElementById('asset-list');
        list.innerHTML = '';
        assets.forEach(asset => {
            const el = document.createElement('div');
            el.className = 'asset-item' + (asset.symbol === currentSymbol ? ' active' : '');
            el.innerHTML = `
                <span class="asset-symbol">${asset.symbol}</span>
                <span class="asset-price">$${(prices[asset.symbol] || asset.base_price).toFixed(2)}</span>
            `;
            el.addEventListener('click', () => selectAsset(asset.symbol));
            list.appendChild(el);
        });
    }

    function selectAsset(symbol) {
        currentSymbol = symbol;
        document.querySelectorAll('.asset-item').forEach(el => {
            el.classList.toggle('active', el.querySelector('.asset-symbol').textContent === symbol);
        });
        document.getElementById('chart-symbol').textContent = symbol;
        _updateTradeButton();
        if (typeof App !== 'undefined') App.onAssetSelected(symbol);
    }

    function getCurrentSymbol() { return currentSymbol; }

    // ── Prices ──

    function updatePrices(newPrices) {
        prices = { ...prices, ...newPrices };

        // Update asset list prices in the sidebar
        document.querySelectorAll('.asset-item').forEach(el => {
            const sym = el.querySelector('.asset-symbol').textContent;
            if (newPrices[sym]) {
                const priceEl = el.querySelector('.asset-price');
                const oldPrice = parseFloat(priceEl.textContent.replace('$', ''));
                const newPrice = newPrices[sym];
                
                priceEl.textContent = `$${newPrice.toFixed(2)}`;
                
                // Add a visual flash effect for price changes
                if (newPrice > oldPrice) {
                    priceEl.style.color = 'var(--accent-green)';
                } else if (newPrice < oldPrice) {
                    priceEl.style.color = 'var(--accent-red)';
                }
                
                setTimeout(() => {
                    priceEl.style.color = 'var(--text-primary)';
                }, 500);
            }
        });

        // Update chart header
        if (newPrices[currentSymbol]) {
            document.getElementById('chart-price').textContent = `$${newPrices[currentSymbol].toFixed(2)}`;
        }

        // Update ticker
        _updateTicker(newPrices);

        // Update trade estimate
        _updateTradeEstimate();
    }

    function _updateTicker(priceMap) {
        const ticker = document.getElementById('market-ticker');
        ticker.innerHTML = '';
        for (const [sym, price] of Object.entries(priceMap)) {
            const span = document.createElement('span');
            span.className = 'ticker-item';
            span.innerHTML = `<span class="ticker-symbol">${sym}</span><span class="ticker-price">$${price.toFixed(2)}</span>`;
            ticker.appendChild(span);
        }
    }

    // ── Trading ──

    function _bindTradeTabs() {
        document.querySelectorAll('.trade-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.trade-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                currentSide = tab.dataset.side;
                _updateTradeButton();
            });
        });
    }

    function _bindTradeType() {
        const sel = document.getElementById('trade-type');
        sel.addEventListener('change', () => {
            document.getElementById('limit-price-group').classList.toggle('hidden', sel.value !== 'limit');
            _updateTradeEstimate();
        });

        document.getElementById('trade-qty').addEventListener('input', _updateTradeEstimate);
        document.getElementById('trade-limit-price').addEventListener('input', _updateTradeEstimate);
    }

    function _updateTradeButton() {
        const btn = document.getElementById('trade-submit');
        const label = currentSide === 'buy' ? 'Buy' : 'Sell';
        btn.textContent = `${label} ${currentSymbol}`;
        btn.style.background = currentSide === 'buy' ? '#00e676' : '#ff1744';
        btn.style.borderColor = btn.style.background;
    }

    function _updateTradeEstimate() {
        const qty = parseInt(document.getElementById('trade-qty').value) || 0;
        const type = document.getElementById('trade-type').value;
        let price = prices[currentSymbol] || 0;
        if (type === 'limit') {
            price = parseFloat(document.getElementById('trade-limit-price').value) || price;
        }
        const total = qty * price;
        document.getElementById('trade-total').textContent = `¤${total.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
    }

    function getTradeParams() {
        return {
            symbol: currentSymbol,
            side: currentSide,
            order_type: document.getElementById('trade-type').value,
            quantity: parseInt(document.getElementById('trade-qty').value) || 0,
            limit_price: document.getElementById('trade-type').value === 'limit'
                ? parseFloat(document.getElementById('trade-limit-price').value) || null
                : null,
        };
    }

    function showTradeError(msg) {
        document.getElementById('trade-error').textContent = msg;
        document.getElementById('trade-success').textContent = '';
    }

    function showTradeSuccess(msg) {
        document.getElementById('trade-success').textContent = msg;
        document.getElementById('trade-error').textContent = '';
        setTimeout(() => { document.getElementById('trade-success').textContent = ''; }, 3000);
    }

    // ── Portfolio ──

    function renderPortfolio(items) {
        const list = document.getElementById('portfolio-list');
        if (!items.length) {
            list.innerHTML = '<div style="color:var(--text-muted);font-size:12px;">No holdings</div>';
            return;
        }
        list.innerHTML = items.map(item => `
            <div class="portfolio-item">
                <span>${item.symbol} x${item.quantity}</span>
                <span>$${item.current_price.toFixed(2)}</span>
                <span class="${item.pnl >= 0 ? 'pnl-pos' : 'pnl-neg'}">${item.pnl >= 0 ? '+' : ''}¤${item.pnl.toFixed(2)}</span>
            </div>
        `).join('');
    }

    // ── Zoom ──

    function _bindZoomButtons() {
        document.querySelectorAll('.zoom-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.zoom-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                ChartRenderer.setZoom(btn.dataset.zoom);
            });
        });
    }

    // ── Faucet ──

    function _bindFaucetButtons() {
        document.querySelectorAll('.btn-faucet').forEach(btn => {
            btn.addEventListener('click', () => {
                if (typeof App !== 'undefined') App.requestTask(parseInt(btn.dataset.tier));
            });
        });

        document.getElementById('task-submit').addEventListener('click', () => {
            if (typeof App !== 'undefined') App.submitTask();
        });
    }

    function showTask(data) {
        taskData = data;
        const el = document.getElementById('task-challenge');
        el.classList.remove('hidden');
        document.getElementById('task-question').textContent = data.question;
        document.getElementById('task-answer').value = '';
        document.getElementById('task-result').textContent = '';

        if (taskTimer) clearInterval(taskTimer);
        taskTimer = setInterval(() => {
            const remaining = Math.max(0, Math.floor(data.expires - Date.now() / 1000));
            document.getElementById('task-timer').textContent = `Time: ${remaining}s`;
            if (remaining <= 0) {
                clearInterval(taskTimer);
                document.getElementById('task-result').textContent = 'Expired!';
                document.getElementById('task-result').style.color = 'var(--accent-red)';
            }
        }, 1000);
    }

    function getTaskAnswer() {
        return parseFloat(document.getElementById('task-answer').value);
    }

    function getTaskData() { return taskData; }

    function showTaskResult(result) {
        const el = document.getElementById('task-result');
        if (result.success) {
            el.textContent = `+¤${result.reward}!`;
            el.style.color = 'var(--accent-green)';
            updateBalance(result.new_balance);
        } else {
            el.textContent = result.error || 'Failed';
            el.style.color = 'var(--accent-red)';
        }
    }

    // ── Economy ──

    function renderEconomy(stats) {
        const el = document.getElementById('economy-stats');
        el.innerHTML = `
            <div class="eco-row"><span class="eco-label">Supply</span><span class="eco-value">¤${stats.total_supply.toLocaleString()}</span></div>
            <div class="eco-row"><span class="eco-label">Faucets</span><span class="eco-value">¤${stats.total_faucet_output.toLocaleString()}</span></div>
            <div class="eco-row"><span class="eco-label">Sinks</span><span class="eco-value">¤${stats.total_sink_drainage.toLocaleString()}</span></div>
            <div class="eco-row"><span class="eco-label">SCR</span><span class="eco-value">${(stats.sink_coverage_ratio * 100).toFixed(1)}%</span></div>
            <div class="eco-row"><span class="eco-label">Players</span><span class="eco-value">${stats.active_players}</span></div>
        `;
    }

    // ── News ──

    function showNews(text) {
        document.getElementById('news-ticker').innerHTML = `<span>${text}</span>`;
    }

    return {
        init, showApp, showAuth, setUser, updateBalance, showAuthError,
        renderAssets, selectAsset, getCurrentSymbol, updatePrices,
        getTradeParams, showTradeError, showTradeSuccess,
        renderPortfolio, showTask, getTaskAnswer, getTaskData, showTaskResult,
        renderEconomy, showNews,
    };
})();
