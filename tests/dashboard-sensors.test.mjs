import assert from 'node:assert/strict';
import test from 'node:test';
import {
  dashboardSensors,
  enclosureDoorStatus,
  filterSensors,
  sensorStatus,
  SENSOR_MAX_AGE,
} from '../gui/helpers/dashboard-sensors.js';

const now = Date.UTC(2026, 0, 1, 12);
const sensor = {
  id: 'canopy',
  name: 'Canopy',
  type: 'temperature',
  value: 0,
  error: false,
  alarm_min: -1,
  alarm_max: 30,
  measured_at: now / 1000,
};

test('reports fresh zero readings and distinguishes stale, invalid and alarm readings', () => {
  assert.equal(sensorStatus(sensor, now), 'normal');
  assert.equal(sensorStatus(sensor, now + SENSOR_MAX_AGE), 'stale');
  assert.equal(sensorStatus({ ...sensor, value: 31 }, now), 'alarm');
  assert.equal(sensorStatus({ ...sensor, value: 31, error: true }, now), 'invalid');
  assert.equal(sensorStatus({ ...sensor, value: null, measured_at: null }, now), 'missing');
});

test('a delayed live reading cannot replace the inventory snapshot', () => {
  const live = { ...sensor, value: 20, last_update: new Date(now - 1000) };
  assert.equal(dashboardSensors([sensor], { canopy: live }, now, now)[0].value, 0);
  live.last_update = new Date(now + 1000);
  assert.equal(dashboardSensors([sensor], { canopy: live }, now, now)[0].value, 20);
});

test('search and attention filters work together and pinned sensors sort first', () => {
  const readings = [
    { ...sensor, status: 'normal' },
    { ...sensor, id: 'pool', name: 'Pool', status: 'alarm' },
  ];
  assert.deepEqual(filterSensors(readings, ' TEMPERATURE ', 'attention', []), [readings[1]]);
  assert.deepEqual(filterSensors(readings, '', 'all', ['pool']), [readings[1], readings[0]]);
});

test('door state honors inverse inputs and falls back to fresh REST data', () => {
  const enclosure = { doors: [{ id: 'door', hardware: 'remote', value: 0, calibration: { inverse: 'on' } }] };
  assert.equal(enclosureDoorStatus(enclosure, {}, now), 'closed');
  assert.equal(enclosureDoorStatus(enclosure, { door: { value: 1, last_update: new Date(now - 1) } }, now), 'closed');
  assert.equal(enclosureDoorStatus(enclosure, { door: { value: 1, last_update: new Date(now) } }, now), 'open');
  assert.equal(enclosureDoorStatus({ doors: [{ id: 'door', value: null }] }, {}, now), 'unknown');
});
