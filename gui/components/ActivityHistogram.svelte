<style>
  .activity-histogram-container {
    width: 100%;
    min-height: 200px;
  }

  .histogram-wrapper {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .histogram-legend {
    text-align: center;
    padding-top: 0.5rem;
    border-top: 1px solid #16213e;
  }
</style>

<script>
  import { onMount } from 'svelte';
  import { Bar } from 'svelte-chartjs';
  import { Chart as ChartJS, Title, Tooltip, Legend, CategoryScale, LinearScale, BarElement } from 'chart.js';

  ChartJS.register(Title, Tooltip, Legend, CategoryScale, LinearScale, BarElement);

  export let buckets = [];
  export let bucketMinutes = 60;
  export let loading = false;

  let chartData = { labels: [], datasets: [] };
  let chartOptions = {
    responsive: true,
    maintainAspectRatio: true,
    indexAxis: 'x',
    plugins: {
      legend: {
        display: false,
      },
      title: {
        display: false,
      },
      tooltip: {
        callbacks: {
          label: function (context) {
            return `${context.parsed.y} detections`;
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        ticks: {
          color: '#a0a0a0',
          font: {
            size: 11,
          },
        },
        grid: {
          color: 'rgba(0, 212, 255, 0.05)',
          drawBorder: false,
        },
      },
      x: {
        ticks: {
          color: '#a0a0a0',
          font: {
            size: 10,
          },
          maxRotation: 45,
          minRotation: 0,
        },
        grid: {
          display: false,
          drawBorder: false,
        },
      },
    },
  };

  $: if (buckets && buckets.length > 0) {
    const labels = buckets.map((bucket) => {
      if (!bucket.start) return '';
      const [datePart, timePart] = bucket.start.split('T');
      if (!timePart) return '';
      return timePart.split(':').slice(0, 2).join(':');
    });

    const data = buckets.map((bucket) => bucket.count || 0);

    chartData = {
      labels,
      datasets: [
        {
          label: 'Detections',
          data,
          backgroundColor: 'rgba(0, 212, 255, 0.7)',
          borderColor: '#00d4ff',
          borderWidth: 1,
          borderRadius: 3,
          barThickness: 'flex',
          maxBarThickness: 25,
        },
      ],
    };
  } else {
    chartData = { labels: [], datasets: [] };
  }
</script>

<div class="activity-histogram-container">
  {#if loading}
    <div class="text-center py-5">
      <i class="fas fa-2x fa-sync-alt fa-spin"></i>
    </div>
  {:else if buckets.length === 0}
    <div class="text-center py-5 text-muted">
      <p>No activity data for the selected range</p>
    </div>
  {:else}
    <div class="histogram-wrapper">
      <Bar data="{chartData}" options="{chartOptions}" />
      <div class="histogram-legend">
        <small style="color: #a0a0a0;">Interval: {bucketMinutes} minutes</small>
      </div>
    </div>
  {/if}
</div>
