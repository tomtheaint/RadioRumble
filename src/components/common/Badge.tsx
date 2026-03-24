import React from 'react';

type BadgeVariant = 'success' | 'warning' | 'danger' | 'info';

interface BadgeProps {
  text: string;
  variant: BadgeVariant;
  style?: React.CSSProperties;
}

const variantColors: Record<BadgeVariant, { bg: string; color: string }> = {
  success: { bg: 'rgba(74, 222, 128, 0.15)', color: '#4ade80' },
  warning: { bg: 'rgba(244, 197, 92, 0.15)', color: '#F4C55C' },
  danger: { bg: 'rgba(239, 68, 68, 0.15)', color: '#ef4444' },
  info: { bg: 'rgba(107, 63, 160, 0.25)', color: '#a78bfa' },
};

export default function Badge({ text, variant, style }: BadgeProps) {
  const colors = variantColors[variant];

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: '0.04em',
        padding: '3px 10px',
        borderRadius: 999,
        background: colors.bg,
        color: colors.color,
        border: `1px solid ${colors.color}33`,
        lineHeight: 1.4,
        textTransform: 'uppercase',
        whiteSpace: 'nowrap',
        ...style,
      }}
    >
      {text}
    </span>
  );
}
