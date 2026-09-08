'use strict';

/**
 * Renders the interpolated-deadline score curve onto a <canvas>.
 *
 * All colours come from CSS custom properties declared on the canvas element
 * (see .deadline-graph-canvas in tasks.css), so the graph automatically follows
 * the light/dark theme and any restyling of the deadline planks. Nothing about
 * the palette is hard-coded here.
 */

// CSS custom property -> internal name. Values are resolved per canvas so that
// the `.expired` / `.urgent` / `.active` modifier on the parent plank can change
// them via normal CSS cascade.
const GRAPH_COLOR_VARS = {
    text: '--graph-text',
    axis: '--graph-axis',
    grid: '--graph-grid',
    line: '--graph-line',
    fill: '--graph-fill',
    dot:  '--graph-dot',
    now:  '--graph-now'
};

function _readGraphColors(canvas) {
    const cs = getComputedStyle(canvas);
    const colors = {};
    Object.keys(GRAPH_COLOR_VARS).forEach(function (key) {
        colors[key] = cs.getPropertyValue(GRAPH_COLOR_VARS[key]).trim();
    });
    return colors;
}

function _readGraphMetrics(canvas) {
    const cs = getComputedStyle(canvas);
    const num = function (prop, fallback) {
        const v = parseFloat(cs.getPropertyValue(prop));
        return isNaN(v) ? fallback : v;
    };
    return {
        height:   num('--graph-height', 110),
        marginL:  num('--graph-margin-left', 46),
        marginR:  num('--graph-margin-right', 8),
        marginT:  num('--graph-margin-top', 6),
        marginB:  num('--graph-margin-bottom', 30),
        fontSize: num('--graph-font-size', 10),
        fontFamily: cs.fontFamily || 'system-ui, sans-serif'
    };
}

function drawDeadlineGraph(canvas) {
    const points = JSON.parse(canvas.dataset.points);
    const nowTs = parseFloat(canvas.dataset.now);
    const totalScore = parseInt(canvas.dataset.score) || 0;

    if (!points || points.length < 2) return;

    const color = _readGraphColors(canvas);
    const m = _readGraphMetrics(canvas);

    const dpr = window.devicePixelRatio || 1;
    const cssWidth = canvas.getBoundingClientRect().width || canvas.parentElement.clientWidth || 300;
    const cssHeight = m.height;

    canvas.style.height = cssHeight + 'px';
    canvas.width = Math.round(cssWidth * dpr);
    canvas.height = Math.round(cssHeight * dpr);

    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);

    const mL = m.marginL, mR = m.marginR, mT = m.marginT, mB = m.marginB;
    const pW = cssWidth - mL - mR;
    const pH = cssHeight - mT - mB;
    const labelFont = m.fontSize + 'px ' + m.fontFamily;

    const minTs   = points[0].ts;
    const maxTs   = points[points.length - 1].ts;
    const tsRange = maxTs - minTs || 1;

    function xOf(ts)  { return mL + (ts - minTs) / tsRange * pW; }
    function yOf(pct) { return mT + (1 - pct) * pH; }

    ctx.clearRect(0, 0, cssWidth, cssHeight);

    // Horizontal grid lines at 0 %, 50 %, 100 %
    ctx.strokeStyle = color.grid;
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
    ctx.fillStyle = color.fill;
    ctx.fill();

    // Piecewise line
    ctx.beginPath();
    ctx.moveTo(xOf(points[0].ts), yOf(points[0].pct));
    for (let i = 1; i < points.length; i++) {
        ctx.lineTo(xOf(points[i].ts), yOf(points[i].pct));
    }
    ctx.strokeStyle = color.line;
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    ctx.stroke();

    // Axes
    ctx.strokeStyle = color.axis;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(mL, mT);
    ctx.lineTo(mL, mT + pH);
    ctx.lineTo(mL + pW, mT + pH);
    ctx.stroke();

    // Y-axis labels at each unique percentage breakpoint
    ctx.font = labelFont;
    ctx.fillStyle = color.text;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    const allPcts    = [1.0, ...points.slice(1, -1).map(function (p) { return p.pct; }), 0.0];
    const uniquePcts = [...new Set(allPcts)].sort(function (a, b) { return b - a; });
    let lastLabelY   = -Infinity;
    uniquePcts.forEach(function (pct) {
        const y = yOf(pct);
        // Always draw endpoints; skip middle ones if too close
        if (pct !== 1.0 && pct !== 0.0 && y - lastLabelY < m.fontSize + 4) return;
        lastLabelY = y;
        const label = totalScore > 0
            ? (Math.round(pct * totalScore) + 'pt')
            : (Math.round(pct * 100) + '%');
        ctx.fillText(label, mL - 4, y);
    });

    // X-axis date labels at each critical point
    ctx.textBaseline = 'top';
    let lastLabelX = -Infinity;
    const minGap   = m.fontSize * 5.2;
    // The final point is the vertical drop to 0 % and shares its timestamp with
    // the previous one, so it carries no label of its own.
    const labelled = points.filter(function (pt) { return pt.label; });
    labelled.forEach(function (pt, i) {
        const x       = xOf(pt.ts);
        const isFirst = (i === 0);
        const isLast  = (i === labelled.length - 1);

        // Enforce spacing; always show first and last
        if (!isFirst && !isLast && x - lastLabelX < minGap) return;
        // Skip intermediate labels that would crowd the final label
        if (!isLast && (xOf(labelled[labelled.length - 1].ts) - x) < minGap && !isFirst) return;

        ctx.textAlign = isFirst ? 'left' : (isLast ? 'right' : 'center');
        const labelX  = isFirst ? mL : (isLast ? mL + pW : x);
        ctx.fillStyle = color.text;
        ctx.fillText(pt.label, labelX, mT + pH + 5);

        // Tick mark
        ctx.strokeStyle = color.axis;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, mT + pH);
        ctx.lineTo(x, mT + pH + 3);
        ctx.stroke();

        lastLabelX = x;
    });

    // "Now" dashed marker — only while the deadline window is open
    if (nowTs > minTs && nowTs < maxTs) {
        const nx = xOf(nowTs);

        // Interpolate the currently achievable percentage. The last segment is
        // the vertical cliff at `end` (zero width), so skip it to avoid /0.
        // Uses a half-open interval [ts, nextTs) so that at the exact `end`
        // instant the value is 0 %, matching get_current_percent_multiplier().
        let curPct = 0;
        for (let i = 0; i < points.length - 1; i++) {
            const span = points[i + 1].ts - points[i].ts;
            if (span <= 0) continue;
            if (nowTs >= points[i].ts && nowTs < points[i + 1].ts) {
                const t = (nowTs - points[i].ts) / span;
                curPct = points[i].pct + t * (points[i + 1].pct - points[i].pct);
                break;
            }
        }

        ctx.strokeStyle = color.now;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 3]);
        ctx.beginPath();
        ctx.moveTo(nx, mT);
        ctx.lineTo(nx, mT + pH);
        ctx.stroke();
        ctx.setLineDash([]);

        // Dot at current achievable score on the curve
        ctx.fillStyle = color.now;
        ctx.beginPath();
        ctx.arc(nx, yOf(curPct), 4, 0, Math.PI * 2);
        ctx.fill();
    }

    // Dots at key breakpoints
    ctx.fillStyle = color.dot;
    points.forEach(function (pt) {
        ctx.beginPath();
        ctx.arc(xOf(pt.ts), yOf(pt.pct), 3, 0, Math.PI * 2);
        ctx.fill();
    });
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
