<style>
  .monitoring-stream-wrapper {
    position: relative;
    width: 100%;
    background: #000;
    border-radius: 0.25rem;
    overflow: hidden;
  }

  .monitoring-stream {
    width: 100%;
    height: auto;
    display: block;
  }

  .monitoring-overlay {
    position: absolute;
    inset: 0;
    pointer-events: none;
  }

  .monitoring-zone-list {
    max-height: 320px;
    overflow: auto;
  }

  .monitoring-events {
    max-height: 420px;
    overflow: auto;
  }
</style>

<script>
  import { onMount, onDestroy } from 'svelte';
  import { PageHeader } from '@keenmate/svelte-adminlte';
  import { _ } from 'svelte-i18n';

  import { setCustomPageTitle, customPageTitleUsed } from '../stores/page-title';
  import { fetchMonitoringZones, fetchMonitoringEvents, fetchEnclosures } from '../providers/api';
  import { ApiUrl } from '../constants/urls';

  import hls from 'hls.js';

  let enclosures = [];
  let selectedEnclosure = '';
  let zones = [];
  let events = [];

  let videoEl;
  let canvasEl;
  let hlsPlayer;
  let refreshTimer;
  let resizeObserver;

  const streamUrl = `${ApiUrl}/nocturnal-eye/stream.m3u8`;

  const zoneColors = {
    basking: '#ff9800',
    hide: '#3f51b5',
    feeding: '#4caf50',
    general: '#00bcd4',
    default: '#f44336',
  };

  const getZoneColor = (zone) => {
    if (zone?.meta?.color) return zone.meta.color;
    if (zone?.type && zoneColors[zone.type]) return zoneColors[zone.type];
    return zoneColors.default;
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

  const resizeCanvas = () => {
    if (!videoEl || !canvasEl) return;
    const rect = videoEl.getBoundingClientRect();
    canvasEl.width = rect.width;
    canvasEl.height = rect.height;
    drawZones();
  };

  const drawZones = () => {
    if (!canvasEl) return;
    const ctx = canvasEl.getContext('2d');
    if (!ctx) return;

    const width = canvasEl.width;
    const height = canvasEl.height;
    ctx.clearRect(0, 0, width, height);

    zones.forEach((zone) => {
      const shape = zone.shape || {};
      const color = getZoneColor(zone);

      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.fillStyle = color + '33';
      ctx.font = '12px "Source Sans Pro", sans-serif';
      ctx.textBaseline = 'top';

      if (shape.type === 'polygon' && Array.isArray(shape.points)) {
        const points = shape.points.map((point) => ({
          x: point.x * width,
          y: point.y * height,
        }));
        if (points.length > 2) {
          ctx.beginPath();
          ctx.moveTo(points[0].x, points[0].y);
          points.slice(1).forEach((point) => ctx.lineTo(point.x, point.y));
          ctx.closePath();
          ctx.fill();
          ctx.stroke();
          ctx.fillStyle = color;
          ctx.fillText(zone.name, points[0].x + 4, points[0].y + 4);
        }
      } else if (shape.type === 'rect') {
        const x = (shape.x || 0) * width;
        const y = (shape.y || 0) * height;
        const w = (shape.width || 0) * width;
        const h = (shape.height || 0) * height;
        ctx.fillRect(x, y, w, h);
        ctx.strokeRect(x, y, w, h);
        ctx.fillStyle = color;
        ctx.fillText(zone.name, x + 4, y + 4);
      }
    });
  };

  const loadEnclosures = () => {
    fetchEnclosures(false, (data) => {
      enclosures = data;
      if (!selectedEnclosure && enclosures.length > 0) {
        selectedEnclosure = enclosures[0].id;
      }
      loadZones();
      loadEvents();
    });
  };

  const loadZones = () => {
    if (!selectedEnclosure) {
      zones = [];
      drawZones();
      return;
    }
    fetchMonitoringZones(selectedEnclosure, (data) => {
      zones = data || [];
      drawZones();
    });
  };

  const loadEvents = () => {
    if (!selectedEnclosure) {
      events = [];
      return;
    }
    fetchMonitoringEvents({ enclosure: selectedEnclosure, limit: 50 }, (data) => {
      events = data || [];
    });
  };

  const handleEnclosureChange = () => {
    loadZones();
    loadEvents();
  };

  const resolveZoneName = (zoneId) => {
    if (!zoneId) return $_('monitoring.events.unknown_zone', { default: 'Unknown zone' });
    const zone = zones.find((z) => z.id === zoneId);
    return zone ? zone.name : $_('monitoring.events.unknown_zone', { default: 'Unknown zone' });
  };

  onMount(() => {
    setCustomPageTitle($_('monitoring.title', { default: 'Monitoring' }));
    setupHls();
    loadEnclosures();

    refreshTimer = setInterval(() => {
      loadEvents();
    }, 10000);

    window.addEventListener('resize', resizeCanvas);

    resizeObserver = new ResizeObserver(() => {
      resizeCanvas();
    });
    if (videoEl) {
      resizeObserver.observe(videoEl);
    }
  });

  onDestroy(() => {
    customPageTitleUsed.set(false);
    window.removeEventListener('resize', resizeCanvas);

    if (refreshTimer) {
      clearInterval(refreshTimer);
    }

    if (resizeObserver) {
      resizeObserver.disconnect();
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
  <div class="row mb-3">
    <div class="col-md-4">
      <label>{$_('monitoring.enclosure.label', { default: 'Enclosure' })}</label>
      <select class="form-control" bind:value={selectedEnclosure} on:change={handleEnclosureChange}>
        {#if enclosures.length === 0}
          <option value="">{$_('monitoring.enclosure.empty', { default: 'No enclosures available' })}</option>
        {/if}
        {#each enclosures as enclosure}
          <option value={enclosure.id}>{enclosure.name}</option>
        {/each}
      </select>
    </div>
    <div class="col-md-8 d-flex align-items-end">
      <button class="btn btn-primary mr-2" on:click={loadEvents}>
        <i class="fas fa-sync-alt mr-1"></i>{$_('monitoring.actions.refresh', { default: 'Refresh activity' })}
      </button>
      <button class="btn btn-outline-secondary" on:click={loadZones}>
        <i class="fas fa-border-style mr-1"></i>{$_('monitoring.actions.refresh_zones', { default: 'Reload zones' })}
      </button>
    </div>
  </div>

  <div class="row">
    <div class="col-xl-8">
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{$_('monitoring.stream.title', { default: 'Live stream' })}</h3>
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
              on:loadedmetadata={resizeCanvas}
            ></video>
            <canvas class="monitoring-overlay" bind:this={canvasEl}></canvas>
          </div>
        </div>
      </div>
    </div>

    <div class="col-xl-4">
      <div class="card mb-3">
        <div class="card-header">
          <h3 class="card-title">{$_('monitoring.zones.title', { default: 'Zones' })}</h3>
        </div>
        <div class="card-body monitoring-zone-list">
          {#if zones.length === 0}
            <p class="text-muted">{$_('monitoring.zones.empty', { default: 'No monitoring zones configured yet.' })}</p>
          {:else}
            <ul class="list-unstyled mb-0">
              {#each zones as zone}
                <li class="mb-2">
                  <span class="badge mr-2" style="background:{getZoneColor(zone)}">&nbsp;</span>
                  <strong>{zone.name}</strong>
                  <div class="text-muted">
                    {zone.type || $_('monitoring.zones.default_type', { default: 'general' })}
                  </div>
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{$_('monitoring.events.title', { default: 'Recent activity' })}</h3>
        </div>
        <div class="card-body monitoring-events">
          {#if events.length === 0}
            <p class="text-muted">{$_('monitoring.events.empty', { default: 'No detections yet.' })}</p>
          {:else}
            <ul class="list-group">
              {#each events as event}
                <li class="list-group-item">
                  <div class="d-flex justify-content-between">
                    <div>
                      <strong>{event.label || $_('monitoring.events.default_label', { default: 'Detection' })}</strong>
                      <div class="text-muted">{resolveZoneName(event.zone)}</div>
                    </div>
                    <small class="text-muted">
                      {new Date(event.timestamp * 1000).toLocaleString()}
                    </small>
                  </div>
                  {#if event.confidence !== null && event.confidence !== undefined}
                    <div class="text-muted">
                      {$_('monitoring.events.confidence', { default: 'Confidence' })}: {(event.confidence * 100).toFixed(1)}%
                    </div>
                  {/if}
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      </div>
    </div>
  </div>
</div>
