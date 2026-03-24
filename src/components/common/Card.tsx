import React from 'react';

interface CardProps {
  title?: string;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export default function Card({ title, children, style }: CardProps) {
  return (
    <div style={{ ...styles.card, ...style }}>
      {title && <h3 style={styles.title}>{title}</h3>}
      {children}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  card: {
    background: '#2d1d42',
    border: '1px solid #3a2a52',
    borderRadius: 8,
    padding: 16,
  },
  title: {
    fontSize: 14,
    fontWeight: 700,
    color: '#F4C55C',
    letterSpacing: '0.03em',
    marginBottom: 12,
    textTransform: 'uppercase',
  },
};
