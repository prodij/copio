import type { ApiError } from "@/api/errors";

export function ErrorState({ error }: { error: ApiError }) {
  return (
    <div role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 p-4 text-sm">
      <p className="font-mono text-destructive">{error.status}</p>
      <p className="text-muted-foreground">{error.detail}</p>
    </div>
  );
}
