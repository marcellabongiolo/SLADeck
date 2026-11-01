import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

test('dashboard offers closed request filter', () => {
  const page = readFileSync('app/dashboard/page.tsx', 'utf8');
  assert.ok(page.includes('value="closed"'));
});
