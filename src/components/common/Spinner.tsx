import React from 'react';

interface SpinnerProps {
  size?: number;
  color?: string;
  style?: React.CSSProperties;
}

const keyframesId = 'ksu-spinner-keyframes';

function ensureKeyframes() {
  if (typeof document === 'undefined') return;
  if (document.getElementById(keyframesId)) return;

  const style = document.createElement('style');
  style.id = keyframesId;
  style.textContent = `
    @keyframes ksu-spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
  `;
  document.head.appendChild(style);
}

export default function Spinner({
  size = 28,
  color = '#512888',
  style,
}: SpinnerProps) {
  React.useEffect(() => {
    ensureKeyframes();
  }, []);

  return (
    <div
      role="status"
      aria-label="Loading"
      style={{
        width: size,
        height: size,
        border: `3px solid rgba(81, 40, 136, 0.2)`,
        borderTopColor: color,
        borderRadius: '50%',
        animation: 'ksu-spin 0.7s linear infinite',
        ...style,
      }}
    >
      <span
        style={{
          position: 'absolute',
          width: 1,
          height: 1,
          padding: 0,
          margin: -1,
          overflow: 'hidden',
          clip: 'rect(0,0,0,0)',
          whiteSpace: 'nowrap',
          border: 0,
        }}
      >
        Loading...
      </span>
    </div>
  );
}
