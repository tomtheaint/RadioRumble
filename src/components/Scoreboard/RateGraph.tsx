import React, { useRef, useEffect } from 'react';

interface RateGraphProps {
  data: number[];
}

const WIDTH = 80;
const HEIGHT = 24;
const GOLD = '#F4C55C';

const RateGraph: React.FC<RateGraphProps> = ({ data }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || data.length === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = WIDTH * dpr;
    canvas.height = HEIGHT * dpr;
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, WIDTH, HEIGHT);

    const max = Math.max(...data, 1);
    const step = data.length > 1 ? WIDTH / (data.length - 1) : 0;

    const points = data.map((val, i) => ({
      x: i * step,
      y: HEIGHT - (val / max) * (HEIGHT - 4) - 2,
    }));

    // Fill
    ctx.beginPath();
    ctx.moveTo(points[0].x, HEIGHT);
    points.forEach((p) => ctx.lineTo(p.x, p.y));
    ctx.lineTo(points[points.length - 1].x, HEIGHT);
    ctx.closePath();
    ctx.fillStyle = `${GOLD}18`;
    ctx.fill();

    // Line
    ctx.beginPath();
    points.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
    ctx.strokeStyle = GOLD;
    ctx.lineWidth = 1.5;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.stroke();

    // End dot
    const last = points[points.length - 1];
    ctx.beginPath();
    ctx.arc(last.x, last.y, 2, 0, Math.PI * 2);
    ctx.fillStyle = GOLD;
    ctx.fill();
  }, [data]);

  if (data.length === 0) {
    return (
      <span style={{ color: 'var(--text-secondary)', fontSize: 12, width: WIDTH }}>—</span>
    );
  }

  return (
    <canvas
      ref={canvasRef}
      style={{ width: WIDTH, height: HEIGHT, display: 'block' }}
    />
  );
};

export default RateGraph;
