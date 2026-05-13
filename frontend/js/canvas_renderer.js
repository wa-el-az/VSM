/**
 * Canvas-based financial chart renderer with OHLC conflation.
 * Eliminates DOM explosion — all geometry drawn imperatively per frame.
 */
const ChartRenderer = (() => {
    let canvas, ctx;
    let data = [];
    let zoomLevel = '1D';
    let animFrameId = null;

    const COLORS = {
        bg: '#0f0f2a',
        grid: 'rgba(255,255,255,0.04)',
        gridText: 'rgba(255,255,255,0.25)',
        up: '#00e676',
        down: '#ff1744',
        line: '#448aff',
        crosshair: 'rgba(255,255,255,0.15)',
        volume: 'rgba(68,138,255,0.15)',
    };

    const BUCKET_SIZES = {
        '1D': 1,
        '1W': 300,
        '1M': 3600,
        '1Y': 86400,
    };

    let mouseX = -1, mouseY = -1;
    let viewOffset = 0;
    let isDragging = false;
    let dragStartX = 0;
    let dragStartOffset = 0;

    function init(canvasElement) {
        canvas = canvasElement;
        ctx = canvas.getContext('2d');
        _resize();
        window.addEventListener('resize', _resize);
        canvas.addEventListener('mousemove', _onMouseMove);
        canvas.addEventListener('mouseleave', _onMouseLeave);
        canvas.addEventListener('wheel', _onWheel, { passive: false });
        canvas.addEventListener('mousedown', _onMouseDown);
        window.addEventListener('mouseup', _onMouseUp);
        window.addEventListener('mousemove', _onDragMove);
        _startRenderLoop();
    }

    function _resize() {
        const rect = canvas.parentElement.getBoundingClientRect();
        canvas.width = rect.width * devicePixelRatio;
        canvas.height = rect.height * devicePixelRatio;
        canvas.style.width = rect.width + 'px';
        canvas.style.height = rect.height + 'px';
        ctx.scale(devicePixelRatio, devicePixelRatio);
    }

    function _onMouseMove(e) {
        const rect = canvas.getBoundingClientRect();
        mouseX = e.clientX - rect.left;
        mouseY = e.clientY - rect.top;
    }

    function _onMouseLeave() { mouseX = -1; mouseY = -1; }

    function _onWheel(e) {
        e.preventDefault();
        viewOffset = Math.max(0, viewOffset + Math.sign(e.deltaY) * 5);
    }

    function _onMouseDown(e) {
        isDragging = true;
        dragStartX = e.clientX;
        dragStartOffset = viewOffset;
    }

    function _onMouseUp() { isDragging = false; }

    function _onDragMove(e) {
        if (!isDragging) return;
        const dx = dragStartX - e.clientX;
        viewOffset = Math.max(0, dragStartOffset + Math.round(dx / 4));
    }

    function setData(newData) {
        data = newData;
        viewOffset = 0;
    }

    function addTick(tick) {
        data.push(tick);
        if (data.length > 50000) data = data.slice(-50000);
    }

    function setZoom(level) {
        zoomLevel = level;
        viewOffset = 0;
    }

    function _conflate(rawData) {
        const bucketSize = BUCKET_SIZES[zoomLevel] || 1;
        if (bucketSize <= 1) return rawData;

        const buckets = [];
        let current = null;

        for (const tick of rawData) {
            const key = Math.floor(tick.timestamp / bucketSize);
            if (!current || current._key !== key) {
                if (current) buckets.push(current);
                current = {
                    _key: key,
                    timestamp: tick.timestamp,
                    open: tick.close || tick.price,
                    high: tick.close || tick.price,
                    low: tick.close || tick.price,
                    close: tick.close || tick.price,
                    volume: tick.volume || 0,
                };
            } else {
                const p = tick.close || tick.price;
                current.high = Math.max(current.high, p);
                current.low = Math.min(current.low, p);
                current.close = p;
                current.volume += tick.volume || 0;
            }
        }
        if (current) buckets.push(current);
        return buckets;
    }

    function _startRenderLoop() {
        function frame() {
            _render();
            animFrameId = requestAnimationFrame(frame);
        }
        animFrameId = requestAnimationFrame(frame);
    }

    function _render() {
        const w = canvas.width / devicePixelRatio;
        const h = canvas.height / devicePixelRatio;
        ctx.clearRect(0, 0, w, h);

        const conflated = _conflate(data);
        if (conflated.length < 2) {
            ctx.fillStyle = COLORS.gridText;
            ctx.font = '14px -apple-system, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('Waiting for market data...', w / 2, h / 2);
            return;
        }

        const margin = { top: 20, right: 60, bottom: 30, left: 10 };
        const chartW = w - margin.left - margin.right;
        const chartH = h - margin.top - margin.bottom;

        const visibleCount = Math.min(conflated.length, Math.floor(chartW / 6));
        const startIdx = Math.max(0, conflated.length - visibleCount - viewOffset);
        const endIdx = Math.min(conflated.length, startIdx + visibleCount);
        const visible = conflated.slice(startIdx, endIdx);

        if (visible.length < 2) return;

        let minP = Infinity, maxP = -Infinity, maxV = 0;
        for (const bar of visible) {
            const hi = bar.high || bar.close || bar.price;
            const lo = bar.low || bar.close || bar.price;
            if (hi > maxP) maxP = hi;
            if (lo < minP) minP = lo;
            if ((bar.volume || 0) > maxV) maxV = bar.volume;
        }

        const pRange = maxP - minP || 1;
        const padding = pRange * 0.05;
        minP -= padding;
        maxP += padding;
        const finalRange = maxP - minP;

        const scaleX = (i) => margin.left + (i / (visible.length - 1)) * chartW;
        const scaleY = (p) => margin.top + (1 - (p - minP) / finalRange) * chartH;

        // Grid
        ctx.strokeStyle = COLORS.grid;
        ctx.lineWidth = 0.5;
        const gridLines = 6;
        for (let i = 0; i <= gridLines; i++) {
            const y = margin.top + (i / gridLines) * chartH;
            ctx.beginPath();
            ctx.moveTo(margin.left, y);
            ctx.lineTo(w - margin.right, y);
            ctx.stroke();

            const price = maxP - (i / gridLines) * finalRange;
            ctx.fillStyle = COLORS.gridText;
            ctx.font = '10px Courier New';
            ctx.textAlign = 'left';
            ctx.fillText(price.toFixed(2), w - margin.right + 6, y + 3);
        }

        // Volume bars
        if (maxV > 0) {
            const volH = chartH * 0.15;
            ctx.fillStyle = COLORS.volume;
            for (let i = 0; i < visible.length; i++) {
                const bar = visible[i];
                const v = (bar.volume || 0) / maxV;
                const x = scaleX(i);
                const barW = Math.max(1, chartW / visible.length * 0.6);
                ctx.fillRect(x - barW / 2, margin.top + chartH - v * volH, barW, v * volH);
            }
        }

        // Candlestick or line
        const barWidth = Math.max(1, Math.min(8, chartW / visible.length * 0.6));

        if (zoomLevel === '1D' && barWidth < 3) {
            // Line chart for dense data
            ctx.beginPath();
            ctx.strokeStyle = COLORS.line;
            ctx.lineWidth = 1.5;
            for (let i = 0; i < visible.length; i++) {
                const p = visible[i].close || visible[i].price;
                const x = scaleX(i);
                const y = scaleY(p);
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.stroke();

            // Gradient fill
            const gradient = ctx.createLinearGradient(0, margin.top, 0, margin.top + chartH);
            gradient.addColorStop(0, 'rgba(68,138,255,0.12)');
            gradient.addColorStop(1, 'rgba(68,138,255,0.0)');
            ctx.lineTo(scaleX(visible.length - 1), margin.top + chartH);
            ctx.lineTo(scaleX(0), margin.top + chartH);
            ctx.closePath();
            ctx.fillStyle = gradient;
            ctx.fill();
        } else {
            // Candlestick
            for (let i = 0; i < visible.length; i++) {
                const bar = visible[i];
                const o = bar.open || bar.close;
                const c = bar.close;
                const hi = bar.high || Math.max(o, c);
                const lo = bar.low || Math.min(o, c);
                const x = scaleX(i);
                const isUp = c >= o;
                const color = isUp ? COLORS.up : COLORS.down;

                // Wick
                ctx.strokeStyle = color;
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(x, scaleY(hi));
                ctx.lineTo(x, scaleY(lo));
                ctx.stroke();

                // Body
                const yTop = scaleY(Math.max(o, c));
                const yBot = scaleY(Math.min(o, c));
                const bodyH = Math.max(1, yBot - yTop);
                ctx.fillStyle = color;
                ctx.fillRect(x - barWidth / 2, yTop, barWidth, bodyH);
            }
        }

        // Crosshair
        if (mouseX > margin.left && mouseX < w - margin.right &&
            mouseY > margin.top && mouseY < margin.top + chartH) {
            ctx.strokeStyle = COLORS.crosshair;
            ctx.lineWidth = 0.5;
            ctx.setLineDash([4, 4]);

            ctx.beginPath();
            ctx.moveTo(mouseX, margin.top);
            ctx.lineTo(mouseX, margin.top + chartH);
            ctx.stroke();

            ctx.beginPath();
            ctx.moveTo(margin.left, mouseY);
            ctx.lineTo(w - margin.right, mouseY);
            ctx.stroke();

            ctx.setLineDash([]);

            const hoverPrice = maxP - ((mouseY - margin.top) / chartH) * finalRange;
            ctx.fillStyle = 'rgba(30,30,60,0.85)';
            ctx.fillRect(w - margin.right, mouseY - 10, margin.right, 20);
            ctx.fillStyle = '#fff';
            ctx.font = '10px Courier New';
            ctx.textAlign = 'left';
            ctx.fillText(hoverPrice.toFixed(2), w - margin.right + 4, mouseY + 4);

            const barIdx = Math.round((mouseX - margin.left) / chartW * (visible.length - 1));
            if (barIdx >= 0 && barIdx < visible.length) {
                const bar = visible[barIdx];
                const info = `O:${(bar.open||bar.close).toFixed(2)} H:${(bar.high||bar.close).toFixed(2)} L:${(bar.low||bar.close).toFixed(2)} C:${bar.close.toFixed(2)}`;
                ctx.fillStyle = 'rgba(30,30,60,0.85)';
                ctx.fillRect(margin.left, margin.top - 18, ctx.measureText(info).width + 12, 18);
                ctx.fillStyle = '#fff';
                ctx.font = '10px Courier New';
                ctx.textAlign = 'left';
                ctx.fillText(info, margin.left + 6, margin.top - 5);
            }
        }
    }

    function destroy() {
        if (animFrameId) cancelAnimationFrame(animFrameId);
        window.removeEventListener('resize', _resize);
    }

    return { init, setData, addTick, setZoom, destroy };
})();
