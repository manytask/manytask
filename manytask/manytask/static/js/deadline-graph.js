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

    // Y-axis labels. The plank is short, so only draw the breakpoints that fit;
    // the 100 % / 0 % endpoints always win over intermediate steps.
    // Percentages (not absolute points) keep the labels narrow enough for the
    // left margin — the exact score is already shown in .deadline-percent.
    ctx.font = labelFont;
    ctx.fillStyle = color.text;
    ctx.textAlign = 'right';
    const fmtPct = function (pct) {
        return Math.round(pct * 100) + '%';
    };
    const minYGap = m.fontSize + 3;
    const drawnY  = [];
    // endpoints first, then intermediates in descending order
    const midPcts = [...new Set(points.slice(1, -1).map(function (p) { return p.pct; }))]
        .filter(function (p) { return p !== 1.0 && p !== 0.0; })
        .sort(function (a, b) { return b - a; });
    ctx.textBaseline = 'middle';
    [1.0, 0.0].concat(midPcts).forEach(function (pct) {
        const y = yOf(pct);
        const clash = drawnY.some(function (dy) { return Math.abs(dy - y) < minYGap; });
        if (clash) return;
        drawnY.push(y);
        // Clamp into the canvas so the outermost labels are never cut off by
        // the top/bottom edge, while staying centred on their gridline.
        const half = m.fontSize * 0.5;
        const cy = Math.min(Math.max(y, half), cssHeight - half);
        ctx.fillText(fmtPct(pct), mL - 4, cy);
    });

    // X-axis labels. Each carries a time only when the deadline is not at the
    // end of the day (see the template), so widths are mixed and collisions are
    // resolved from the measured extents rather than one global gap.
    // The final point is the vertical drop to 0 % and shares its timestamp with
    // the previous one, so it carries no label of its own.
    ctx.textBaseline = 'top';
    const labelled = points.filter(function (pt) { return pt.label; });
    const PAD = 4;

    // Resolve each label's drawing position and horizontal extent up front.
    const boxes = labelled.map(function (pt, i) {
        const x     = xOf(pt.ts);
        const w     = ctx.measureText(pt.label).width;
        const first = (i === 0);
        const last  = (i === labelled.length - 1);
        const align = first ? 'left' : (last ? 'right' : 'center');
        const drawX = first ? mL : (last ? mL + pW : x);
        const left  = align === 'left' ? drawX : (align === 'right' ? drawX - w : drawX - w / 2);
        return { pt: pt, x: x, align: align, drawX: drawX, left: left, right: left + w, first: first, last: last };
    });

    // The first and last labels anchor the axis and are always drawn; drop any
    // intermediate label that would overlap an already-placed neighbour.
    const placed = boxes.filter(function (b) { return b.first || b.last; });
    boxes.forEach(function (b) {
        if (b.first || b.last) return;
        const clash = placed.some(function (p) {
            return b.left - PAD < p.right && b.right + PAD > p.left;
        });
        if (!clash) placed.push(b);
    });

    placed.forEach(function (b) {
        ctx.textAlign = b.align;
        ctx.fillStyle = color.text;
        ctx.fillText(b.pt.label, b.drawX, mT + pH + 2);

        // Tick mark
        ctx.strokeStyle = color.axis;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(b.x, mT + pH);
        ctx.lineTo(b.x, mT + pH + 3);
        ctx.stroke();
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

    // Dots at key breakpoints. Their positions are cached on the element so the
    // hover handler can map a cursor position back to a deadline.
    ctx.fillStyle = color.dot;
    const hotspots = [];
    points.forEach(function (pt) {
        const cx = xOf(pt.ts), cy = yOf(pt.pct);
        ctx.beginPath();
        ctx.arc(cx, cy, 3, 0, Math.PI * 2);
        ctx.fill();
        if (pt.date) hotspots.push({ x: cx, y: cy, pt: pt });
    });
    canvas._deadlineHotspots = hotspots;

    attachDeadlineTooltip(canvas);
}

/**
 * Shows a tippy tooltip with the full date/time when the cursor is over one of
 * the breakpoint dots. Mirrors the calendar/clock icon markup used by
 * .task-deadline__deadline-time on the non-interpolated planks.
 */
function attachDeadlineTooltip(canvas) {
    if (typeof tippy !== 'function') return;

    // Create the singleton instance once per canvas; later redraws (resize)
    // only refresh the cached hotspot coordinates.
    if (!canvas._deadlineTippy) {
        canvas._deadlineTippy = tippy(canvas, {
            trigger: 'manual',
            arrow: false,
            allowHTML: true,
            placement: 'top',
            offset: [0, 8],
            content: ''
        });

        const HIT_RADIUS = 7;

        canvas.addEventListener('mousemove', function (event) {
            const spots = canvas._deadlineHotspots || [];
            const rect  = canvas.getBoundingClientRect();
            const mx    = event.clientX - rect.left;
            const my    = event.clientY - rect.top;

            let hit = null;
            let bestDist = Infinity;
            spots.forEach(function (s) {
                const d = Math.hypot(s.x - mx, s.y - my);
                if (d <= HIT_RADIUS && d < bestDist) {
                    bestDist = d;
                    hit = s;
                }
            });

            const tip = canvas._deadlineTippy;
            if (!hit) {
                tip.hide();
                canvas.style.cursor = '';
                return;
            }

            canvas.style.cursor = 'pointer';
            tip.setContent(
                '<span class="deadline-graph-tip">' +
                    '<span><i class="far fa-calendar"></i> ' + hit.pt.date + '</span>' +
                    '<span><i class="far fa-clock"></i> ' + hit.pt.time +
                        (hit.pt.tz ? ' ' + hit.pt.tz : '') + '</span>' +
                '</span>'
            );
            // Anchor the tooltip to the dot rather than the cursor.
            tip.setProps({
                getReferenceClientRect: function () {
                    const r = canvas.getBoundingClientRect();
                    return {
                        width: 0, height: 0,
                        top: r.top + hit.y, bottom: r.top + hit.y,
                        left: r.left + hit.x, right: r.left + hit.x
                    };
                }
            });
            tip.show();
        });

        canvas.addEventListener('mouseleave', function () {
            canvas._deadlineTippy.hide();
            canvas.style.cursor = '';
        });
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
