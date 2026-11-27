import { useState } from "react";
import { Button } from "@/components/ui/button";

/** A two-step button: the first click asks, the second does it. Inline, so the operator keeps the
 * row they are acting on in view. */
export function ConfirmAction({
  label,
  question,
  onConfirm,
  disabled,
  disabledReason,
  pending,
}: {
  label: string;
  question: string;
  onConfirm: () => void;
  disabled?: boolean;
  disabledReason?: string;
  pending?: boolean;
}) {
  const [asking, setAsking] = useState(false);
  if (!asking) {
    return (
      <Button size="xs" variant="outline" disabled={disabled || pending} aria-label={label}
        title={disabled ? disabledReason : undefined}
        onClick={() => setAsking(true)}>
        {pending ? "Working…" : label}
      </Button>
    );
  }
  return (
    <span role="group" aria-label={question} className="inline-flex max-w-56 flex-wrap items-center justify-end gap-1.5 max-sm:justify-start">
      <span className="basis-full text-right text-xs max-sm:text-left text-muted-foreground">{question}</span>
      <Button size="xs" onClick={() => { setAsking(false); onConfirm(); }}>Confirm</Button>
      <Button size="xs" variant="ghost" onClick={() => setAsking(false)}>Cancel</Button>
    </span>
  );
}
