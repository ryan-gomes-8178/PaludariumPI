<style>
  button:hover {
    background: #70ffab !important;
    transform: translateY(-2px);
  }
</style>

<script>
  import { onMount, onDestroy } from 'svelte';
  import { PageHeader } from '@keenmate/svelte-adminlte';
  import { _ } from 'svelte-i18n';

  import { setCustomPageTitle, customPageTitleUsed } from '../stores/page-title';
  import { ApiUrl } from '../constants/urls';

  let todayActivity = '--';
  let snapshotCount = '--';
  let dbEvents = '--';
  let systemStatus = '✅';
  let snapshots = [];
  let zones = [];
  let hourlyData = [];

  let snapshotLimit = 12;
  let snapshotOffset = 0;
  let snapshotTotal = 0;
  let snapshotMode = 'recent';

  const nocturnalEyeApi = ApiUrl;

  async function loadDashboard() {
    try {
      const response = await fetch(`${nocturnalEyeApi}/dashboard/summary`);
      const data = await response.json();

      todayActivity = data.daily_summary.total_events || '--';
      snapshotCount = data.snapshot_count || '--';
      dbEvents = data.database_stats.total_events || '--';
      systemStatus = '✅';

      loadSnapshots(data.recent_snapshots);
      loadHourlyData(data.hourly_distribution);
      loadZones(data.zones);
    } catch (error) {
      console.error('Error loading dashboard:', error);
      systemStatus = '❌';
    }
  }

  async function loadSnapshotPage() {
    try {
      const response = await fetch(
        `${nocturnalEyeApi}/snapshots/recent?limit=${snapshotLimit}&offset=${snapshotOffset}`,
      );
      const data = await response.json();
      snapshotTotal = data.count || snapshotCount;
      loadSnapshots(data.snapshots || []);
    } catch (error) {
      console.error('Error loading snapshots:', error);
    }
  }

  function loadSnapshots(snaps) {
    snapshots = snaps.map((snap) => ({
      ...snap,
      timestamp: snap.timestamp ? new Date(snap.timestamp).toLocaleTimeString() : 'Unknown',
    }));
  }

  function loadHourlyData(hourly) {
    hourlyData = hourly ? Object.entries(hourly).map(([hour, count]) => ({ hour, count })) : [];
  }

  function loadZones(zonesData) {
    zones = zonesData || [];
  }

  function nextSnapshots() {
    if (snapshotOffset + snapshotLimit < snapshotTotal) {
      snapshotOffset += snapshotLimit;
      loadSnapshotPage();
    }
  }

  function prevSnapshots() {
    snapshotOffset = Math.max(0, snapshotOffset - snapshotLimit);
    loadSnapshotPage();
  }

  onMount(() => {
    setCustomPageTitle('Nocturnal Eye Monitoring');
    loadDashboard();
    const interval = setInterval(loadDashboard, 30000);
    return () => clearInterval(interval);
  });

  onDestroy(() => {
    customPageTitleUsed.set(false);
  });
</script>

<PageHeader />

<div
  style="background: linear-gradient(135deg, #1a1a2e 0%, #0f3460 100%); min-height: 100vh; padding: 20px; color: #e0e0e0;"
