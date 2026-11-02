import { expect, test, type Page } from "@playwright/test";
import { compose, restoreStack } from "./mock-payment-stack";

// Milestone 1's definition of done (spec §1): sign up through Zitadel, create a workspace, save
// Stripe's test card on Stripe's hosted page, and see premium_report switch on because Lago's
// invoice-paid webhook said so, never because the browser came back from Stripe.
// Everything up to the plans page works without Stripe, so it has its own test; the payment test
// needs a key and is skipped without one. `make e2e` sets STRIPE_CONFIGURED (never the key itself).
//
// With BILLING_MODE=mock in .env, `make e2e` sets MOCK_PAYMENT and the mock payment test runs instead:
// real Zitadel, real Lago, its real signed webhook, and a faked payment step. It is not a Stripe pass.
//
// Two blocks of selectors belong to pages we do not own. If one fails, fix it here only:
// - signUp(): Zitadel login UI ghcr.io/zitadel/zitadel-login:v4.20.0 (labels checked 2026-11-01).
// - saveTestCard(): Stripe Checkout, hosted, setup mode (input ids as of 2026-11-01).

const PASSWORD = "Correct-horse-battery-9";
const WORKSPACE = "E2E Co";
const STRIPE_CONFIGURED = !!process.env.STRIPE_CONFIGURED;
const NOT_SET_UP = /billing isn't set up/i;
const MOCK_PAYMENT = !!process.env.MOCK_PAYMENT;
const NO_KEY = MOCK_PAYMENT
  ? "this is a mock payment run, which has no Stripe key"
  : "STRIPE_SECRET_KEY is empty: add a Stripe test key to .env and run make bootstrap";
const NOT_A_STRIPE_PASS = "A mock payment pass is not a Stripe pass.";

const sql = (database: string, query: string) =>
  compose("exec", "-T", "postgres", "psql", "-U", "postgres", "-d", database, "-Atc", query);

async function signUp(page: Page, email: string) {
  // No email code: the login UI asks for one only when EMAIL_VERIFICATION=true (unset in Compose).
  await page.getByRole("button", { name: /register new user/i }).click();
  await page.getByLabel(/first name/i).fill("E2E");
  await page.getByLabel(/last name/i).fill("User");
  await page.getByLabel(/e-?mail/i).fill(email);
  await page.getByRole("radio", { name: /password/i }).click(); // the default is Passkey
  await page.getByRole("button", { name: /continue/i }).click();
  await page.waitForURL(/\/register\/password/);
  await page.getByRole("textbox", { name: /^password/i }).fill(PASSWORD); // "Password *"
  await page.getByRole("textbox", { name: /^confirm password/i }).fill(PASSWORD);
  await page.getByRole("button", { name: /continue/i }).click();
}

async function saveTestCard(page: Page) {
  const card = page.locator("#cardNumber");
  const cardChoice = page.getByTestId("card-accordion-item-button");
  await card.or(cardChoice).first().waitFor();
  if (await cardChoice.isVisible()) await cardChoice.click();
  const email = page.locator("#email");
  if ((await email.isVisible()) && (await email.isEditable()) && !(await email.inputValue())) {
    await email.fill("e2e@example.com");
  }
  await card.fill("4242 4242 4242 4242");
  await page.locator("#cardExpiry").fill("12 / 34");
  await page.locator("#cardCvc").fill("123");
  for (const [id, value] of [["#billingName", "E2E User"], ["#billingPostalCode", "94103"]] as const) {
    const field = page.locator(id);
    if (await field.isVisible()) await field.fill(value);
  }
  await page.getByTestId("hosted-payment-submit-button").click();
}

// The plan the tests buy, found by its code: a product can rename it or list other plans first.
const PLAN_CODE = "starter";

