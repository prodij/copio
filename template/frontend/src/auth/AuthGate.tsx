import { useEffect, useState, type ReactNode } from "react";
import { PageSkeleton } from "@/components/PageSkeleton";
import { Button } from "@/components/ui/button";
import { userManager } from "./userManager";

// The authorization code can be exchanged only once; StrictMode mounts effects twice in dev.
let callbackDone: Promise<unknown> | null = null;
function handleCallbackOnce() {
  callbackDone ??= userManager.signinRedirectCallback();
  return callbackDone;
}

export function AuthGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<"loading" | "in" | "out">("loading");
  useEffect(() => {
    const run = async () => {
      if (window.location.pathname === "/callback") await handleCallbackOnce();
      const user = await userManager.getUser();
      setState(user && !user.expired ? "in" : "out");
    };
    run().catch(() => setState("out"));
  }, []);
  if (state === "loading") return <PageSkeleton />;
  if (state === "out") {
    return (
      <main className="mx-auto mt-24 max-w-sm space-y-4 text-center">
        <h1 className="text-xl font-semibold">{document.title}</h1>
        <Button onClick={() => void userManager.signinRedirect()}>Sign in</Button>
      </main>
    );
  }
  return <>{children}</>;
}
