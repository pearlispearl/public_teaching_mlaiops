import http from 'k6/http';
import { check } from 'k6';

export const options = {
  vus: Number(__ENV.VUS || 10),
  duration: __ENV.DURATION || '60s',
  summaryTrendStats: ['avg', 'med', 'p(95)', 'p(99)', 'max'],
};

console.log(`Target URL: ${__ENV.URL}`);

const payload = JSON.stringify({
  temp_c: 75.0, vibration_mm_s: 12.5, pressure_kpa: 250.0,
  hours_since_service: 120.0, load_pct: 65.0, ambient_humidity: 45.0,
});
const params = {
  headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${__ENV.TOKEN}` },
};

export default function () {
  const res = http.post(__ENV.URL, payload, params);
  check(res, { 'status 200': (r) => r.status === 200 });
}
