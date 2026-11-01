import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

test('first response failures display feedback to users', () => {
  const page = readFileSync('app/dashboard/requests/[id]/page.tsx', 'utf8');
  assert.ok(page.includes('await firstResponse(token,org,id)'));
  assert.ok(page.includes('setError(e instanceof Error?e.message:"Unable to mark first response.")'));
  assert.ok(page.includes('{error&&<p className="error">{error}</p>}'));
});
