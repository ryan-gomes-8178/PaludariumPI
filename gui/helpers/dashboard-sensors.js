export const SENSOR_MAX_AGE = 5 * 60 * 1000;
const PIN_STORAGE_KEY = 'paludariumpi.dashboard.pinned-sensors';

export const sensorStatus = (sensor, now) => {
  if (sensor.measured_at !== undefined) {
    if (sensor.measured_at === null) return 'missing';
    if (now - sensor.measured_at * 1000 >= SENSOR_MAX_AGE) return 'stale';
  } else if (sensor.last_update && now - sensor.last_update >= SENSOR_MAX_AGE) {
    return 'stale';
  }

  if (!Number.isFinite(sensor.value)) return 'missing';
  if (sensor.error) return 'invalid';

  if (
    sensor.alarm ||
    (Number.isFinite(sensor.alarm_min) && sensor.value < sensor.alarm_min) ||
    (Number.isFinite(sensor.alarm_max) && sensor.value > sensor.alarm_max)
  ) {
    return 'alarm';
  }

  return 'normal';
};

export const dashboardSensors = (inventory, live, now, snapshotAt) =>
  inventory.map((sensor) => {
    const update = Object.hasOwn(live, sensor.id) ? live[sensor.id] : undefined;
    // Prefer a live measurement recorded as recently as the snapshot. Older API versions
    // omit measurement timestamps, so use the time when the live message was received.
    const useLive =
      update &&
      (sensor.measured_at !== undefined
        ? Number.isFinite(update.measured_at) &&
          (update.measured_at > (sensor.measured_at ?? -Infinity) ||
            (update.measured_at === sensor.measured_at && update.last_update >= snapshotAt))
        : update.last_update >= snapshotAt);
    const reading = useLive
      ? {
          ...sensor,
          value: update.value,
          error: update.error,
          alarm: undefined,
          measured_at: update.measured_at,
          last_update: update.last_update,
        }
      : sensor;
    return { ...reading, status: sensorStatus(reading, now) };
  });

export const filterSensors = (sensors, query, filter, pins) => {
  const term = query.trim().toLocaleLowerCase();
  const pinned = new Set(pins);
  return sensors
    .filter((sensor) => {
      if (filter === 'pinned' && !pinned.has(sensor.id)) return false;
      if (filter === 'attention' && sensor.status === 'normal') return false;
      return !term || `${sensor.name} ${sensor.type}`.toLocaleLowerCase().includes(term);
    })
    .sort((a, b) => Number(pinned.has(b.id)) - Number(pinned.has(a.id)) || a.name.localeCompare(b.name));
};

export const readSensorPins = () => {
  try {
    const value = JSON.parse(window.localStorage.getItem(PIN_STORAGE_KEY));
    return Array.isArray(value) ? value.filter((id) => typeof id === 'string') : [];
  } catch {
    return [];
  }
};

export const saveSensorPins = (pins) => {
  try {
    window.localStorage.setItem(PIN_STORAGE_KEY, JSON.stringify(pins));
  } catch {
    // Pins still work for the current page when browser storage is unavailable.
  }
};

export const sensorUnit = (sensor, units) => {
  const unit = units[sensor.type]?.value ?? '';
  return sensor.type === 'temperature' && /^[CF]$/.test(unit) ? `°${unit}` : unit;
};

export const enclosureDoorStatus = (enclosure, liveButtons, snapshotAt) => {
  if (!enclosure.doors.length) return 'unmonitored';
  const known = enclosure.doors.map((door) => {
    const live = Object.hasOwn(liveButtons, door.id) ? liveButtons[door.id] : undefined;
    const current = live?.last_update >= snapshotAt ? live : door;
    if (current.value !== 0 && current.value !== 1) return null;
    const inverse = door.hardware === 'remote' && door.calibration?.inverse === 'on';
    return current.value === (inverse ? 0 : 1);
  });
  if (known.includes(false)) return 'open';
  return known.every(Boolean) ? 'closed' : 'unknown';
};
