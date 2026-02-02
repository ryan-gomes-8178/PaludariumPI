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
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 0.75rem;
    margin-top: 1rem;
  }

  .snapshot-thumb {
    width: 100%;
    aspect-ratio: 16/9;
    object-fit: cover;
    border-radius: 0.25rem;
    cursor: pointer;
    border: 2px solid transparent;
    transition: border-color 0.2s;
  }

  .snapshot-thumb:hover {
    border-color: #00d4ff;
  }

  .pagination-controls {
    display: flex;
    gap: 0.5rem;
    margin-top: 1rem;
    justify-content: center;
  }

  .pagination-controls button {
    padding: 0.5rem 0.75rem;
    font-size: 0.85rem;
  }

  .hourly-stats {
    margin-top: 1rem;
    padding: 1rem;
    background: #16213e;
    border-radius: 0.25rem;
  }

  .hourly-bar {
    display: flex;
    align-items: flex-end;
    gap: 0.25rem;
    height: 100px;
    margin-top: 0.5rem;
  }

  .bar {
    flex: 1;
    background: #00d4ff;
    border-radius: 0.15rem;
    opacity: 0.8;
    transition: opacity 0.2s;
  }

  .bar:hover {
    opacity: 1;
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
  let hourlyStats = [];
  let systemStatus = '✅';
  let snapshotTotal = 0;

  let videoEl;
  let hlsPlayer;
  let refreshTimer;
  let currentPage = 0;
  const snapshotsPerPage = 12;

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
        hourlyStats = summary.hourly_distribution
          ? Object.entries(summary.hourly_distribution).map(([hour, count]) => ({ hour, count }))
          : [];
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
      const res = await fetch(
        `${nocturnalEyeApi}/snapshots/recent?limit=${snapshotsPerPage}&offset=${offset}`
      );
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

  const formatDate = (timestamp) => {
    if (!timestamp) return '';
    const date = typeof timestamp === 'number' ? new Date(timestamp * 1000) : new Date(timestamp);
    return date.toLocaleString();
  };

  const maxHourlyCount = () => Math.max(...hourlyStats.map((stat) => stat.count || 0), 1);

  onMount(() => {
    setCustomPageTitle($_('monitoring.title', { default: 'Monitoring' }));
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
            <button class="btn btn-sm btn-default mr-1" on:click={() => window.location.reload()}>
              <i class="fas fa-sync-alt"></i> Refresh
            </button>
          </div>
        </div>
        <div class="card-body">
          <div class="monitoring-stream-wrapper">
            <video
              class="monitoring-stream"
              bind:this={videoEl}
              controls
              autoplay
              muted
              playsinline
            ></video>
          </div>
        </div>
      </div>

      <!-- Snapshots -->
      {#if snapshots.length > 0}
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">
              <i class="fas fa-image mr-2"></i>Recent Snapshots
            </h3>
          </div>
          <div class="card-body">
            <div class="snapshots-grid">
              {#each snapshots as snapshot}
                <img
                  src={snapshot.path}
                  alt="Snapshot"
                  class="snapshot-thumb"
                  title={formatDate(snapshot.timestamp)}
                />
              {/each}
            </div>
            <div class="pagination-controls">
              <button
                class="btn btn-sm btn-outline-secondary"
                disabled={currentPage === 0}
                on:click={previousPage}
              >
                <i class="fas fa-chevron-left"></i> Previous
              </button>
              <span class="text-muted d-flex align-items-center mx-2">
                Page {currentPage + 1}
              </span>
              <button
                class="btn btn-sm btn-outline-secondary"
                disabled={snapshotTotal !== 0 && (currentPage + 1) * snapshotsPerPage >= snapshotTotal}
                on:click={nextPage}
              >
                Next <i class="fas fa-chevron-right"></i>
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
                      src={event.path}
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
      {#if hourlyStats.length > 0}
        <div class="card mt-3">
          <div class="card-header">
            <h3 class="card-title">
              <i class="fas fa-chart-bar mr-2"></i>Activity (Last 24h)
            </h3>
          </div>
          <div class="card-body">
            <div class="hourly-stats">
              <div class="hourly-bar">
                {#each hourlyStats as stat}
                  <div
                    class="bar"
                    style="height: {Math.min(100, (stat.count / maxHourlyCount()) * 100)}%"
                    title="{stat.hour}:00 - {stat.count} events"
                  ></div>
                {/each}
              </div>
            </div>
          </div>
        </div>
      {/if}
    </div>
  </div>
</div>
