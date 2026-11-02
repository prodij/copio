import { execFileSync } from "node:child_process";

// The mock payment test pauses lago-worker and stops jobs. restoreStack puts them back; it also runs
// before and after every mock payment `make e2e` (Playwright globalSetup and globalTeardown), so a
// killed run can't leave them held for the next one.

// `make e2e` runs from e2e/, so Compose finds the product's docker-compose.yml and .env one level up.
export function compose(...args: string[]): string {
  return execFileSync("docker", ["compose", ...args], {
    cwd: "..",
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    timeout: 60_000,
  }).trim();
}

const STEPS: [string, () => void][] = [
  ["unpause lago-worker", () => {
    // Compose fails on a container that isn't paused, so ask first.
    if (compose("ps", "lago-worker", "--format", "{{.State}}") === "paused") compose("unpause", "lago-worker");
  }],
  ["start jobs", () => void compose("start", "jobs")],
];

// Tries every step, logs what failed and returns the errors, so one failure can't skip the other step.
export function restoreStack(): unknown[] {
  const errors: unknown[] = [];
  for (const [name, step] of STEPS) {
    try {
      step();
    } catch (error) {
      console.error(`Mock payment cleanup: ${name} failed: ${error}`);
      errors.push(error);
    }
  }
  return errors;
}

export default function globalSetupAndTeardown() {
  const errors = restoreStack();
  if (errors.length) throw errors[0];
}
