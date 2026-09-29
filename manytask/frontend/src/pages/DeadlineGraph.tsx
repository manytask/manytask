import {useEffect, useRef, useState} from 'react';
import {useThemeValue} from '@gravity-ui/uikit';

export type DeadlineGraphData = {
  points: Array<{ts: number; pct: number; label: string; date: string; time: string; tz: string}>;
  status: 'expired' | 'urgent' | 'active';
  percent: number;
  hint: string;
};

type Hotspot = {x: number; y: number; point: DeadlineGraphData['points'][number]};

export function DeadlineGraph({graph, now}: {graph: DeadlineGraphData; now: string}) {
  const themeValue = useThemeValue();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const hotspots = useRef<Hotspot[]>([]);
  const [tip, setTip] = useState<Hotspot | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || graph.points.length < 2) return;
    const draw = () => {
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      const style = getComputedStyle(canvas);
      const metric = (name: string, fallback: number) => Number.parseFloat(style.getPropertyValue(name)) || fallback;
      const color = (name: string, fallback: string) => style.getPropertyValue(name).trim() || fallback;
      const height = metric('--graph-height', 95);
      const left = metric('--graph-margin-left', 38);
      const right = metric('--graph-margin-right', 9);
      const top = metric('--graph-margin-top', 7);
      const bottom = metric('--graph-margin-bottom', 24);
      const fontSize = metric('--graph-font-size', 10);
      const width = canvas.getBoundingClientRect().width || canvas.parentElement?.clientWidth || 300;
      const ratio = window.devicePixelRatio || 1;
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      canvas.style.height = `${height}px`;
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      const plotWidth = Math.max(width - left - right, 1);
      const plotHeight = Math.max(height - top - bottom, 1);
      const points = graph.points;
      const first = points[0].ts;
      const span = points[points.length - 1].ts - first || 1;
      const x = (ts: number) => left + (ts - first) / span * plotWidth;
      const y = (pct: number) => top + (1 - pct) * plotHeight;

      ctx.clearRect(0, 0, width, height);
      ctx.strokeStyle = color('--graph-grid', '#ddd');
      ctx.lineWidth = 1;
      for (const pct of [0, 0.5, 1]) {
        ctx.beginPath(); ctx.moveTo(left, y(pct)); ctx.lineTo(left + plotWidth, y(pct)); ctx.stroke();
      }
      const trace = () => {
        ctx.moveTo(x(points[0].ts), y(points[0].pct));
        for (const point of points.slice(1)) ctx.lineTo(x(point.ts), y(point.pct));
      };
      ctx.beginPath(); trace();
      ctx.lineTo(x(points[points.length - 1].ts), y(0));
      ctx.lineTo(x(points[0].ts), y(0)); ctx.closePath();
      ctx.fillStyle = color('--graph-fill', '#e1fae4'); ctx.fill();
      ctx.beginPath(); trace(); ctx.strokeStyle = color('--graph-line', '#4caf50');
      ctx.lineWidth = 2; ctx.lineJoin = 'round'; ctx.stroke();
      ctx.beginPath(); ctx.moveTo(left, top); ctx.lineTo(left, top + plotHeight);
      ctx.lineTo(left + plotWidth, top + plotHeight);
      ctx.strokeStyle = color('--graph-axis', '#999'); ctx.lineWidth = 1; ctx.stroke();

      ctx.font = `${fontSize}px ${style.fontFamily || 'system-ui, sans-serif'}`;
      ctx.fillStyle = color('--graph-text', '#777');
      ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
      const drawn: number[] = [];
      const middle = [...new Set(points.slice(1, -1).map((point) => point.pct))]
        .filter((pct) => pct !== 0 && pct !== 1).sort((a, b) => b - a);
      for (const pct of [1, 0, ...middle]) {
        if (drawn.some((position) => Math.abs(position - y(pct)) < fontSize + 3)) continue;
        drawn.push(y(pct));
        ctx.fillText(`${Math.round(pct * 100)}%`, left - 4, y(pct));
      }
      const labelled = points.filter((point) => point.label);
      const boxes = labelled.map((point, index) => {
        const align = index === 0 ? 'left' : index === labelled.length - 1 ? 'right' : 'center';
        const drawX = index === 0 ? left : index === labelled.length - 1 ? left + plotWidth : x(point.ts);
        const measured = ctx.measureText(point.label).width;
        const boxLeft = align === 'left' ? drawX : align === 'right' ? drawX - measured : drawX - measured / 2;
        return {point, align, drawX, left: boxLeft, right: boxLeft + measured, index};
      });
      const placed = boxes.filter((box) => box.index === 0 || box.index === boxes.length - 1);
      for (const box of boxes) {
        if (placed.includes(box)) continue;
        if (!placed.some((other) => box.left - 4 < other.right && box.right + 4 > other.left)) placed.push(box);
      }
      ctx.textBaseline = 'top';
      for (const box of placed) {
        ctx.textAlign = box.align as CanvasTextAlign;
        ctx.fillText(box.point.label, box.drawX, top + plotHeight + 2);
        ctx.beginPath(); ctx.moveTo(x(box.point.ts), top + plotHeight);
        ctx.lineTo(x(box.point.ts), top + plotHeight + 3); ctx.stroke();
      }

      const nowTs = Date.parse(now) / 1000;
      if (nowTs > first && nowTs < points[points.length - 1].ts) {
        let current = 0;
        for (let index = 0; index < points.length - 1; index++) {
          const part = points[index + 1].ts - points[index].ts;
          if (part > 0 && nowTs >= points[index].ts && nowTs < points[index + 1].ts) {
            current = points[index].pct + (nowTs - points[index].ts) / part * (points[index + 1].pct - points[index].pct);
            break;
          }
        }
        ctx.strokeStyle = color('--graph-now', '#ef6c00'); ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 3]); ctx.beginPath(); ctx.moveTo(x(nowTs), top);
        ctx.lineTo(x(nowTs), top + plotHeight); ctx.stroke(); ctx.setLineDash([]);
        ctx.fillStyle = color('--graph-now', '#ef6c00'); ctx.beginPath();
        ctx.arc(x(nowTs), y(current), 4, 0, Math.PI * 2); ctx.fill();
      }
      ctx.fillStyle = color('--graph-dot', '#388e3c');
      hotspots.current = points.filter((point) => point.date).map((point) => {
        const spot = {x: x(point.ts), y: y(point.pct), point};
        ctx.beginPath(); ctx.arc(spot.x, spot.y, 3, 0, Math.PI * 2); ctx.fill();
        return spot;
      });
    };
    // Gravity applies its body theme class in a layout effect. This effect runs
    // afterward, so getComputedStyle reads the new palette before painting.
    draw();
    if (typeof ResizeObserver !== 'undefined') {
      const observer = new ResizeObserver(draw);
      observer.observe(canvas);
      return () => observer.disconnect();
    }
    window.addEventListener('resize', draw);
    return () => window.removeEventListener('resize', draw);
  }, [graph, now, themeValue]);

  const onMove = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const mx = event.clientX - rect.left;
    const my = event.clientY - rect.top;
    const nearest = hotspots.current.map((spot) => ({spot, distance: Math.hypot(spot.x - mx, spot.y - my)}))
      .filter((item) => item.distance <= 7).sort((a, b) => a.distance - b.distance)[0];
    setTip(nearest?.spot ?? null);
  };

  return <div className={`assignment-graph-wrap ${graph.status}`}>
    <canvas ref={canvasRef} className="deadline-graph-canvas" role="img" aria-label="Deadline score curve"
      onMouseMove={onMove} onMouseLeave={() => setTip(null)} />
    {tip && <div role="tooltip" className="assignment-graph-tip" style={{left: tip.x, top: tip.y}}>
      {tip.point.date} {tip.point.time} {tip.point.tz}
    </div>}
  </div>;
}
