<script>
  import { onDestroy, onMount } from 'svelte';
  import { _, date, number } from 'svelte-i18n';
  import { getCustomConfig } from '../config';
  import { fetchEnclosures, fetchSensors } from '../providers/api';
  import { websocket } from '../providers/websocket';
  import { currency } from '../locale/i18n';
  import { customPageTitleUsed, setCustomPageTitle } from '../stores/page-title';
  import { template_sensor_type_icon } from '../helpers/icon-helpers';
  import { uptime_format } from '../helpers/number-helpers';
  import {
    buttons,
    currentPower,
    currentWater,
    isDay,
    isOnline,
    lastUpdate,
    maxPower,
    maxWater,
    resourceStatsReceived,
    sensors,
    systemLoad,
    systemStatsReceived,
    totalPower,
    totalPowerCosts,
    totalWater,
    totalWaterCosts,
    uptime,
  } from '../stores/terrariumpi';
  import {
    dashboardSensors,
    enclosureDoorStatus,
    filterSensors,
    readSensorPins,
    saveSensorPins,
    sensorUnit,
  } from '../helpers/dashboard-sensors';
  import Enclosure from '../components/enclosure/Enclosure.svelte';
  import SensorTrend from '../components/dashboard/SensorTrend.svelte';
  import Graph from '../components/common/Graph.svelte';

  const settings = getCustomConfig();
  const showEnclosures = settings.dashboard_mode !== 1;
  const enclosureFirst = settings.dashboard_mode === 2;
  const filters = ['all', 'attention', 'pinned'];
  const statusIcons = {
    normal: 'fa-circle-check',
    alarm: 'fa-triangle-exclamation',
    stale: 'fa-clock',
    invalid: 'fa-circle-exclamation',
    missing: 'fa-circle-minus',
  };
  const doorIcons = {
    open: 'fa-door-open',
    closed: 'fa-door-closed',
    unknown: 'fa-circle-question',
    unmonitored: 'fa-minus',
  };

  let inventory = [];
  let enclosures = [];
  let snapshotAt = 0;
  let enclosuresSnapshotAt = 0;
  let averageType;
  let showAverages = false;
  let now = Date.now();
  let pins = readSensorPins();
  let selectedId;
  let filter = 'all';
  let query = '';
  let active = false;
  let sensorPending = false;
  let sensorError = false;
  let enclosurePending = false;
  let enclosureError = false;
  let enclosuresLoaded = false;
  let previousPower;
  let powerRefresh;
  let monitoring;

  $: readings = dashboardSensors(inventory, $sensors, now, snapshotAt);
  $: visibleSensors = filterSensors(readings, query, filter, pins);
  $: sortedSensors = filterSensors(readings, '', 'all', pins);
  $: selectedSensor = sortedSensors.find((sensor) => sensor.id === selectedId) ?? sortedSensors[0] ?? null;
  $: monitoredEnclosures = enclosures.map((enclosure) => ({
    ...enclosure,
    doorStatus: enclosureDoorStatus(enclosure, $buttons, enclosuresSnapshotAt),
  }));
  $: attentionSensors = readings.filter((sensor) => sensor.status !== 'normal');
  $: doorAlerts = monitoredEnclosures.filter((enclosure) => ['open', 'unknown'].includes(enclosure.doorStatus));
  $: attentionCount = attentionSensors.length + doorAlerts.length;
  let averages = new Map();
  $: setCustomPageTitle($_('habitat.title'));
  onDestroy(() => customPageTitleUsed.set(false));
  $: {
    const groups = new Map();
    for (const sensor of readings) {
      if (sensor.exclude_avg || !['normal', 'alarm'].includes(sensor.status)) continue;
      const group = groups.get(sensor.type) ?? { total: 0, count: 0 };
      group.total += sensor.value;
      group.count += 1;
      groups.set(sensor.type, group);
    }
    averages = groups;
  }
  $: activeAverage = averages.has(averageType) ? averageType : [...averages.keys()][0];
  $: connection = $isOnline.status === true ? 'live' : $isOnline.status === false ? 'offline' : 'connecting';

  const refreshSensors = async () => {
    if (sensorPending) return;
    sensorPending = true;
    const requestedAt = Date.now();
    try {
      await fetchSensors(false, (data) => {
        if (!Array.isArray(data)) throw new Error('Invalid sensor inventory');
        if (active) {
          inventory = data;
          snapshotAt = requestedAt;
          sensorError = false;
        }
      });
    } catch {
      if (active) sensorError = true;
    } finally {
      sensorPending = false;
    }
  };

  const refreshEnclosures = async () => {
    if (!showEnclosures || enclosurePending) return;
    enclosurePending = true;
    const requestedAt = Date.now();
    try {
      await fetchEnclosures(false, (data) => {
        if (active) {
          enclosures = [...data].sort((a, b) => a.name.localeCompare(b.name));
          enclosuresLoaded = true;
          enclosuresSnapshotAt = requestedAt;
          enclosureError = false;
        }
      });
    } catch {
      if (active) enclosureError = true;
    } finally {
      enclosurePending = false;
    }
  };

  const togglePin = (id) => {
    // Keep the current trend selected when the card order changes.
    selectedId = selectedSensor?.id;
    pins = pins.includes(id) ? pins.filter((pin) => pin !== id) : [...pins, id];
    saveSensorPins(pins);
  };

  const selectAttentionSensor = (id) => {
    selectedId = id;
    filter = 'attention';
    query = '';
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    monitoring?.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'start' });
    monitoring?.focus({ preventScroll: true });
  };

  const requestStats = () => {
    try {
      websocket.set({ type: 'load_dashboard' });
    } catch {
      // Periodic messages will populate the system metrics as the connection recovers.
    }
  };

  onMount(() => {
    active = true;
    refreshSensors();
    refreshEnclosures();
    const stopConnectionSync = isOnline.subscribe((state) => {
      if (state.status === true) requestStats();
    });
    const stopPowerSync = currentPower.subscribe((value) => {
      if (previousPower !== undefined && value !== previousPower && showEnclosures && !powerRefresh) {
        powerRefresh = setTimeout(() => {
          powerRefresh = null;
          refreshEnclosures();
        }, 1000);
      }
      previousPower = value;
    });
    const clock = setInterval(() => (now = Date.now()), 15_000);
    const sensorRefresh = setInterval(refreshSensors, 60_000);
    const enclosureRefresh = showEnclosures ? setInterval(refreshEnclosures, 30_000) : undefined;

    return () => {
      active = false;
      stopConnectionSync();
      stopPowerSync();
      clearTimeout(powerRefresh);
      clearInterval(clock);
      clearInterval(sensorRefresh);
      clearInterval(enclosureRefresh);
    };
  });
