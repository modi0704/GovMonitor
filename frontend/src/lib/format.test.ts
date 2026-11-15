import { afterEach } from 'vitest';
import { dateTime, setDisplayTimeZone } from './format';

afterEach(() => setDisplayTimeZone(undefined));

it('shows times in the agency time zone, not the computer’s', () => {
  setDisplayTimeZone('Asia/Manila');
  // 15:59:59 UTC is 11:59 PM in Manila: the end of the cutoff day there.
  expect(dateTime('2026-04-10T15:59:59Z')).toMatch(/Apr 10, 2026.*11:59/);
  setDisplayTimeZone('UTC');
  expect(dateTime('2026-04-10T15:59:59Z')).toMatch(/3:59/);
  expect(dateTime(null)).toBe('—');
});
