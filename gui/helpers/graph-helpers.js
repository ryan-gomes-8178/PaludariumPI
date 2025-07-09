import { graphs } from '../stores/terrariumpi';
import { get } from 'svelte/store';
import { fetchExportData } from '../providers/api';

// https://stackoverflow.com/a/63348486
export const smoothing = (data, smoothingValue) => {
  if (smoothingValue == 0) {
    return data;
  }

  const countBefore = Math.round(smoothingValue / 2);
  const countAfter = smoothingValue - countBefore;
  const new_data = [];
  const max_items = data.length;

  for (let i = 0; i < max_items; i++) {
    // Remove spikes in alarm values
    if (i > 0 && i < max_items - 1) {
      if (data[i - 1].alarm_min == data[i + 1].alarm_min && data[i - 1].alarm_min !== data[i].alarm_min) {
        data[i].alarm_min = data[i - 1].alarm_min;
      }
      if (data[i - 1].alarm_max == data[i + 1].alarm_max && data[i - 1].alarm_max !== data[i].alarm_max) {
        data[i].alarm_max = data[i - 1].alarm_max;
      }
    }

    // Smoothing value
    const range = data.slice(Math.max(i - countBefore, 0), Math.min(i + countAfter + 1, max_items));
    const new_data_point = JSON.parse(JSON.stringify(data[i]));

    new_data_point.value =
      range.reduce((accumulator, point) => accumulator + (isNaN(point.value) ? 0 : point.value), 0) / range.length;
    new_data.push(new_data_point);
  }

  return new_data;
};

export const toggleGraphPeriod = (graph, period, customDates = null) => {
  period = period || 'day';

  const store = get(graphs);
  store[graph].period = period;

  if (period === 'custom' && customDates) {
    // Save custom start and end dates as ISO strings
    store[graph].customStart = customDates.start;
    store[graph].customEnd = customDates.end;
  } else {
    // Clear custom dates when not custom period
    store[graph].customStart = null;
    store[graph].customEnd = null;
  }
  
  store[graph].changed = true;
  graphs.set(store);
};

export const convertTimestamps = (data) => {
  return data.map((point) => {
    point.timestamp *= 1000;
    return point;
  });
};

export const extendGraphData = (data, period) => {
  const now = new Date();

  const start = JSON.parse(JSON.stringify(data[0]));
  const end = JSON.parse(JSON.stringify(data[data.length - 1]));

  end.timestamp = Math.round(now.getTime());

  now.setDate(now.getDate() - period);

  start.timestamp = Math.round(now.getTime());

  return [start, ...data, end];
};

export const exportGraphPeriod = async (type, graph) => {
  const store = get(graphs);
  const filename = `terrariumpi_export_${type}_${graph}_${store[graph].period}.csv`;

  let export_data = '';
  await fetchExportData(type, graph, store[graph].period, (data) => (export_data = data));

  const link = document.createElement('a');
  link.href = window.URL.createObjectURL(new Blob([export_data]));
  link.download = filename;
  link.click();
};
