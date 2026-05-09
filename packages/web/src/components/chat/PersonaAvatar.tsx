type Props = { initials: string; size?: number };

export function PersonaAvatar({ initials, size = 32 }: Props) {
  const fontSize = Math.round(size * 0.34);
  return (
    <div
      aria-hidden
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        background: "var(--accent)",
        color: "var(--accent-fg)",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        fontWeight: 600,
        fontSize: `${fontSize}px`,
        letterSpacing: "0.05em",
        flexShrink: 0,
      }}
    >
      {initials}
    </div>
  );
}