// Resolves to the "Choose <plan's name>" button once the Plans page has loaded.
async function signUpToPlans(page: Page, app: string, workspace = WORKSPACE) {
  await page.goto("/");
  await expect(async () => {
    const loaded = await page.getByRole("main").locator("img").evaluate((i) => (i as HTMLImageElement).naturalWidth > 0);
    expect(loaded).toBe(true);
  }, "the app's logo").toPass({ timeout: 10_000 });
  await page.getByRole("button", { name: "Sign in" }).click();
  // Zitadel draws a light and a dark logo and hides one: both must load, or the page shows a broken image.
  const logos = page.getByRole("img", { name: "logo", includeHidden: true });
  await expect(logos).toHaveCount(2);
  await expect(async () => {
    expect(await logos.evaluateAll((images) => images.every((i) => (i as HTMLImageElement).naturalWidth > 0))).toBe(true);
  }, "the sign-in page's logo").toPass({ timeout: 10_000 });
  await signUp(page, `e2e+${Date.now()}@example.com`);

  await page.waitForURL(`${app}/workspace/new`);
  await page.getByLabel("Workspace name").fill(workspace);
  const plansLoaded = page.waitForResponse(
    (r) => r.url().endsWith("/billing/plans") && r.request().method() === "GET" && r.ok(),
  );
  await page.getByRole("button", { name: "Create workspace" }).click();
  await page.waitForURL(`${app}/plans`);
  const plans: { code: string; name: string }[] = await (await plansLoaded).json();
  const plan = plans.find((p) => p.code === PLAN_CODE);
  expect(plan, `backend/app/billing/plans.yaml must keep a plan with code ${PLAN_CODE}`).toBeDefined();
  return page.getByRole("button", { name: `Choose ${plan!.name}`, exact: true });
}

test("sign up → workspace → plans", async ({ page, baseURL }) => {
  const choose = await signUpToPlans(page, new URL(baseURL!).origin);
  // Invoices embed the billing entity's logo; a missing file makes every invoice PDF fail.
  const logoKey = sql("lago", "select b.key from active_storage_blobs b join active_storage_attachments a on a.blob_id = b.id " +
                              "where a.record_type = 'BillingEntity' and a.name = 'logo'");
  expect(logoKey, "make brand gave Lago's billing entity a logo").not.toBe("");
  compose("exec", "-T", "lago-worker", "test", "-f", `storage/${logoKey.slice(0, 2)}/${logoKey.slice(2, 4)}/${logoKey}`);
  await expect(choose).toBeVisible();
  if (!MOCK_PAYMENT) await expect(page.getByText("Mock payment")).toHaveCount(0); // off by default
  if (STRIPE_CONFIGURED || MOCK_PAYMENT) return;

  // No key: the app says billing isn't set up, right away, and access stays denied.
  await choose.click();
  await expect(page.getByRole("alert")).toContainText(NOT_SET_UP, { timeout: 5_000 });
  await page.goto("/billing");
  await expect(page.getByText(NOT_SET_UP)).toBeVisible();
  await page.goto("/premium");
  await expect(page.getByRole("alert")).toContainText("402");
});

test("sign up → workspace → pay → premium report", async ({ page, baseURL }) => {
  if (!STRIPE_CONFIGURED) console.log(`Stripe payment test skipped. ${NO_KEY}`); // the list reporter hides skip reasons
  test.skip(!STRIPE_CONFIGURED, NO_KEY);
  const app = new URL(baseURL!).origin;
  const choose = await signUpToPlans(page, app);

  // Lago creates the Stripe customer in a background job; until then checkout answers 503 and
  // the page shows the error, so choosing the plan is retried until Stripe's page opens.
  await expect(async () => {
    await choose.click();
    await page.waitForURL(/checkout\.stripe\.com/, { timeout: 10_000 });
  }).toPass({ timeout: 120_000, intervals: [5_000] });

  // Second leg (checkout option A): Stripe's page only saves the card. Back on /billing/return,
  // the app calls POST /billing/checkout again (retrying for up to 60 s while Lago has not yet
  // processed Stripe's webhook) until it answers checkout_url null: the gated subscription exists.
  const secondLeg = page.waitForResponse(
    async (r) =>
      r.url().endsWith("/billing/checkout") &&
      r.request().method() === "POST" &&
      r.status() === 200 &&
      (await r.json()).checkout_url === null,
    { timeout: 120_000 },
  );
  await saveTestCard(page);
  await page.waitForURL((u) => u.origin === app, { timeout: 120_000 });
  // From here on the card is saved: the app must never send the browser back to Stripe.
  const backToStripe: string[] = [];
  page.on("framenavigated", (frame) => {
    if (frame === page.mainFrame() && /checkout\.stripe\.com/.test(frame.url())) backToStripe.push(frame.url());
  });
  await secondLeg;

  // Access follows Lago's invoice-paid webhook, so wait on the feature itself, not on the return page.
  await expect(async () => {
    await page.goto("/premium");
    await expect(page.getByText(`Generated for ${WORKSPACE}`)).toBeVisible({ timeout: 5_000 });
  }).toPass({ timeout: 180_000, intervals: [3_000] });
  expect(backToStripe, "the app sent the browser back to Stripe after the card was saved").toEqual([]);
});

