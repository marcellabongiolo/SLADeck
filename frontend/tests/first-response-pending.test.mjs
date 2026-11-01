import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

test('first response action disables while pending and resets afterward', () => {
  const page = readFileSync('app/dashboard/requests/[id]/page.tsx', 'utf8');
  assert.ok(page.includes('disabled={markingResponse}'));
  assert.ok(page.includes('if(markingResponse)return'));
  assert.ok(page.includes('finally{setMarkingResponse(false)}'));
});
