<style>
  .trend-chart {
    position: relative;
    height: 13rem;
    margin-top: 1rem;
  }

  .trend-empty {
    min-height: 14.5rem;
    display: grid;
    align-content: center;
    justify-items: center;
    gap: 0.5rem;
    text-align: center;
    color: var(--habitat-muted);
  }

  .trend-summary {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.6rem;
    border-top: 1px solid var(--habitat-border);
    margin: 0.9rem 0 0;
    padding: 0.8rem 0 0;
  }

  .trend-summary dt {
    color: var(--habitat-muted);
    font-size: 0.8rem;
    font-weight: 500;
  }

  .trend-summary dd {
    margin: 0;
    font-size: 1rem;
    font-variant-numeric: tabular-nums;
  }

  @media (max-width: 420px) {
    .trend-summary {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
</style>

<script context="module">
  import { Chart as ChartJS, Filler, LineElement, LinearScale, PointElement, Tooltip } from 'chart.js';

  ChartJS.register(Filler, LineElement, LinearScale, PointElement, Tooltip);
</script>

<script>
  import { Line } from 'svelte-chartjs';
  import { _, date, number } from 'svelte-i18n';
  import { onDestroy } from 'svelte';
  import { fetchSensorTrend } from '../../providers/api';

  export let sensor = null;
  export let unit = '';
  export let now;

  const periods = { hour: '1h', day: '24h', week: '7d' };
  let period = 'day';
  let history;
  let loading = false;
  let failure = false;
  let controller;
  let chart;
  let lastLoadedAt = 0;

  const loadTrend = async (id, range, background = false) => {
    controller?.abort();
    controller = null;
    if (!background) {
      history = null;
      failure = false;
      loading = Boolean(id);
    }
    if (!id) return;

    const request = new AbortController();
    controller = request;
    try {
      const result = await fetchSensorTrend(id, range, request.signal);
      if (
        !Array.isArray(result?.points) ||
        !Number.isFinite(result?.start) ||
        !Number.isFinite(result?.end) ||
        (result.points.length && !result.summary)
      )
        throw new Error('Invalid trend response');
      if (!request.signal.aborted) {
        history = result;
        lastLoadedAt = Date.now();
      }
    } catch {
      if (!request.signal.aborted) {
        failure = !background;
        lastLoadedAt = Date.now();
      }
    } finally {
      if (!request.signal.aborted) loading = false;
    }
  };

  $: sensorId = sensor?.id;
  $: sensorName = sensor?.name ?? '';
  $: loadTrend(sensorId, period);
  $: datedHistory = Array.isArray(history?.points);
  $: chart = datedHistory && {
    labels: [],
    datasets: [
      {
        label: sensorName,
        data: history.points.map((point) => ({ x: point.timestamp * 1000, y: point.value })),
        borderColor: '#69ddad',
        backgroundColor: 'rgba(74, 207, 152, 0.12)',
        borderWidth: 2,
        pointRadius: history.points.length === 1 ? 4 : 0,
        pointHoverRadius: 4,
        fill: 'origin',
        tension: 0,
        spanGaps: Math.max(5 * 60 * 1000, ((history.end - history.start) * 1000) / 50),
      },
    ],
  };

  $: options = {
    animation: false,
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'nearest', intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          title: ([item]) =>
            $date(item.parsed.x, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }),
          label: (item) => `${$number(item.parsed.y, { maximumFractionDigits: 2 })} ${unit}`,
        },
      },
    },
    scales: {
      x: {
        type: 'linear',
        min: history?.start * 1000,
        max: history?.end * 1000,
        border: { display: false },
        grid: { display: false },
        ticks: {
          color: '#9bb6ac',
          maxTicksLimit: 5,
          callback: (value) =>
            $date(value, period === 'week' ? { weekday: 'short' } : { hour: 'numeric', minute: '2-digit' }),
        },
      },
      y: {
        border: { display: false },
        grid: { color: 'rgba(159, 189, 176, 0.15)' },
        ticks: { color: '#9bb6ac', maxTicksLimit: 5 },
      },
    },
  };

  $: if (history && now - lastLoadedAt >= 5 * 60 * 1000) loadTrend(sensorId, period, true);

  onDestroy(() => controller?.abort());
</script>

<section class="habitat-panel trend-panel" aria-labelledby="sensor-trend-title">
  <div class="habitat-panel-heading">
    <div>
      <h2 id="sensor-trend-title">{$_('habitat.trend.title')}</h2>
      {#if sensor}
        <p>{sensor.name}</p>
      {/if}
    </div>
    {#if sensor}
      <div class="habitat-segments" role="group" aria-label="{$_('habitat.trend.period')}">
        {#each Object.entries(periods) as [range, label]}
          <button
            type="button"
            aria-pressed="{period === range}"
            aria-label="{$_(`habitat.trend.${range}`)}"
            on:click="{() => (period = range)}">{label}</button
          >
        {/each}
      </div>
    {/if}
  </div>

  {#if loading}
    <div class="trend-empty" role="status">{$_('habitat.trend.loading')}</div>
  {:else if failure}
    <div class="trend-empty">
      <span role="status">{$_('habitat.trend.error')}</span>
      <button type="button" class="habitat-link" on:click="{() => loadTrend(sensor.id, period)}">
        {$_('habitat.retry')}
      </button>
    </div>
  {:else if !sensor || !datedHistory || !history.points.length}
    <div class="trend-empty">{$_(sensor ? 'habitat.trend.empty' : 'habitat.trend.select')}</div>
  {:else}
    <div class="trend-chart" role="img" aria-label="{$_('habitat.trend.chart', { values: { name: sensor.name } })}">
      <Line data="{chart}" {options} />
    </div>
    <dl class="trend-summary">
      {#each Object.entries(history.summary) as [metric, value]}
        <div>
          <dt>{$_(`habitat.trend.${metric}`)}</dt>
          <dd>{$number(value, { maximumFractionDigits: 2 })}{metric !== 'count' && unit ? ` ${unit}` : ''}</dd>
        </div>
      {/each}
    </dl>
  {/if}
</section>
