import type { Capability } from "@/lib/api";

type Props = { capability: Capability };

export function CapabilityRow({ capability }: Props) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        height: 32,
        padding: "0 var(--space-4)",
        fontSize: 13,
        color: "var(--text-primary)",
      }}
    >
      <Indicator status={capability.status} />
      <span style={{ flex: 1 }}>{capability.label}</span>
      {capability.status === "reconnect" && capability.reconnect_url ? (
        <a
          href={capability.reconnect_url}
          style={{
            fontSize: 12,
            color: "var(--accent-text)",
            fontWeight: 500,
          }}
        >
          {capability.detail ?? "Reconnect"}
        </a>
      ) : (
        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
          {capability.detail ?? capability.status}
        </span>
      )}
    </div>
  );
}

function Indicator({ status }: { status: Capability["status"] }) {
  if (status === "ready") {
    return (
      <span
        aria-hidden
        style={{
          display: "inline-block",
          width: 10,
          height: 10,
          borderRadius: "50%",
          background: "var(--success)",
          flexShrink: 0,
        }}
      />
    );
  }
  if (status === "syncing") {
    return (
      <span
        aria-hidden
        className="capability-syncing"
        style={{
          display: "inline-block",
          width: 10,
          height: 10,
          borderRadius: "50%",
          border: "2px solid var(--warning)",
          flexShrink: 0,
        }}
      />
    );
  }
  if (status === "reconnect") {
    return (
      <span
        aria-hidden
        style={{
          display: "inline-block",
          width: 10,
          height: 10,
          color: "var(--error)",
          fontSize: 14,
          lineHeight: 1,
          flexShrink: 0,
        }}
      >
        ⚠
      </span>
    );
  }
  return (
    <span
      aria-hidden
      style={{
        display: "inline-block",
        width: 10,
        height: 10,
        borderRadius: "50%",
        background: "var(--text-disabled)",
        flexShrink: 0,
      }}
    />
  );
}
