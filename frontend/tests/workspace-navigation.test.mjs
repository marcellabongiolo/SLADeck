import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

test('dashboard restores a workspace only if it belongs to the user', () => {
  const page = readFileSync('app/dashboard/page.tsx', 'utf8');
  assert.ok(page.includes('new URLSearchParams(location.search).get("org")'));
  assert.ok(page.includes('o.find(workspace=>workspace.id===requestedOrg)?.id??o[0].id'));
});
