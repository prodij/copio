import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { ApiError } from "@/api/errors";
import { syncKeys } from "./api";

export type Notice = { kind: "ok" | "error"; text: string; key: string };

/** Runs one sync action at a time, then refreshes every sync screen and says what happened. Actions
 * only queue work, so success means "queued", never "done". */
export function useSyncAction() {
  const client = useQueryClient();
  const [notice, setNotice] = useState<Notice | null>(null);
  const mutation = useMutation<unknown, ApiError, { key: string; run: () => Promise<unknown>; done: string }>({
    mutationFn: ({ run }) => run(),
    onSuccess: (_run, { key, done }) => setNotice({ kind: "ok", text: done, key }),
    onError: (error, { key }) => setNotice({ kind: "error", text: error.detail, key }),
    onSettled: () => client.invalidateQueries({ queryKey: syncKeys.all }),
  });
  return {
    notice,
    pendingKey: mutation.isPending ? mutation.variables?.key : undefined,
    act: (key: string, run: () => Promise<unknown>, done: string) => {
      setNotice(null);
      mutation.mutate({ key, run, done });
    },
  };
}

/** Shown next to where the action was taken: `scope` is the action key's prefix(es), e.g. "refresh". */
export function ActionNotice({ notice, scope }: { notice: Notice | null; scope: string[] }) {
  if (!notice || !scope.includes(notice.key.split(":")[0])) return null;
  return notice.kind === "ok" ? (
    <p role="status" className="rounded-md border border-border bg-muted/40 px-3 py-2 text-sm">{notice.text}</p>
  ) : (
    <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">{notice.text}</p>
  );
}
