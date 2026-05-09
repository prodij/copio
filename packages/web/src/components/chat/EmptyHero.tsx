import { PersonaAvatar } from "./PersonaAvatar";

type Props = {
  personaInitials: string;
  greeting: string;
  examples: string[];
  onPick: (q: string) => void;
};

export function EmptyHero({
  personaInitials,
  greeting,
  examples,
  onPick,
}: Props) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        padding: "var(--space-16) var(--space-6)",
        gap: "var(--space-6)",
      }}
    >
      <PersonaAvatar initials={personaInitials} size={56} />
      <div
        style={{
          fontFamily: "var(--font-display)",
          fontSize: 24,
          fontWeight: 500,
          color: "var(--text-primary)",
          maxWidth: 540,
          lineHeight: 1.3,
        }}
      >
        {greeting}
      </div>
      <div
        style={{
          display: "flex",
          gap: "var(--space-2)",
          flexWrap: "wrap",
          justifyContent: "center",
          maxWidth: 720,
        }}
      >
        {examples.map((ex) => (
          <button
            key={ex}
            type="button"
            onClick={() => onPick(ex)}
            style={{
              fontSize: 14,
              color: "var(--text-primary)",
              background: "var(--bg-elevated)",
              border: "1px solid var(--border-subtle)",
              borderRadius: 16,
              padding: "var(--space-2) var(--space-4)",
              transition: "border-color 100ms ease-out, transform 100ms ease-out",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.borderColor =
                "var(--border-strong)";
              (e.currentTarget as HTMLButtonElement).style.transform =
                "translateY(-1px)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.borderColor =
                "var(--border-subtle)";
              (e.currentTarget as HTMLButtonElement).style.transform =
                "translateY(0)";
            }}
          >
            {ex}
          </button>
        ))}
      </div>
    </div>
  );
}
