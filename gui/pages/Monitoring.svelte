<style>
  .monitoring-stream-wrapper {
    position: relative;
    width: 100%;
    background: #000;
    border-radius: 0.25rem;
    overflow: hidden;
    aspect-ratio: 16/9;
  }

  .monitoring-stream {
    width: 100%;
    height: 100%;
    display: block;
    object-fit: contain;
  }

  .monitoring-overlay {
    position: absolute;
    inset: 0;
    pointer-events: none;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  .stat-card {
    background: #1a1a2e;
    border: 1px solid #16213e;
    border-radius: 0.5rem;
    padding: 1rem;
    text-align: center;
  }

  .stat-value {
    font-size: 1.5rem;
    font-weight: 600;
    color: #00d4ff;
    margin: 0.5rem 0;
  }

  .stat-label {
    font-size: 0.85rem;
    color: #a0a0a0;
    text-transform: uppercase;
  }

  .monitoring-zone-list {
    max-height: 320px;
    overflow: auto;
  }

  .monitoring-events {
    max-height: 420px;
    overflow: auto;
  }

  .snapshots-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 0.75rem;
    margin-top: 1rem;
  }

  .snapshot-card {
    position: relative;
    aspect-ratio: 16/9;
    border-radius: 0.25rem;
    overflow: hidden;
    cursor: pointer;
    border: 2px solid transparent;
    transition: border-color 0.2s;
  }

  .snapshot-card:hover {
    border-color: #00d4ff;
  }

  .snapshot-thumb {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .snapshot-overlay {
    position: absolute;
    inset: 0;
    background: linear-gradient(180deg, rgba(0, 0, 0, 0) 0%, rgba(0, 0, 0, 0.7) 100%);
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    padding: 6px;
    opacity: 1;
  }

  .snapshot-time {
    font-size: 0.75rem;
    color: #00d4ff;
    font-weight: 600;
    margin-bottom: 3px;
  }

  .snapshot-count {
    font-size: 0.7rem;
    color: #a0a0a0;
  }

  .date-filter-row {
    display: flex;
    gap: 1rem;
    align-items: center;
    margin-bottom: 1rem;
    flex-wrap: wrap;
  }

  .date-input-group {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }

  .date-input-group label {
    font-size: 0.85rem;
    color: #a0a0a0;
    margin: 0;
    white-space: nowrap;
  }

  .date-input-group input {
    padding: 0.4rem 0.6rem;
    background: #16213e;
    border: 1px solid #0f3460;
    border-radius: 0.25rem;
    color: #fff;
    font-size: 0.85rem;
  }

  .date-input-group input:focus {
    border-color: #00d4ff;
    outline: none;
    box-shadow: 0 0 0 2px rgba(0, 212, 255, 0.1);
  }

  .filter-buttons {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .filter-buttons button {
    padding: 0.4rem 0.8rem;
    font-size: 0.85rem;
    white-space: nowrap;
  }

  .pagination-controls {
    display: flex;
    gap: 0.5rem;
    margin-top: 1rem;
    justify-content: center;
    align-items: center;
    flex-wrap: wrap;
  }

  .pagination-controls button {
    padding: 0.5rem 0.75rem;
    font-size: 0.85rem;
  }

  .pagination-info {
    font-size: 0.85rem;
    color: #a0a0a0;
  }

  .activity-range-row {
    display: flex;
    gap: 1rem;
    align-items: center;
    margin-bottom: 1rem;
    flex-wrap: wrap;
  }

  .y-axis-label {
    position: absolute;
    left: -52px;
    top: 50%;
    transform: translateY(-50%) rotate(-90deg);
    font-size: 0.7rem;
    color: #666;
    white-space: nowrap;
    text-align: center;
    width: 110px;
  }

  .chart-legend {
    display: flex;
    gap: 1rem;
    margin-top: 0.75rem;
    font-size: 0.8rem;
    color: #a0a0a0;
    flex-wrap: wrap;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .legend-color {
    width: 12px;
    height: 12px;
    background: #00d4ff;
    border-radius: 0.15rem;
  }

  .hourly-stats {
    margin-top: 1rem;
    padding: 1rem;
    background: #16213e;
    border-radius: 0.25rem;
    position: relative;
    height: 150px;
  }

  .hourly-chart-container {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 0.2rem;
    height: 100px;
    position: relative;
    padding-right: 20px;
  }

  .hourly-y-axis {
    position: absolute;
    left: 0;
    top: 0;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    font-size: 0.65rem;
    color: #666;
    width: 40px;
    text-align: right;
    padding-right: 5px;
  }

  .hourly-bars {
    display: flex;
    align-items: flex-end;
    gap: 0.15rem;
    height: 100%;
    flex: 1;
    margin-left: 40px;
  }

  .bar {
    flex: 1;
    background: #00d4ff;
    border-radius: 0.15rem;
    opacity: 0.7;
    transition:
      opacity 0.2s,
      background 0.2s;
    position: relative;
    min-height: 2px;
  }

  .bar:hover {
    opacity: 1;
    background: #00ffff;
  }

  .hourly-x-axis {
    position: absolute;
    bottom: 0;
    left: 40px;
    right: 0;
    height: 20px;
    display: flex;
    justify-content: space-between;
    font-size: 0.65rem;
    color: #666;
  }

  .hour-label {
    flex: 1;
    text-align: center;
  }
</style>

<script>
  import { onMount, onDestroy } from 'svelte';
  import { PageHeader } from '@keenmate/svelte-adminlte';
  import { _ } from 'svelte-i18n';

  import { setCustomPageTitle, customPageTitleUsed } from '../stores/page-title';
  import { ApiUrl } from '../constants/urls';

  import hls from 'hls.js';

  let loading = false;
  let zones = [];
  let events = [];
  let snapshots = [];
  let summary = {};
  let activityBuckets = [];
  let systemStatus = '✅';
  let snapshotTotal = 0;

  let videoEl;
  let hlsPlayer;
  let refreshTimer;
  let currentPage = 0;
  let fromDate = '';
  let toDate = '';

  let activityFromDate = '';
  let activityFromTime = '00:00';
  let activityToDate = '';
  let activityToTime = '23:59';
  let activityBucketMinutes = 60;

  const snapshotsPerPage = 20;

  const nocturnalEyeApi = `${ApiUrl}/nocturnal-eye/api`;
  const streamUrl = `${ApiUrl}/nocturnal-eye/stream.m3u8`;

  const zoneColors = {
    feeding: '#4caf50',
    basking: '#ff9800',
    hide: '#3f51b5',
    general: '#00bcd4',
    default: '#f44336',
  };

  const getZoneColor = (zone) => {
    if (zone?.meta?.color) return zone.meta.color;
    if (zone?.color) {
      const match = String(zone.color).match(/\[(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\]/);
      if (match) {
        return `rgb(${match[1]}, ${match[2]}, ${match[3]})`;
      }
    }
    if (zone?.type && zoneColors[zone.type]) return zoneColors[zone.type];
    return zoneColors.default;
  };

  const mapSnapshotPath = (path) => {
    if (!path) return '';
    if (path.startsWith('http')) {
      try {
        const url = new URL(path);
        return `${ApiUrl}/nocturnal-eye${url.pathname}`;
      } catch (e) {
        return path;
      }
    }
    if (path.startsWith('/')) {
      return `${ApiUrl}/nocturnal-eye${path}`;
    }
    return path;
  };

  const formatTimeShort = (timestamp) => {
    if (!timestamp) return '';
    const date = typeof timestamp === 'number' ? new Date(timestamp * 1000) : new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const formatBucketLabel = (isoTimestamp) => {
    if (!isoTimestamp) return '';
    const date = new Date(isoTimestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const calculateBucketMinutes = (start, end) => {
    const totalMinutes = Math.max((end - start) / 60000, 1);
    const candidateBuckets = [15, 30, 60, 120, 180, 240, 360, 720];
    const targetBuckets = 12;

    for (const bucket of candidateBuckets) {
      if (totalMinutes / bucket <= targetBuckets) {
        return bucket;
      }
    }

    return 720;
  };

  const loadActivityHistogram = async () => {
    try {
      if (!activityFromDate || !activityToDate) return;

      const start = new Date(`${activityFromDate}T${activityFromTime}:00`);
      const end = new Date(`${activityToDate}T${activityToTime}:59`);
      if (end <= start) {
        window.alert('The end date and time must be after the start date and time.');
        return;
      }

      activityBucketMinutes = calculateBucketMinutes(start, end);

      const url = `${nocturnalEyeApi}/activity/histogram?start=${start.toISOString()}&end=${end.toISOString()}&bucket_minutes=${activityBucketMinutes}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        activityBuckets = data.buckets || [];
      }
    } catch (err) {
      console.error('Failed to load activity histogram:', err);
    }
  };

  const setupHls = () => {
    if (!videoEl) return;

    if (videoEl.canPlayType('application/vnd.apple.mpegurl')) {
      videoEl.src = streamUrl;
      return;
    }

    if (hls.isSupported()) {
      hlsPlayer = new hls({
        lowLatencyMode: true,
        backBufferLength: 30,
      });
      hlsPlayer.loadSource(streamUrl);
      hlsPlayer.attachMedia(videoEl);
    } else {
      videoEl.src = streamUrl;
    }
  };

  const loadData = async () => {
    try {
      loading = true;

      const summaryRes = await fetch(`${nocturnalEyeApi}/dashboard/summary`);
      if (summaryRes.ok) {
        summary = await summaryRes.json();
        zones = summary.zones || [];
        snapshotTotal = summary.snapshot_count || 0;
        if (summary.recent_snapshots?.length) {
          events = summary.recent_snapshots.map((snap) => ({
            label: 'Detection',
            timestamp: snap.timestamp,
            zone: null,
            confidence: null,
            count: snap.metadata?.detection_count || 0,
            path: mapSnapshotPath(snap.path),
          }));
        }
        systemStatus = '✅';
      } else {
        systemStatus = '❌';
      }

      await loadSnapshots();
      await loadActivityHistogram();
      await loadActivityHistogram();
    } catch (err) {
      console.error('Failed to load monitoring data:', err);
      systemStatus = '❌';
    } finally {
      loading = false;
    }
  };

  const loadSnapshots = async () => {
    try {
      const offset = currentPage * snapshotsPerPage;
      let url = `${nocturnalEyeApi}/snapshots/recent?limit=${snapshotsPerPage}&offset=${offset}`;

      if (fromDate) url += `&from=${fromDate}`;
      if (toDate) url += `&to=${toDate}`;

      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        snapshots = (data.snapshots || []).map((snap) => ({
          ...snap,
          path: mapSnapshotPath(snap.path),
        }));
        snapshotTotal = data.count || snapshotTotal;
      }
    } catch (err) {
      console.error('Failed to load snapshots:', err);
    }
  };

  const previousPage = () => {
    if (currentPage > 0) {
      currentPage--;
      loadSnapshots();
    }
  };

  const nextPage = () => {
    currentPage++;
    loadSnapshots();
  };

  const applyDateRange = () => {
    currentPage = 0;
    loadSnapshots();
  };

  const clearDateRange = () => {
    fromDate = '';
    toDate = '';
    currentPage = 0;
    loadSnapshots();
  };

  const formatDate = (timestamp) => {
    if (!timestamp) return '';
    const date = typeof timestamp === 'number' ? new Date(timestamp * 1000) : new Date(timestamp);
    return date.toLocaleString();
  };

  const maxHourlyCount = () => Math.max(...activityBuckets.map((bucket) => bucket.count || 0), 1);

  onMount(() => {
    setCustomPageTitle($_('monitoring.title', { default: 'Monitoring' }));

    // Initialize date inputs with today's date
    const today = new Date().toISOString().split('T')[0];
    toDate = today;
    fromDate = today;

    activityFromDate = today;
    activityToDate = today;
    activityFromTime = '00:00';
    activityToTime = '23:59';

    setupHls();
    loadData();

    refreshTimer = setInterval(() => {
      loadData();
    }, 10000);
  });

  onDestroy(() => {
    customPageTitleUsed.set(false);

    if (refreshTimer) {
      clearInterval(refreshTimer);
    }

    if (hlsPlayer) {
      hlsPlayer.destroy();
    }
  });
</script>

<PageHeader>
  {$_('monitoring.title', { default: 'Monitoring' })}
</PageHeader>

<div class="container-fluid">
  <!-- Stats Row -->
  <div class="row mb-4">
    <div class="col-12">
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">Today's Activity</div>
          <div class="stat-value">{summary?.daily_summary?.total_events || 0}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Total Snapshots</div>
          <div class="stat-value">{summary?.snapshot_count || 0}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Database Events</div>
          <div class="stat-value">{summary?.database_stats?.total_events || 0}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Status</div>
          <div class="stat-value">{systemStatus}</div>
        </div>
      </div>
    </div>
  </div>

  <!-- Main Content Row -->
  <div class="row">
    <!-- Left Column: Stream -->
    <div class="col-xl-8">
      <!-- Live Stream -->
      <div class="card mb-3">
        <div class="card-header">
          <h3 class="card-title">
            <i class="fas fa-video mr-2"></i>Live Stream
          </h3>
          <div class="card-tools">
            <button class="btn btn-sm btn-default mr-1" on:click="{() => window.location.reload()}">
              <i class="fas fa-sync-alt"></i> Refresh
            </button>
          </div>
        </div>
        <div class="card-body">
          <div class="monitoring-stream-wrapper">
            <video class="monitoring-stream" bind:this="{videoEl}" controls autoplay muted playsinline></video>
          </div>
        </div>
      </div>

      <!-- Snapshots -->
      {#if snapshots.length > 0}
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">
              <i class="fas fa-image mr-2"></i>Recent Detections
            </h3>
          </div>
          <div class="card-body">
            <!-- Date Range Filter -->
            <div class="date-filter-row">
              <div class="date-input-group">
                <label for="fromDate">From</label>
                <input type="date" id="fromDate" bind:value="{fromDate}" />
              </div>
              <div class="date-input-group">
                <label for="toDate">To</label>
                <input type="date" id="toDate" bind:value="{toDate}" />
              </div>
              <div class="filter-buttons">
                <button class="btn btn-sm btn-success" on:click="{applyDateRange}">
                  <i class="fas fa-check"></i> Apply Range
                </button>
                <button class="btn btn-sm btn-outline-secondary" on:click="{clearDateRange}">
                  <i class="fas fa-times"></i> Clear Range
                </button>
              </div>
            </div>

            <!-- Snapshots Grid -->
            <div class="snapshots-grid">
              {#each snapshots as snapshot}
                <div class="snapshot-card">
                  <img src="{snapshot.path}" alt="Snapshot" class="snapshot-thumb" />
                  <div class="snapshot-overlay">
                    <div class="snapshot-time">
                      {formatTimeShort(snapshot.timestamp)}
                    </div>
                    {#if snapshot.metadata?.detection_count}
                      <div class="snapshot-count">
                        {snapshot.metadata.detection_count} detection(s)
                      </div>
                    {/if}
                  </div>
                </div>
              {/each}
            </div>

            <!-- Pagination Info -->
            <div class="pagination-controls">
              <button class="btn btn-sm btn-outline-secondary" disabled="{currentPage === 0}" on:click="{previousPage}">
                <i class="fas fa-chevron-left"></i> Newer
              </button>
              <span class="pagination-info">
                {#if snapshotTotal > 0}
                  {currentPage * snapshotsPerPage + 1} - {Math.min((currentPage + 1) * snapshotsPerPage, snapshotTotal)}
                  of {snapshotTotal}
                {:else}
                  Page {currentPage + 1}
                {/if}
              </span>
              <button
                class="btn btn-sm btn-outline-secondary"
                disabled="{snapshotTotal !== 0 && (currentPage + 1) * snapshotsPerPage >= snapshotTotal}"
                on:click="{nextPage}"
              >
                Older <i class="fas fa-chevron-right"></i>
              </button>
            </div>
          </div>
        </div>
      {/if}
    </div>

    <!-- Right Column: Info Panels -->
    <div class="col-xl-4">
      <!-- Monitoring Zones -->
      <div class="card mb-3">
        <div class="card-header">
          <h3 class="card-title">
            <i class="fas fa-draw-polygon mr-2"></i>Zones ({zones.length})
          </h3>
        </div>
        <div class="card-body monitoring-zone-list">
          {#if zones.length === 0}
            <p class="text-muted text-center">No zones configured yet</p>
          {:else}
            <ul class="list-unstyled mb-0">
              {#each zones as zone}
                <li class="mb-3">
                  <div class="d-flex align-items-center mb-1">
                    <span class="badge mr-2" style="background:{getZoneColor(zone)}">&nbsp;</span>
                    <strong>{zone.name}</strong>
                  </div>
                  <small class="text-muted d-block ml-3">
                    {zone.type || 'general'}
                    {#if zone.enabled === false}
                      <span class="badge badge-secondary ml-1">disabled</span>
                    {/if}
                  </small>
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      </div>

      <!-- Recent Activity -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">
            <i class="fas fa-history mr-2"></i>Recent Activity ({events.length})
          </h3>
        </div>
        <div class="card-body monitoring-events">
          {#if events.length === 0}
            <p class="text-muted text-center">No detections yet</p>
          {:else}
            <div class="timeline">
              {#each events as event}
                <div class="mb-3 pb-3 border-bottom">
                  <div class="d-flex justify-content-between align-items-start mb-1">
                    <strong style="font-size: 0.95rem;">{event.label || 'Detection'}</strong>
                    <small class="text-muted">{formatDate(event.timestamp)}</small>
                  </div>
                  {#if event.count !== undefined}
                    <small class="text-muted d-block">
                      Detections: {event.count}
                    </small>
                  {/if}
                  {#if event.path}
                    <img
                      src="{event.path}"
                      alt="Detection"
                      style="width: 100%; border-radius: 0.25rem; margin-top: 6px;"
                    />
                  {/if}
                </div>
              {/each}
            </div>
          {/if}
        </div>
      </div>

      <!-- Hourly Stats -->
      {#if activityBuckets.length > 0}
        <div class="card mt-3">
          <div class="card-header">
            <h3 class="card-title">
              <i class="fas fa-chart-bar mr-2"></i>Hourly Activity (24h)
            </h3>
          </div>
          <div class="card-body">
            <div class="activity-range-row">
              <div class="date-input-group">
                <label for="activityFromDate">From</label>
                <input type="date" id="activityFromDate" bind:value="{activityFromDate}" />
              </div>
              <div class="date-input-group">
                <label for="activityFromTime">Time</label>
                <input type="time" id="activityFromTime" bind:value="{activityFromTime}" />
              </div>
              <div class="date-input-group">
                <label for="activityToDate">To</label>
                <input type="date" id="activityToDate" bind:value="{activityToDate}" />
              </div>
              <div class="date-input-group">
                <label for="activityToTime">Time</label>
                <input type="time" id="activityToTime" bind:value="{activityToTime}" />
              </div>
              <div class="filter-buttons">
                <button class="btn btn-sm btn-success" on:click="{loadActivityHistogram}">
                  <i class="fas fa-check"></i> Apply Range
                </button>
              </div>
            </div>
            <div class="hourly-stats">
              <div class="y-axis-label">Detections per Interval</div>
              <div class="hourly-y-axis">
                <div>{Math.round(maxHourlyCount())}</div>
                <div>{Math.round(maxHourlyCount() / 2)}</div>
                <div>0</div>
              </div>
              <div class="hourly-chart-container">
                <div class="hourly-bars">
                  {#each activityBuckets as bucket, idx}
                    <div
                      class="bar"
                      style="height: {Math.max(2, (bucket.count / maxHourlyCount()) * 100)}%"
                      title="{formatBucketLabel(bucket.start)} - {bucket.count} detections"
                    ></div>
                  {/each}
                </div>
              </div>
              <div class="hourly-x-axis">
                {@const labelStep = Math.max(Math.floor(activityBuckets.length / 6), 1)}
                {#each activityBuckets as bucket, idx}
                  {#if idx % labelStep === 0}
                    <div class="hour-label">{formatBucketLabel(bucket.start)}</div>
                  {:else}
                    <div class="hour-label"></div>
                  {/if}
                {/each}
              </div>
            </div>
            <div class="chart-legend">
              <div class="legend-item">
                <div class="legend-color"></div>
                <span>Detection Count (per interval)</span>
              </div>
              <div class="legend-item">
                <span style="font-size: 0.75rem; color: #666;">Interval: {activityBucketMinutes} min</span>
              </div>
            </div>
          </div>
        </div>
      {/if}
    </div>
  </div>
</div>
