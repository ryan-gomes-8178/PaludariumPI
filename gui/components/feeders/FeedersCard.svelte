<script>
  import { createEventDispatcher } from 'svelte';
  import { manualFeed, testFeederServo } from '../../providers/api';

  export let feeder;

  const dispatch = createEventDispatcher();
  let isFeedingNow = false;

  function triggerManualFeed() {
    try {
      isFeedingNow = true;
      manualFeed(feeder.id, feeder.servo_config.portion_size, (data) => {
        dispatch('reload');
        isFeedingNow = false;
      });
    } catch (e) {
      console.error('Feed error:', e);
      isFeedingNow = false;
    }
  }

  function testServo() {
    try {
      testFeederServo(feeder.id, (data) => {
        // Handle servo test result if needed
      });
    } catch (e) {
      console.error('Test error:', e);
    }
  }
</script>

<div class="feeder-card">
  <div class="card-header">
    <h3>{feeder.name}</h3>
    <div class="status">
      {#if feeder.enabled}
        <span class="badge badge-success">Enabled</span>
      {:else}
        <span class="badge badge-secondary">Disabled</span>
      {/if}
    </div>
  </div>

  <div class="card-body">
    <div class="info-row">
      <label>Enclosure:</label>
      <span>{feeder.enclosure}</span>
    </div>
    <div class="info-row">
      <label>GPIO:</label>
      <span>{feeder.hardware}</span>
    </div>
    <div class="info-row">
      <label>Portion Size:</label>
      <span>{feeder.servo_config.portion_size}g</span>
    </div>
  </div>

  <div class="card-actions">
    <button
      class="btn btn-sm btn-success"
      on:click={triggerManualFeed}
      disabled={isFeedingNow}
    >
      {isFeedingNow ? 'Feeding...' : 'Feed Now'}
    </button>
    <button class="btn btn-sm btn-info" on:click={testServo}>
      Test
    </button>
    <button class="btn btn-sm btn-warning" on:click={() => dispatch('edit')}>
      Edit
    </button>
    <button class="btn btn-sm btn-danger" on:click={() => dispatch('delete')}>
      Delete
    </button>
  </div>
</div>

<style>
  .feeder-card {
    border: 1px solid #ddd;
    border-radius: 8px;
    overflow: hidden;
  }

  :global(.dark-mode) .feeder-card {
    border-color: #4b5563;
  }

  .card-header {
    background-color: #f5f5f5;
    padding: 15px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  :global(.dark-mode) .card-header {
    background-color: #343a40;
  }

  .card-header h3 {
    margin: 0;
    font-size: 18px;
    color: #333;
  }

  :global(.dark-mode) .card-header h3 {
    color: #fff;
  }

  .card-body {
    padding: 15px;
    background-color: #fff;
  }

  :global(.dark-mode) .card-body {
    background-color: #454d55;
  }

  .info-row {
    display: flex;
    justify-content: space-between;
    margin-bottom: 8px;
    font-size: 14px;
  }

  .info-row label {
    font-weight: bold;
    color: #666;
  }

  :global(.dark-mode) .info-row label {
    color: #adb5bd;
  }

  .info-row span {
    color: #333;
  }

  :global(.dark-mode) .info-row span {
    color: #e9ecef;
  }

  .card-actions {
    padding: 15px;
    background-color: #f9f9f9;
    display: flex;
    gap: 5px;
    flex-wrap: wrap;
  }

  :global(.dark-mode) .card-actions {
    background-color: #2d3238;
  }

  .btn {
    flex: 1;
    min-width: 70px;
  }
</style>