>
  <div style="max-width: 1400px; margin: 0 auto;">
    <header style="text-align: center; padding: 20px 0; border-bottom: 2px solid #16213e; margin-bottom: 30px;">
      <h1 style="font-size: 2.5em; color: #50fa7b; margin-bottom: 10px;">🌙 Nocturnal Eye</h1>
      <p style="color: #8be9fd; font-size: 1.1em;">Gecko Activity Monitoring</p>
    </header>

    <!-- Status Bar -->
    <div style="display: flex; justify-content: space-around; flex-wrap: wrap; gap: 15px; margin-bottom: 30px;">
      <div
        style="background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 20px; min-width: 200px; flex: 1; backdrop-filter: blur(10px);"
      >
        <h3 style="color: #8be9fd; font-size: 0.9em; margin-bottom: 10px; text-transform: uppercase;">
          Today's Activity
        </h3>
        <div style="font-size: 2em; color: #50fa7b; font-weight: bold;">{todayActivity}</div>
      </div>
      <div
        style="background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 20px; min-width: 200px; flex: 1; backdrop-filter: blur(10px);"
      >
        <h3 style="color: #8be9fd; font-size: 0.9em; margin-bottom: 10px; text-transform: uppercase;">
          Total Snapshots
        </h3>
        <div style="font-size: 2em; color: #50fa7b; font-weight: bold;">{snapshotCount}</div>
      </div>
      <div
        style="background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 20px; min-width: 200px; flex: 1; backdrop-filter: blur(10px);"
      >
        <h3 style="color: #8be9fd; font-size: 0.9em; margin-bottom: 10px; text-transform: uppercase;">
          Database Events
        </h3>
        <div style="font-size: 2em; color: #50fa7b; font-weight: bold;">{dbEvents}</div>
      </div>
      <div
        style="background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 20px; min-width: 200px; flex: 1; backdrop-filter: blur(10px);"
      >
        <h3 style="color: #8be9fd; font-size: 0.9em; margin-bottom: 10px; text-transform: uppercase;">Status</h3>
        <div style="font-size: 2em; color: #50fa7b; font-weight: bold;">{systemStatus}</div>
      </div>
    </div>

    <!-- Grid Content -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px;">
      <!-- Live Stream -->
      <div
        style="background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 20px; backdrop-filter: blur(10px); grid-column: 1 / -1;"
      >
        <h2
          style="color: #ff79c6; margin-bottom: 20px; font-size: 1.3em; border-bottom: 2px solid rgba(255, 255, 255, 0.1); padding-bottom: 10px;"
        >
          🎥 Live Stream with Zones
        </h2>
        <div
          style="position: relative; width: 100%; aspect-ratio: 16/9; background: #000; border-radius: 8px; overflow: hidden; margin-bottom: 10px;"
        >
          <video style="width: 100%; height: 100%; display: block; background: #000;" controls>
            <source src="http://localhost:8090/nocturnal-eye/stream.m3u8" type="application/x-mpegURL" />
            Your browser does not support the video tag.
          </video>
        </div>
        <p style="margin-top: 10px; color: #8be9fd; font-size: 0.9em;">
          🟢 Feeding Station | 🟠 Basking Spot | 🔵 Hide Box
        </p>
      </div>

      <!-- Snapshots -->
      <div
        style="background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 20px; backdrop-filter: blur(10px); grid-column: 1 / -1;"
      >
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
          <h2 style="color: #ff79c6; margin: 0; font-size: 1.3em;">📸 Recent Detections</h2>
          <button
            on:click="{loadDashboard}"
            style="background: #50fa7b; color: #1a1a2e; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-weight: bold; transition: all 0.2s;"
          >
            🔄 Refresh
          </button>
        </div>
        <div style="display: flex; gap: 10px; margin-bottom: 15px;">
          <button
            on:click="{prevSnapshots}"
            style="background: #50fa7b; color: #1a1a2e; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-weight: bold;"
          >
            ⬅ Newer
          </button>
          <button
            on:click="{nextSnapshots}"
            style="background: #50fa7b; color: #1a1a2e; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-weight: bold;"
          >
            Older ➡
          </button>
          <span style="color: #f1fa8c; font-size: 0.9em; display: flex; align-items: center;">
            Showing {snapshotOffset + 1}-{Math.min(snapshotOffset + snapshotLimit, snapshotTotal)} of {snapshotTotal}
          </span>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 15px;">
          {#if snapshots.length > 0}
            {#each snapshots as snap (snap.filename)}
              <div
                style="position: relative; border-radius: 8px; overflow: hidden; cursor: pointer; transition: transform 0.2s; background: rgba(0, 0, 0, 0.3);"
              >
                <img src="{snap.path}" alt="Detection" style="width: 100%; height: auto; display: block;" />
                <div
                  style="position: absolute; bottom: 0; left: 0; right: 0; background: linear-gradient(transparent, rgba(0, 0, 0, 0.9)); padding: 10px; font-size: 0.85em;"
                >
                  <div style="color: #8be9fd;">{snap.timestamp}</div>
                  <div style="color: #50fa7b; font-weight: bold;">
                    {snap.metadata?.detection_count || 0} detection(s)
                  </div>
                </div>
              </div>
            {/each}
          {:else}
            <div style="color: #8be9fd; padding: 20px; text-align: center;">Loading snapshots...</div>
          {/if}
        </div>
      </div>

      <!-- Zones -->
      <div
        style="background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 20px; backdrop-filter: blur(10px);"
      >
        <h2
          style="color: #ff79c6; margin-bottom: 20px; font-size: 1.3em; border-bottom: 2px solid rgba(255, 255, 255, 0.1); padding-bottom: 10px;"
        >
          🗺️ Defined Zones
        </h2>
        <div style="display: flex; flex-direction: column; gap: 10px;">
          {#if zones.length > 0}
            {#each zones as zone}
              <div
                style="display: flex; align-items: center; padding: 10px; background: rgba(255, 255, 255, 0.03); border-radius: 5px;"
              >
                <div
                  style="width: 20px; height: 20px; border-radius: 50%; margin-right: 10px; background-color: rgb({zone
                    .color[0]}, {zone.color[1]}, {zone.color[2]});"
                ></div>
                <div style="flex: 1; color: #f8f8f2;">{zone.name}</div>
                <div style="color: #6272a4; font-size: 0.85em;">({zone.x}, {zone.y}) r={zone.radius}</div>
              </div>
            {/each}
          {:else}
            <div style="color: #8be9fd; padding: 10px;">Loading zones...</div>
          {/if}
        </div>
      </div>

      <!-- Hourly Activity -->
      <div
        style="background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 20px; backdrop-filter: blur(10px);"
      >
        <h2
          style="color: #ff79c6; margin-bottom: 20px; font-size: 1.3em; border-bottom: 2px solid rgba(255, 255, 255, 0.1); padding-bottom: 10px;"
        >
          📊 Hourly Activity
        </h2>
        <div style="text-align: center; padding: 20px; color: #8be9fd;">
          {#if hourlyData.length > 0}
            Showing {hourlyData.length} hours of data
          {:else}
            Loading chart data...
          {/if}
        </div>
      </div>
    </div>
  </div>
</div>
