'use strict';

function _formatRemaining(diffSec) {
    if (diffSec < 3600) {
        const m = Math.ceil(diffSec / 60);
        return m + ' min.';
    }
    if (diffSec < 86400) {
        const h = Math.floor(diffSec / 3600);
        return h + ' h.';
    }
    const d = Math.floor(diffSec / 86400);
    return d + ' d.';
}

function drawDeadlineGraph(canvas) {
    const points = JSON.parse(canvas.dataset.points);
    const nowTs = parseFloat(canvas.dataset.now);
    const totalScore = parseInt(canvas.dataset.score) || 0;
    const isExpired = canvas.dataset.expired === 'true';

    if (!points || points.length < 2) return;

    const dpr = window.devicePixelRatio || 1;
    const cssWidth = canvas.getBoundingClientRect().width || canvas.parentElement.clientWidth || 300;
    const cssHeight = 130;

    canvas.style.height = cssHeight + 'px';
    canvas.width = Math.round(cssWidth * dpr);
    canvas.height = Math.round(cssHeight * dpr);

    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);

    const isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark'
                || window.matchMedia('(prefers-color-scheme: dark)').matches;

    const textColor = isDark ? '#adb5bd' : '#555';
    const axisColor = isDark ? 'rgba(255,255,255,0.18)' : 'rgba(0,0,0,0.18)';
    const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)';
    const lineColor = isExpired ? '#9e9e9e'
                    : (isDark   ? '#66cda3' : '#2e7d32');
    const fillColor = isExpired ? 'rgba(158,158,158,0.12)'
                    : (isDark   ? 'rgba(102,205,163,0.15)' : 'rgba(46,125,50,0.12)');
    const nowColor  = '#ef6c00';
    const dotColor  = isExpired ? '#9e9e9e' : (isDark ? '#66cda3' : '#388e3c');

    const mL = 46, mR = 8, mT = 10, mB = 34;
    const pW = cssWidth - mL - mR;
    const pH = cssHeight - mT - mB;

    const minTs   = points[0].ts;
    const maxTs   = points[points.length - 1].ts;
    const tsRange = maxTs - minTs || 1;

    function xOf(ts)  { return mL + (ts - minTs) / tsRange * pW; }
    function yOf(pct) { return mT + (1 - pct) * pH; }

    ctx.clearRect(0, 0, cssWidth, cssHeight);

    // Horizontal grid lines at 0%, 50%, 100%
    ctx.strokeStyle = gridColor;
    ctx.lineWidth = 1;
    [0, 0.5, 1.0].forEach(function (p) {
        const y = yOf(p);
        ctx.beginPath();
        ctx.moveTo(mL, y);
        ctx.lineTo(mL + pW, y);
        ctx.stroke();
    });

    // Filled area under the piecewise line
    ctx.beginPath();
    ctx.moveTo(xOf(points[0].ts), yOf(points[0].pct));
    for (let i = 1; i < points.length; i++) {
        ctx.lineTo(xOf(points[i].ts), yOf(points[i].pct));
    }
    ctx.lineTo(xOf(points[points.length - 1].ts), yOf(0));
    ctx.lineTo(xOf(points[0].ts), yOf(0));
    ctx.closePath();
    ctx.fillStyle = fillColor;
    ctx.fill();

    // Piecewise line
    ctx.beginPath();
    ctx.moveTo(xOf(points[0].ts), yOf(points[0].pct));
    for (let i = 1; i < points.length; i++) {
        ctx.lineTo(xOf(points[i].ts), yOf(points[i].pct));
    }
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    ctx.stroke();

    // Axes
    ctx.strokeStyle = axisColor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(mL, mT);
    ctx.lineTo(mL, mT + pH);
    ctx.lineTo(mL + pW, mT + pH);
    ctx.stroke();

    // Y-axis labels at each unique percentage breakpoint
    ctx.font = '10px system-ui, -apple-system, sans-serif';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    const allPcts    = [1.0, ...points.slice(1, -1).map(function (p) { return p.pct; }), 0.0];
    const uniquePcts = [...new Set(allPcts)].sort(function (a, b) { return b - a; });
    let lastLabelY   = -Infinity;
    uniquePcts.forEach(function (pct) {
        const y = yOf(pct);
        // Always draw endpoints; skip middle ones if too close
        if (pct !== 1.0 && pct !== 0.0 && y - lastLabelY < 14) return;
        lastLabelY = y;
        ctx.fillStyle = textColor;
        const label = totalScore > 0
            ? (Math.round(pct * totalScore) + 'pt')
            : (Math.round(pct * 100) + '%');
        ctx.fillText(label, mL - 4, y);
    });

    // X-axis date labels at each critical point
    ctx.textBaseline = 'top';
    let lastLabelX = -Infinity;
    const minGap   = 52;
    points.forEach(function (pt, i) {
        const x       = xOf(pt.ts);
        const isFirst = (i === 0);
        const isLast  = (i === points.length - 1);

        // Enforce spacing; always show first and last
        if (!isFirst && !isLast && x - lastLabelX < minGap) return;
        // Skip intermediate labels that would crowd the final label
        if (!isLast && (xOf(points[points.length - 1].ts) - x) < minGap && !isFirst) return;

        ctx.textAlign = isFirst ? 'left' : (isLast ? 'right' : 'center');
        const labelX  = isFirst ? mL : (isLast ? mL + pW : x);
        ctx.fillStyle = textColor;
        ctx.fillText(pt.label, labelX, mT + pH + 5);

        // Tick mark
        ctx.strokeStyle = axisColor;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, mT + pH);
        ctx.lineTo(x, mT + pH + 3);
        ctx.stroke();

        lastLabelX = x;
    });

    // "Now" dashed marker — only shown while the deadline window is open
    if (nowTs > minTs && nowTs < maxTs) {
        const nx = xOf(nowTs);

        // Interpolate the currently achievable percentage
        let curPct = 0;
        for (let i = 0; i < points.length - 1; i++) {
            if (nowTs >= points[i].ts && nowTs <= points[i + 1].ts) {
                const t = (nowTs - points[i].ts) / (points[i + 1].ts - points[i].ts);
                curPct = points[i].pct + t * (points[i + 1].pct - points[i].pct);
                break;
            }
        }

        ctx.strokeStyle = nowColor;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 3]);
        ctx.beginPath();
        ctx.moveTo(nx, mT);
        ctx.lineTo(nx, mT + pH);
        ctx.stroke();
        ctx.setLineDash([]);

        // Dot at current achievable score on the curve
        ctx.fillStyle = nowColor;
        ctx.beginPath();
        ctx.arc(nx, yOf(curPct), 4, 0, Math.PI * 2);
        ctx.fill();
    }

    // Dots at key breakpoints
    ctx.fillStyle = dotColor;
    points.forEach(function (pt) {
        ctx.beginPath();
        ctx.arc(xOf(pt.ts), yOf(pt.pct), 3, 0, Math.PI * 2);
        ctx.fill();
    });

    // "Next deadline in" hint — drawn inside the bottom-right of the plot area
    const next = points.find(function (pt) { return pt.ts > nowTs; });
    if (next) {
        const diffSec = next.ts - nowTs;
        const isUrgent = diffSec < 86400;
        const hintText = 'Next deadline in: ' + _formatRemaining(diffSec);
        ctx.font = 'italic 10px system-ui, -apple-system, sans-serif';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'top';
        ctx.fillStyle = isUrgent ? nowColor : textColor;
        ctx.fillText(hintText, mL + pW, mT + 4);
    }
}

function initDeadlineGraphs() {
    document.querySelectorAll('.deadline-graph-canvas').forEach(drawDeadlineGraph);
}

initDeadlineGraphs();

// Redraw on resize so the canvas stays sharp and correctly sized
let _deadlineGraphResizeTimer;
window.addEventListener('resize', function () {
    clearTimeout(_deadlineGraphResizeTimer);
    _deadlineGraphResizeTimer = setTimeout(initDeadlineGraphs, 120);
});