// Must fail if anything but Lago's webhook turns premium on. Delivery is held back by pausing Lago's
// worker, and billing_reconcile (which would also repair the state, from Lago's API) is stopped, so
// the webhook is the only thing left that can change the state.
test("mock payment: sign up → workspace → mock payment → premium report from Lago's webhook", async ({ page, baseURL }) => {
  test.skip(!MOCK_PAYMENT, "BILLING_MODE is not mock: mock payment is off, as it is by default");
  const app = new URL(baseURL!).origin;
  const workspace = `Mock Co ${Date.now()}`;
  const toStripe: string[] = [];
  page.on("request", (r) => {
    if (/(^|\.)stripe\.(com|network)$/.test(new URL(r.url()).hostname)) toStripe.push(r.url());
  });
  const row = () =>
    sql("app", `select s.state, s.lago_external_id, s.lago_subscription_id from subscriptions s join workspaces w ` +
               `on w.id = s.workspace_id where w.name = '${workspace}'`).split("|");

  let passed = false;
  compose("stop", "jobs");
  try {
    const choose = await signUpToPlans(page, app, workspace);
    const banner = page.getByRole("status");
    await expect(banner).toContainText("Mock payment");
    await choose.click();
    await page.waitForURL(`${app}/billing/mock-payment`);
    await expect(page.getByRole("heading", { name: "Mock payment" })).toBeVisible();
    await expect(banner).toContainText("not real billing");

    compose("pause", "lago-worker");
    const created = page.waitForResponse(
      async (r) =>
        r.url().endsWith("/billing/checkout") && r.request().method() === "POST" && r.status() === 200 &&
        (await r.json()).checkout_url === null,
    );
    await page.getByRole("button", { name: "Confirm mock payment" }).click();
    await page.waitForURL(`${app}/billing/return`);
    await created;
    await expect(page.getByText("Waiting for payment confirmation…")).toBeVisible();
    await expect(banner).toContainText("Mock payment");

    // The browser is back and Lago says active, but no webhook has landed: premium must stay off.
    const [state, externalId, lagoId] = row();
    expect(state, "the return alone must not change the state").toBe("pending");
    expect(lagoId).toBe(externalId);
    expect(sql("lago", `select status from subscriptions where external_id = '${externalId}'`)).toBe("1"); // active
    const delivered = () =>
      sql("app", `select type, processed_at is not null, signature_sha256 is not null from webhook_events ` +
                 `where payload->'subscription'->>'external_id' = '${externalId}'`);
    expect(delivered()).toBe("");
    for (let check = 0; check < 3; check++) {
      await page.goto("/premium");
      await expect(page.getByRole("alert")).toContainText("402");
      await page.waitForTimeout(3_000);
    }
    expect(row()[0]).toBe("pending");

    compose("unpause", "lago-worker");
    await expect(async () => {
      await page.goto("/premium");
      await expect(page.getByText(`Generated for ${workspace}`)).toBeVisible({ timeout: 5_000 });
    }).toPass({ timeout: 120_000, intervals: [3_000] });

    expect(row()[0], "Lago's webhook moves the state").toBe("active");
    const events = delivered().split("\n");
    expect(events, "a processed, signed subscription.started").toContain("subscription.started|t|t");
    console.log(`Mock payment: pending -> active by Lago's signed webhook. Events for ${externalId}: ${events.join(", ")}`);

    // Nothing here talked to Stripe: no browser request, no provider in Lago, stripe-cli idle.
    expect(toStripe).toEqual([]);
    expect(sql("lago", "select count(*) from payment_providers where deleted_at is null")).toBe("0");
    expect(compose("logs", "--no-log-prefix", "stripe-cli")).toContain("idle");
    console.log(`MOCK PAYMENT passed. The Stripe payment test did not run. ${NOT_A_STRIPE_PASS}`);
    passed = true;
  } finally {
    const errors = restoreStack(); // always tries both; a failed body keeps its own error
    if (passed && errors.length) throw errors[0];
  }
});
