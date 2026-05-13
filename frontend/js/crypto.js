/**
 * Client-side HMAC helper — purely for passing server-generated signatures.
 * All cryptographic authority resides on the server.
 */
const CryptoHelper = (() => {
    function storeToken(token) {
        localStorage.setItem('vsm_token', token);
    }

    function getToken() {
        return localStorage.getItem('vsm_token');
    }

    function clearToken() {
        localStorage.removeItem('vsm_token');
    }

    function hasToken() {
        return !!localStorage.getItem('vsm_token');
    }

    function authHeaders() {
        const token = getToken();
        if (!token) return {};
        return { 'Authorization': `Bearer ${token}` };
    }

    async function apiCall(method, path, body = null) {
        const opts = {
            method,
            headers: {
                'Content-Type': 'application/json',
                ...authHeaders(),
            },
        };
        if (body) opts.body = JSON.stringify(body);

        const resp = await fetch(`/api${path}`, opts);
        const data = await resp.json();

        if (!resp.ok) {
            throw new Error(data.detail || 'Request failed');
        }
        return data;
    }

    return { storeToken, getToken, clearToken, hasToken, authHeaders, apiCall };
})();
