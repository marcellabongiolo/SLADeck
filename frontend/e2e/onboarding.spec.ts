import { test, expect } from "@playwright/test";

const user = { id: "user-1", email: "owner@example.com", full_name: "Demo Owner", created_at: "2026-01-01T00:00:00Z" };
const org = { id: "org-1", name: "Demo Team", slug: "demo-team", created_at: user.created_at };
const policy = { id: "policy-1", organization_id: org.id, name: "Standard support", first_response_minutes: 60, resolution_minutes: 480, created_at: user.created_at, updated_at: user.created_at };

test("new owner can register, create a workspace, set an SLA and create a request", async ({ page }) => {
  let registered = false;
  let organizations: typeof org[] = [];
  let policies: typeof policy[] = [];
  let requests: object[] = [];
  await page.route("http://localhost:8000/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const headers = { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" };
    if (request.method() === "OPTIONS") { await route.fulfill({ status: 204, headers }); return; }
    let body: unknown = {};
    let status = 200;
    if (path === "/auth/register") {
      expect(request.postDataJSON()).toEqual({ email: user.email, password: "StrongPassword123!", full_name: user.full_name });
      registered = true; body = user; status = 201;
    } else if (path === "/auth/login") {
      expect(registered).toBe(true);
      body = { access_token: "test-access", refresh_token: "test-refresh", token_type: "bearer", expires_in: 900 };
    } else {
      expect(request.headers()["authorization"]).toBe("Bearer test-access");
      if (path === "/auth/me") body = user;
      else if (path === "/organizations" && request.method() === "POST") {
        expect(request.postDataJSON()).toEqual({ name: org.name, slug: org.slug });
        organizations = [org]; body = org; status = 201;
      } else if (path === "/organizations") body = organizations;
      else if (path.endsWith("/sla-policies") && request.method() === "POST") {
        expect(request.postDataJSON()).toEqual({ name: policy.name, first_response_minutes: 60, resolution_minutes: 480 });
        policies = [policy]; body = policy; status = 201;
      } else if (path.endsWith("/sla-policies")) body = policies;
      else if (path.endsWith("/requests") && request.method() === "POST") {
        const payload = request.postDataJSON();
        expect(payload.sla_policy_id).toBe(policy.id);
        body = { id: "request-1", ...payload, status: "open", sla_state: "healthy" };
        requests = [body as object]; status = 201;
      } else if (path.endsWith("/requests")) body = requests;
      else if (path.endsWith("/notifications")) body = [];
      else if (path.endsWith("/analytics")) body = { open_requests: 0, healthy_requests: 0, warning_requests: 0, breached_requests: 0, breach_rate_pct: 0 };
      else throw new Error("Unexpected API path: " + path);
    }
    await route.fulfill({ status, headers, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.goto("/");
  await page.getByRole("link", { name: "Create account" }).click();
  await page.getByLabel("Full name").fill(user.full_name);
  await page.getByLabel("Email", { exact: true }).fill(user.email);
  await page.getByLabel("Password", { exact: true }).fill("StrongPassword123!");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.getByRole("button", { name: "Create workspace", exact: true }).click();
  await page.getByPlaceholder("Workspace name").fill(org.name);
  await page.getByPlaceholder("slug e.g. acme-support").fill(org.slug);
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Create your first SLA policy" })).toBeVisible();
  await expect(page.getByRole("button", { name: "+ New request", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Create SLA policy", exact: true }).click();
  await expect(page.getByRole("button", { name: "+ New request", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "+ New request", exact: true }).click();
  await page.getByPlaceholder("Title", { exact: true }).fill("First support request");
  await page.getByRole("button", { name: "Create request", exact: true }).click();
  await expect(page.getByText("First support request", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
});

test("unauthenticated workspace redirects to a working login page", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeVisible();
});

test("failed login shows API feedback and permits another attempt", async ({ page }) => {
  await page.route("http://localhost:8000/**", async route => {
    const headers = { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" };
    if (route.request().method() === "OPTIONS") { await route.fulfill({ status: 204, headers }); return; }
    await route.fulfill({ status: 401, headers, contentType: "application/json", body: JSON.stringify({ detail: "Invalid email or password" }) });
  });
  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill(user.email);
  await page.getByLabel("Password", { exact: true }).fill("wrong-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText("Invalid email or password");
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeEnabled();
});
