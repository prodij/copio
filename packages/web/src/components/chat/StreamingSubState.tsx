"use client";

type Props = { label: string };

export function StreamingSubState({ label }: Props) {
  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        fontSize: 13,
        color: "var(--text-muted)",
        fontStyle: "normal",
      }}
    >
      <span>{label}</span>
      <span className="streaming-caret" aria-hidden />
    </div>
  );
}
