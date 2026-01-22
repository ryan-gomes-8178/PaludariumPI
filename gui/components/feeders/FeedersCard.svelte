<script>
  import { createEventDispatcher } from 'svelte';
  import { manualFeed, testFeederServo } from '../../providers/api';

  export let feeder;

  const dispatch = createEventDispatcher();
  let isFeedingNow = false;

  async function triggerManualFeed() {
    try {
      isFeedingNow = true;
      await manualFeed(feeder.id, feeder.servo_config.portion_size, (data) => {
        dispatch('reload');
        isFeedingNow = false;
      });
    } catch (e) {
      console.error('Feed error:', e);
      isFeedingNow = false;
    }
  }

  async function testServo() {
    try {
      await testFeederServo(feeder.id, (data) => {
        console.log('Servo test result:', data);
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

  .card-header {
    background-color: #f5f5f5;
    padding: 15px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .card-header h3 {
    margin: 0;
    font-size: 18px;
  }

  .card-body {
    padding: 15px;
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

  .card-actions {
    padding: 15px;
    background-color: #f9f9f9;
    display: flex;
    gap: 5px;
    flex-wrap: wrap;
  }

  .btn {
    flex: 1;
    min-width: 70px;
  }
</style>