</script>

<main class="habitat-dashboard">
  <section class="habitat-hero" aria-labelledby="habitat-title">
    <div class="habitat-hero-content">
      <div class="habitat-hero-caption">
        <span class="habitat-live" data-status="{connection}">
          <span aria-hidden="true"></span>{$_(`habitat.connection.${connection}`)}
        </span>
        {#if $systemStatsReceived && connection === 'live'}
          <span
            ><i class="fa-solid {$isDay ? 'fa-sun' : 'fa-moon'}" aria-hidden="true"></i>
            {$_($isDay ? 'habitat.day' : 'habitat.night')}</span
          >
        {/if}
      </div>
      <h1 id="habitat-title">{$_('habitat.title')}</h1>
      <p>
        {#if settings.name && !['TerrariumPI', 'PaludariumPI'].includes(settings.name)}
          {settings.name} ·
        {/if}
        {$_('habitat.description')}
      </p>
      <div class="habitat-hero-links">
        {#if showEnclosures}
          <a class="habitat-primary" href="#/enclosures/">
            <i class="fa-solid fa-layer-group" aria-hidden="true"></i>{$_('habitat.manageEnclosures')}
          </a>
        {/if}
        <a class="habitat-secondary" href="#/webcams/">
          <i class="fa-solid fa-video" aria-hidden="true"></i>{$_('habitat.cameras')}
        </a>
      </div>
    </div>
    {#if $systemStatsReceived}
      <span class="habitat-last-update">
        <i class="fa-regular fa-clock" aria-hidden="true"></i>
        {$_('habitat.controllerUpdate', {
          values: { time: $date($lastUpdate, { hour: 'numeric', minute: '2-digit' }) },
        })}
      </span>
    {/if}
  </section>

  <section class="habitat-monitoring" bind:this="{monitoring}" tabindex="-1" aria-labelledby="habitat-sensors-title">
    <div class="habitat-section-heading">
      <div>
        <h2 id="habitat-sensors-title">{$_('habitat.sensors')}</h2>
        {#if snapshotAt}
          <p>{$_('habitat.sensorCount', { values: { count: readings.length } })}</p>
        {/if}
      </div>
      <div class="habitat-sensor-tools">
        <label class="habitat-search">
          <i class="fa-solid fa-magnifying-glass" aria-hidden="true"></i>
          <span class="sr-only">{$_('habitat.search')}</span>
          <input type="search" placeholder="{$_('habitat.search')}" bind:value="{query}" />
        </label>
        <div class="habitat-segments" role="group" aria-label="{$_('habitat.filters.title')}">
          {#each filters as option}
            <button type="button" aria-pressed="{filter === option}" on:click="{() => (filter = option)}">
              {$_(`habitat.filters.${option}`)}
            </button>
          {/each}
        </div>
      </div>
    </div>

    {#if sensorError}
      <div class="habitat-message">
        <span role="status">{$_(snapshotAt ? 'habitat.refreshError' : 'habitat.sensorError')}</span>
        <button type="button" class="habitat-link" disabled="{sensorPending}" on:click="{refreshSensors}">
          {$_('habitat.retry')}
        </button>
      </div>
    {/if}
    {#if !snapshotAt && !sensorError}
      <div class="habitat-message" role="status">{$_('habitat.sensorLoading')}</div>
    {:else if snapshotAt && !readings.length}
      <div class="habitat-message">
        {$_('habitat.sensorEmpty')} <a class="habitat-link" href="#/sensors/all/">{$_('habitat.sensorSettings')}</a>
      </div>
    {:else if readings.length && !visibleSensors.length}
      <div class="habitat-message">
        {$_('habitat.noResults')}
        <button
          type="button"
          class="habitat-link"
          on:click="{() => {
            query = '';
            filter = 'all';
          }}"
        >
          {$_('habitat.clearFilters')}
        </button>
      </div>
    {:else if visibleSensors.length}
      <div class="habitat-sensor-grid">
        {#each visibleSensors as sensor (sensor.id)}
          <article
            class="habitat-sensor"
            class:selected="{selectedSensor?.id === sensor.id}"
            data-status="{sensor.status}"
          >
            <div class="habitat-sensor-top">
              <span class="habitat-icon" data-type="{sensor.type}">
                <i class="{template_sensor_type_icon(sensor.type) || 'fa-solid fa-wave-square'}" aria-hidden="true"></i>
              </span>
              <button
                type="button"
                class="habitat-pin"
                aria-label="{$_('habitat.pinSensor', { values: { name: sensor.name } })}"
                aria-pressed="{pins.includes(sensor.id)}"
                title="{$_(pins.includes(sensor.id) ? 'habitat.unpin' : 'habitat.pin')}"
                on:click="{() => togglePin(sensor.id)}"><i class="fa-solid fa-thumbtack" aria-hidden="true"></i></button
              >
            </div>
            <h3>
              <button
                type="button"
                aria-pressed="{selectedSensor?.id === sensor.id}"
                on:click="{() => (selectedId = sensor.id)}"
              >
                {sensor.name}
              </button>
            </h3>
            <div class="habitat-reading">
              {#if Number.isFinite(sensor.value) && sensor.status !== 'stale'}
                {$number(sensor.value, { maximumFractionDigits: 2 })}<span>{sensorUnit(sensor, settings.units)}</span>
              {:else}
                <span class="habitat-no-value" aria-hidden="true">—</span>
              {/if}
            </div>
            <div class="habitat-reading-status" data-status="{sensor.status}">
              <i class="fa-solid {statusIcons[sensor.status]}" aria-hidden="true"></i>
              {$_(`habitat.sensorStatus.${sensor.status}`)}
            </div>
          </article>
        {/each}
      </div>
    {/if}
  </section>

  <div class="habitat-insights">
    <SensorTrend
      sensor="{selectedSensor}"
      unit="{selectedSensor ? sensorUnit(selectedSensor, settings.units) : ''}"
      {now}
    />

    <section class="habitat-panel" aria-labelledby="habitat-attention-title">
      <div class="habitat-panel-heading">
        <div>
          <h2 id="habitat-attention-title">{$_('habitat.attention.title')}</h2>
          <p>{$_('habitat.attention.description')}</p>
        </div>
        {#if attentionCount}
          <span class="habitat-counter">{$number(attentionCount)}</span>
        {/if}
      </div>
      {#if attentionCount}
        <ul class="habitat-attention-list">
          {#each attentionSensors as sensor (sensor.id)}
            <li>
              <button type="button" on:click="{() => selectAttentionSensor(sensor.id)}">
                <i class="fa-solid {statusIcons[sensor.status]}" aria-hidden="true"></i>
                <span><strong>{sensor.name}</strong><small>{$_(`habitat.sensorStatus.${sensor.status}`)}</small></span>
                <i class="fa-solid fa-chevron-right" aria-hidden="true"></i>
              </button>
            </li>
          {/each}
          {#each doorAlerts as enclosure (enclosure.id)}
            <li>
              <a href="#/enclosures/">
                <i class="fa-solid {doorIcons[enclosure.doorStatus]}" aria-hidden="true"></i>
                <span><strong>{enclosure.name}</strong><small>{$_(`habitat.door.${enclosure.doorStatus}`)}</small></span
                >
                <i class="fa-solid fa-chevron-right" aria-hidden="true"></i>
              </a>
            </li>
          {/each}
        </ul>
      {:else}
        <div class="habitat-attention-empty">
          {#if !snapshotAt || sensorError || connection !== 'live' || (showEnclosures && (!enclosuresLoaded || enclosureError))}
            <span class="habitat-icon"><i class="fa-solid fa-circle-info" aria-hidden="true"></i></span>
            <p>{$_('habitat.attention.pending')}</p>
          {:else if readings.length || monitoredEnclosures.some((enclosure) => enclosure.doorStatus === 'closed')}
            <span class="habitat-icon"><i class="fa-solid fa-shield-heart" aria-hidden="true"></i></span>
            <p>{$_('habitat.attention.clear')}</p>
          {:else}
            <p>{$_('habitat.attention.empty')}</p>
          {/if}
        </div>
      {/if}
    </section>
  </div>

  {#if showEnclosures}
    <section
      class="habitat-panel habitat-enclosures"
      class:enclosure-first="{enclosureFirst}"
      aria-labelledby="habitat-enclosures-title"
    >
      <div class="habitat-panel-heading">
        <h2 id="habitat-enclosures-title">{$_('habitat.manageEnclosures')}</h2>
        <a href="#/enclosures/" class="habitat-link">{$_('habitat.manage')}</a>
      </div>
      {#if enclosureError}
        <div class="habitat-message">
          <span role="status">{$_('habitat.enclosureError')}</span>
          <button type="button" class="habitat-link" disabled="{enclosurePending}" on:click="{refreshEnclosures}">
            {$_('habitat.retry')}
          </button>
        </div>
      {:else if !enclosuresLoaded}
        <div class="habitat-message" role="status">{$_('habitat.enclosureLoading')}</div>
      {:else if !monitoredEnclosures.length}
        <div class="habitat-message">{$_('habitat.enclosureEmpty')}</div>
      {/if}
      {#each monitoredEnclosures as enclosure (enclosure.id)}
        <details open="{enclosureFirst}">
          <summary>
            <span>{enclosure.name}</span>
            <small data-status="{enclosure.doorStatus}">
              <i class="fa-solid {doorIcons[enclosure.doorStatus]}" aria-hidden="true"></i>
              {$_(`habitat.door.${enclosure.doorStatus}`)}
            </small>
          </summary>
          <div class="habitat-enclosure-body"><Enclosure {enclosure} /></div>
        </details>
      {/each}
    </section>
  {/if}

  {#if !enclosureFirst && averages.size}
    <details class="habitat-panel habitat-averages" on:toggle="{(event) => (showAverages = event.currentTarget.open)}">
      <summary>{$_('habitat.averages')}</summary>
      {#if showAverages}
        <div class="habitat-segments" role="group" aria-label="{$_('habitat.averages')}">
          {#each [...averages] as [type, group] (type)}
            <button type="button" aria-pressed="{activeAverage === type}" on:click="{() => (averageType = type)}">
              {$_(`sensors.average.${type}`, { default: type })} ·
              {$number(group.total / group.count, { maximumFractionDigits: 2 })}
              {sensorUnit({ type }, settings.units)}
            </button>
          {/each}
        </div>
        {#key activeAverage}
          <div class="habitat-average-graph">
            <Graph id="{activeAverage}" type="{activeAverage}" mode="sensors" />
          </div>
        {/key}
      {/if}
    </details>
  {/if}

  <section class="habitat-panel" aria-labelledby="habitat-resources-title">
    <div class="habitat-panel-heading">
      <h2 id="habitat-resources-title">{$_('habitat.resources.title')}</h2>
      <a href="#/system/status/" class="habitat-link">{$_('habitat.resources.system')}</a>
    </div>
    <dl class="habitat-resources">
      <div>
        <dt>{$_('habitat.resources.power')}</dt>
        <dd>{$resourceStatsReceived ? `${$number($currentPower)} / ${$number($maxPower)} W` : '—'}</dd>
      </div>
      <div>
        <dt>{$_('habitat.resources.flow')}</dt>
        <dd>
          {$resourceStatsReceived
            ? `${$number($currentWater)} / ${$number($maxWater)} ${settings.units.water_flow.value}`
            : '—'}
        </dd>
      </div>
      <div>
        <dt>{$_('habitat.resources.energy')}</dt>
        <dd>{$resourceStatsReceived ? `${$number($totalPower)} ${settings.units.powerusage.value}` : '—'}</dd>
        {#if $resourceStatsReceived}<small
            >{$number($totalPowerCosts, { style: 'currency', currency: $currency })}</small
          >{/if}
      </div>
      <div>
        <dt>{$_('habitat.resources.water')}</dt>
        <dd>{$resourceStatsReceived ? `${$number($totalWater)} ${settings.units.water_volume.value}` : '—'}</dd>
        {#if $resourceStatsReceived}<small
            >{$number($totalWaterCosts, { style: 'currency', currency: $currency })}</small
          >{/if}
      </div>
      <div>
        <dt>{$_('habitat.resources.uptime')}</dt>
        <dd>{$systemStatsReceived ? uptime_format($uptime) : '—'}</dd>
        {#if $systemStatsReceived}<small>{$_('habitat.resources.load', { values: { load: $systemLoad[0] } })}</small
          >{/if}
      </div>
    </dl>
  </section>
</main>
