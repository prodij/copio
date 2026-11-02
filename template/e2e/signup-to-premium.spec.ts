import { expect, test, type Page } from "@playwright/test";

// Milestone 1's definition of done (spec §1): sign up through Zitadel, create a workspace, save
// Stripe's test card on Stripe's hosted page, and see premium_report switch on because Lago's
// invoice-paid webhook said so, never because the browser came back from Stripe.
// Everything up to the plans page works without Stripe, so it has its own test; the payment test
// needs a key and is skipped without one. `make e2e` sets STRIPE_CONFIGURED (never the key itself).
//
// Two blocks of selectors belong to pages we do not own. If one fails, fix it here only:
// - signUp(): Zitadel login UI ghcr.io/zitadel/zitadel-login:v4.20.0 (labels checked 2026-11-01).
// - saveTestCard(): Stripe Checkout, hosted, setup mode (input ids as of 2026-11-01).

const PASSWORD = "Correct-horse-battery-9";
const WORKSPACE = "E2E Co";
const STRIPE_CONFIGURED = !!process.env.STRIPE_CONFIGURED;
const NOT_SET_UP = /billing isn't set up/i;

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

async function signUpToPlans(page: Page, app: string) {
  await page.goto("/");
  await page.getByRole("button", { name: "Sign in" }).click();
  await signUp(page, `e2e+${Date.now()}@example.com`);

  await page.waitForURL(`${app}/workspace/new`);
  await page.getByLabel("Workspace name").fill(WORKSPACE);
  await page.getByRole("button", { name: "Create workspace" }).click();
  await page.waitForURL(`${app}/plans`);
}

test("sign up → workspace → plans", async ({ page, baseURL }) => {
  await signUpToPlans(page, new URL(baseURL!).origin);
  const choose = page.getByRole("button", { name: "Choose Starter" });
  await expect(choose).toBeVisible();
  if (STRIPE_CONFIGURED) return;

  // No key: the app says billing isn't set up, right away, and access stays denied.
  await choose.click();
  await expect(page.getByRole("alert")).toContainText(NOT_SET_UP, { timeout: 5_000 });
  await page.goto("/billing");
  await expect(page.getByText(NOT_SET_UP)).toBeVisible();
  await page.goto("/premium");
  await expect(page.getByRole("alert")).toContainText("402");
});

test("sign up → workspace → pay → premium report", async ({ page, baseURL }) => {
  test.skip(!STRIPE_CONFIGURED, "STRIPE_SECRET_KEY is empty: add a Stripe test key to .env and run make bootstrap");
  const app = new URL(baseURL!).origin;
  await signUpToPlans(page, app);

  // Lago creates the Stripe customer in a background job; until then checkout answers 503 and
  // the page shows the error, so choosing the plan is retried until Stripe's page opens.
  await expect(async () => {
    await page.getByRole("button", { name: "Choose Starter" }).click();
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
