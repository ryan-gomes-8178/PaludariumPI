<script>
  import { onMount } from 'svelte';
  import { createEventDispatcher } from 'svelte';
  import { addFeeder, updateFeeder, fetchEnclosures } from '../../providers/api';

  export let feeder = null;

  const dispatch = createEventDispatcher();
  let formData = feeder ? { ...feeder } : {
    name: '',
    enclosure: '',
    hardware: '',
    enabled: true,
    servo_config: {
      feed_angle: 90,
      rest_angle: 0,
      rotate_duration: 1000,
      feed_hold_duration: 1500,
      portion_size: 1.0
    },
    schedule: {
      morning: { time: '08:00', enabled: true, portion_size: 1.0 },
      night: { time: '20:00', enabled: true, portion_size: 1.0 }
    }
  };

  let enclosures = [];
  let isSaving = false;
  let error = '';

  function loadEnclosures() {
    fetchEnclosures(null, (data) => {
      if (data && data.data) {
        enclosures = data.data;
      }
    });
  }

  async function handleSubmit() {
    try {
      isSaving = true;
      error = '';

      if (feeder) {
        // Update
        updateFeeder(formData, (data) => {
          dispatch('save');
        });
      } else {
        // Create
        addFeeder(formData, (data) => {
          dispatch('save');
        });
      }
    } catch (e) {
      error = e.message;
      console.error('Form error:', e);
    } finally {
      isSaving = false;
    }
  }

  function handleCancel() {
    dispatch('close');
  }

  onMount(loadEnclosures);
</script>

<div class="modal-overlay" on:click={handleCancel}>
  <div class="modal" on:click|stopPropagation>
    <div class="modal-header">
      <h2>{feeder ? 'Edit' : 'Add'} Feeder</h2>
      <button class="btn-close" on:click={handleCancel}>&times;</button>
    </div>

    <form on:submit|preventDefault={handleSubmit}>
      {#if error}
        <div class="alert alert-danger">{error}</div>
      {/if}

      <div class="form-group">
        <label for="name">Name:</label>
        <input
          id="name"
          type="text"
          bind:value={formData.name}
          required
          placeholder="e.g., Main Tank Feeder"
        />
      </div>

      <div class="form-group">
        <label for="enclosure">Enclosure:</label>
        <select id="enclosure" bind:value={formData.enclosure} required>
          <option value="">Select an enclosure</option>
          {#each enclosures as enc (enc.id)}
            <option value={enc.id}>{enc.name}</option>
          {/each}
        </select>
      </div>

      <div class="form-group">
        <label for="hardware">GPIO Pin:</label>
        <input
          id="hardware"
          type="text"
          bind:value={formData.hardware}
          required
          placeholder="e.g., 17"
        />
      </div>

      <div class="form-group">
        <label>
          <input type="checkbox" bind:checked={formData.enabled} />
          Enabled
        </label>
      </div>

      <div class="form-section">
        <h4>Servo Configuration</h4>

        <div class="form-row">
          <div class="form-group">
            <label for="feed_angle">Feed Angle:</label>
            <input
              id="feed_angle"
              type="number"
              bind:value={formData.servo_config.feed_angle}
              min="0"
              max="180"
            />
          </div>

          <div class="form-group">
            <label for="rest_angle">Rest Angle:</label>
            <input
              id="rest_angle"
              type="number"
              bind:value={formData.servo_config.rest_angle}
              min="0"
              max="180"
            />
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="rotate_duration">Rotate Duration (ms):</label>
            <input
              id="rotate_duration"
              type="number"
              bind:value={formData.servo_config.rotate_duration}
              min="100"
            />
          </div>

          <div class="form-group">
            <label for="feed_hold_duration">Feed Hold Duration (ms):</label>
            <input
              id="feed_hold_duration"
              type="number"
              bind:value={formData.servo_config.feed_hold_duration}
              min="100"
            />
          </div>
        </div>

        <div class="form-group">
          <label for="portion_size">Portion Size (g):</label>
          <input
            id="portion_size"
            type="number"
            bind:value={formData.servo_config.portion_size}
            min="0.1"
            step="0.1"
          />
        </div>
      </div>

      <div class="form-section">
        <h4>Feeding Schedule</h4>

        {#each Object.entries(formData.schedule) as [schedName, schedData] (schedName)}
          <div class="schedule-item">
            <div class="form-row">
              <div class="form-group">
                <label for="{schedName}-time">
                  {schedName.charAt(0).toUpperCase() + schedName.slice(1)} Time:
                </label>
                <input
                  id="{schedName}-time"
                  type="time"
                  bind:value={schedData.time}
                />
              </div>

              <div class="form-group">
                <label for="{schedName}-portion">Portion Size:</label>
                <input
                  id="{schedName}-portion"
                  type="number"
                  bind:value={schedData.portion_size}
                  min="0.1"
                  step="0.1"
                />
              </div>

              <div class="form-group checkbox">
                <label>
                  <input type="checkbox" bind:checked={schedData.enabled} />
                  Enabled
                </label>
              </div>
            </div>
          </div>
        {/each}
      </div>

      <div class="form-actions">
        <button type="button" class="btn btn-secondary" on:click={handleCancel}>
          Cancel
        </button>
        <button type="submit" class="btn btn-primary" disabled={isSaving}>
          {isSaving ? 'Saving...' : 'Save'}
        </button>
      </div>
    </form>
  </div>
</div>

<style>
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .modal {
    background: white;
    border-radius: 8px;
    width: 90%;
    max-width: 600px;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px;
    border-bottom: 1px solid #eee;
  }

  .btn-close {
    background: none;
    border: none;
    font-size: 24px;
    cursor: pointer;
    color: #666;
  }

  form {
    padding: 20px;
  }

  .form-group {
    margin-bottom: 15px;
  }

  .form-group label {
    display: block;
    margin-bottom: 5px;
    font-weight: 500;
  }

  .form-group input[type='text'],
  .form-group input[type='number'],
  .form-group input[type='time'],
  .form-group select {
    width: 100%;
    padding: 8px;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 14px;
  }

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 15px;
  }

  .form-section {
    margin-top: 20px;
    padding-top: 20px;
    border-top: 1px solid #eee;
  }

  .form-section h4 {
    margin-top: 0;
    margin-bottom: 15px;
  }

  .schedule-item {
    margin-bottom: 15px;
    padding: 10px;
    background-color: #f9f9f9;
    border-radius: 4px;
  }

  .checkbox {
    display: flex;
    align-items: center;
  }

  .checkbox input[type='checkbox'] {
    margin-right: 8px;
    width: auto;
  }

  .form-actions {
    display: flex;
    gap: 10px;
    margin-top: 20px;
    padding-top: 20px;
    border-top: 1px solid #eee;
  }

  .form-actions button {
    flex: 1;
  }
</style>
