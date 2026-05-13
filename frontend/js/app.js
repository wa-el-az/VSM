/**
 * Main application — orchestrates auth, WebSocket, trading, and data flow.
 */
const App = (() => {
    const API = CryptoHelper.apiCall;
    let ws = null;
    let reconnectDelay = 1000;
    let assets = [];
    let heartbeatInterval = null;

    async function boot() {
        UI.init();
        _bindForms();

        if (CryptoHelper.hasToken()) {
            try {
                const user = await API('GET', '/auth/me');
                _enterApp(user);
            } catch {
                CryptoHelper.clearToken();
                UI.showAuth();
            }
        } else {
            UI.showAuth();
        }
    }

    function _bindForms() {
        document.getElementById('login-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            try {
                const data = await API('POST', '/auth/login', {
                    username: document.getElementById('login-username').value,
                    password: document.getElementById('login-password').value,
                });
                CryptoHelper.storeToken(data.access_token);
                const user = await API('GET', '/auth/me');
                _enterApp(user);
            } catch (err) {
                UI.showAuthError('login-error', err.message);
            }
        });

        document.getElementById('register-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            try {
                const data = await API('POST', '/auth/register', {
                    username: document.getElementById('reg-username').value,
                    password: document.getElementById('reg-password').value,
                });
                CryptoHelper.storeToken(data.access_token);
                const user = await API('GET', '/auth/me');
                _enterApp(user);
            } catch (err) {
                UI.showAuthError('reg-error', err.message);
            }
        });

        document.getElementById('trade-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            await _placeTrade();
        });

        document.getElementById('btn-logout').addEventListener('click', () => {
            CryptoHelper.clearToken();
            if (ws) ws.close();
            UI.showAuth();
        });
    }

    async function _enterApp(user) {
        UI.showApp();
        UI.setUser(user.username, user.balance);

        assets = await API('GET', '/market/assets');
        UI.renderAssets(assets);

        const prices = await API('GET', '/market/prices');
        UI.updatePrices(prices);

        ChartRenderer.init(document.getElementById('price-chart'));

        await _loadHistory(UI.getCurrentSymbol());
        await _loadPortfolio();
        await _loadEconomy();

        _connectWebSocket();

        setInterval(_loadPortfolio, 10000);
        setInterval(_loadEconomy, 30000);
    }

    async function _loadHistory(symbol) {
        try {
            const history = await API('GET', `/market/prices/${symbol}/history?limit=1000`);
            ChartRenderer.setData(history);
        } catch {
            ChartRenderer.setData([]);
        }
    }

    async function _loadPortfolio() {
        try {
            const items = await API('GET', '/market/portfolio');
            UI.renderPortfolio(items);
        } catch { /* silent */ }
    }

    async function _loadEconomy() {
        try {
            const stats = await API('GET', '/market/economy');
            UI.renderEconomy(stats);
        } catch { /* silent */ }
    }

    function _connectWebSocket() {
        const token = CryptoHelper.getToken();
        if (!token) return;

        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(`${proto}//${location.host}/api/market/ws/${token}`);

        ws.onopen = () => {
            reconnectDelay = 1000;
            ws.send(JSON.stringify({ type: 'subscribe', symbol: UI.getCurrentSymbol() }));

            heartbeatInterval = setInterval(() => {
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: 'pong' }));
                }
            }, 30000);
        };

        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            _handleMessage(msg);
        };

        ws.onclose = () => {
            if (heartbeatInterval) clearInterval(heartbeatInterval);
            setTimeout(_connectWebSocket, reconnectDelay);
            reconnectDelay = Math.min(reconnectDelay * 2, 30000);
        };

        ws.onerror = () => { ws.close(); };
    }

    function _handleMessage(msg) {
        switch (msg.type) {
            case 'price_update': {
                const p = msg.payload;
                UI.updatePrices({ [p.symbol]: p.price });
                if (p.symbol === UI.getCurrentSymbol()) {
                    ChartRenderer.addTick({
                        timestamp: p.timestamp,
                        price: p.price,
                        close: p.price,
                        open: p.price,
                        high: p.price,
                        low: p.price,
                        volume: p.volume || 0,
                    });
                }
                break;
            }
            case 'terminal': {
                UI.updateTerminal(msg.payload);
                break;
            }
            case 'order_fill': {
                _loadPortfolio();
                const user = msg.payload;
                if (user.new_balance !== undefined) UI.updateBalance(user.new_balance);
                break;
            }
            case 'balance_change': {
                UI.updateBalance(msg.payload.balance);
                break;
            }
            case 'news_event': {
                UI.showNews(msg.payload.name || msg.payload.description || 'Breaking news!');
                break;
            }
            case 'ping': {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: 'pong' }));
                }
                break;
            }
        }
    }

    async function onAssetSelected(symbol) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'subscribe', symbol }));
        }
        await _loadHistory(symbol);
    }

    function sendTerminalCommand(command) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'command', payload: { command } }));
        } else {
            UI.updateTerminal('Terminal offline. Reconnecting...');
        }
    }

    async function _placeTrade() {
        UI.showTradeError('');
        const params = UI.getTradeParams();

        if (!params.quantity || params.quantity < 1) {
            UI.showTradeError('Quantity must be at least 1');
            return;
        }

        try {
            const result = await API('POST', '/market/orders', params);
            UI.showTradeSuccess(`${params.side.toUpperCase()} ${params.quantity} ${params.symbol} — filled!`);

            const user = await API('GET', '/auth/me');
            UI.updateBalance(user.balance);
            await _loadPortfolio();
        } catch (err) {
            UI.showTradeError(err.message);
        }
    }

    async function requestTask(tier) {
        try {
            const data = await API('POST', '/tasks/request', { tier });
            UI.showTask(data);
        } catch (err) {
            UI.showTradeError(err.message);
        }
    }

    async function submitTask() {
        const taskData = UI.getTaskData();
        if (!taskData) return;

        const answer = UI.getTaskAnswer();
        if (isNaN(answer)) return;

        try {
            const result = await API('POST', '/tasks/submit', {
                task_id: taskData.task_id,
                nonce: taskData.nonce,
                answer: answer,
                signature: taskData.signature,
            });
            UI.showTaskResult(result);
        } catch (err) {
            UI.showTaskResult({ success: false, error: err.message });
        }
    }

    document.addEventListener('DOMContentLoaded', boot);

    return { onAssetSelected, requestTask, submitTask, sendTerminalCommand };
})();
