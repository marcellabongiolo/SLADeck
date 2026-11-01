import { readFileSync } from "node:fs";
import { join } from "node:path";
import assert from "node:assert/strict";
import { test } from "node:test";

const root = process.cwd();

test("dashboard logout only clears SLADeck session keys", () => {
  const dashboard = readFileSync(join(root, "app/dashboard/page.tsx"), "utf8");
  const session = readFileSync(join(root, "lib/session.ts"), "utf8");

  assert.match(dashboard, /import\s*\{[^}]*clearSession[^}]*\}\s*from\s*["']\.\.\/\.\.\/lib\/session["']/);
  assert.match(dashboard, /onClick=\{\(\)=>\{clearSession\(\);location\.href=["']\/login["']/);
  assert.doesNotMatch(dashboard, /localStorage\.clear\s*\(/);
  assert.match(session, /localStorage\.removeItem\(ACCESS_TOKEN_KEY\)/);
  assert.match(session, /localStorage\.removeItem\(REFRESH_TOKEN_KEY\)/);
});
