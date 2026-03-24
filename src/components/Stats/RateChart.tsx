import { useRef, useEffect } from 'react';

interface RateChartProps {
  data: Array<{ hour: string; count: number }>;
}

const GOLD = '#F4C55C';
const GOLD_TRANSPARENT = 'rgba(244, 197, 92, 0.15)';
const CREAM = '#E7DED0';
const GRID_LINE = 'rgba(231, 222, 208, 0.1)';

export default function RateChart({ data }: RateChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container || data.length === 0) return;

    const draw = () => {
      const rect = container.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      const w = rect.width;
      const h = 220;

      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;

      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      ctx.scale(dpr, dpr);

      const padLeft = 44;
      const padRight = 12;
      const padTop = 12;
      const padBottom = 28;
      const chartW = w - padLeft - padRight;
      const chartH = h - padTop - padBottom;

      const maxCount = Math.max(...data.map((d) => d.count), 1);
      const ySteps = 4;

      // Clear
      ctx.clearRect(0, 0, w, h);

      // Y-axis grid lines and labels
      ctx.font = '11px system-ui, sans-serif';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      for (let i = 0; i <= ySteps; i++) {
        const val = Math.round((maxCount / ySteps) * i);
        const y = padTop + chartH - (i / ySteps) * chartH;
        ctx.strokeStyle = GRID_LINE;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(padLeft, y);
        ctx.lineTo(padLeft + chartW, y);
        ctx.stroke();

        ctx.fillStyle = CREAM;
        ctx.globalAlpha = 0.5;
        ctx.fillText(val.toString(), padLeft - 6, y);
        ctx.globalAlpha = 1;
      }

      // X-axis labels
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      const labelInterval = Math.max(1, Math.floor(data.length / 8));
      data.forEach((d, i) => {
        if (i % labelInterval === 0 || i === data.length - 1) {
          const x = padLeft + (i / (data.length - 1)) * chartW;
          ctx.fillStyle = CREAM;
          ctx.globalAlpha = 0.5;
          ctx.fillText(d.hour, x, h - padBottom + 8);
          ctx.globalAlpha = 1;
        }
      });

      if (data.length < 2) return;

      // Build path points
      const points: [number, number][] = data.map((d, i) => [
        padLeft + (i / (data.length - 1)) * chartW,
        padTop + chartH - (d.count / maxCount) * chartH,
      ]);

      // Area fill
      ctx.beginPath();
      ctx.moveTo(points[0][0], padTop + chartH);
      points.forEach(([x, y]) => ctx.lineTo(x, y));
      ctx.lineTo(points[points.length - 1][0], padTop + chartH);
      ctx.closePath();
      ctx.fillStyle = GOLD_TRANSPARENT;
      ctx.fill();

      // Line
      ctx.beginPath();
      ctx.moveTo(points[0][0], points[0][1]);
      for (let i = 1; i < points.length; i++) {
        ctx.lineTo(points[i][0], points[i][1]);
      }
      ctx.strokeStyle = GOLD;
      ctx.lineWidth = 2;
      ctx.lineJoin = 'round';
      ctx.stroke();

      // Dots
      points.forEach(([x, y]) => {
        ctx.beginPath();
        ctx.arc(x, y, 3, 0, Math.PI * 2);
        ctx.fillStyle = GOLD;
        ctx.fill();
      });
    };

    draw();

    const observer = new ResizeObserver(draw);
    observer.observe(container);
    return () => observer.disconnect();
  }, [data]);

  if (data.length === 0) {
    return <div style={{ color: '#E7DED0', opacity: 0.5 }}>No rate data available</div>;
  }

  return (
    <div ref={containerRef} style={{ width: '100%' }}>
      <canvas ref={canvasRef} />
    </div>
  );
}
