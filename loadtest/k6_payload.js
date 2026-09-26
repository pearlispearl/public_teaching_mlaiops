import http from 'k6/http';
import { check } from 'k6';

const N = Number(__ENV.ROWS || 10);

export const options = { vus: 1, iterations: 20 };

console.log(`Target URL: ${__ENV.URL}`);
console.log(`Rows per request: ${N}`);

const row = {
  temp_c: 75.0, vibration_mm_s: 12.5, pressure_kpa: 250.0,
  hours_since_service: 120.0, load_pct: 65.0, ambient_humidity: 45.0,
};
const payload = JSON.stringify({ rows: Array(N).fill(row) });
const params = { headers: { 'Content-Type': 'application/json' } };

export default function () {
  const res = http.post(__ENV.URL, payload, params);
  check(res, { 'status 200': (r) => r.status === 200 });
}
