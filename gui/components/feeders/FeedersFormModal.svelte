<script>
  import { Modal, ModalCloseButton } from '@keenmate/svelte-adminlte';
  import { onMount } from 'svelte';
  import { createEventDispatcher } from 'svelte';
  import { addFeeder, updateFeeder, fetchEnclosures } from '../../providers/api';
  import { successNotification, errorNotification } from '../../providers/notification-provider';
  import { _ } from 'svelte-i18n';

  let wrapper_show;
  let wrapper_hide;

  export let feeder = null;

  const dispatch = createEventDispatcher();
  let formData = {
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
    try {
      fetchEnclosures(null, (data) => {
        console.log('Enclosures loaded:', data);
        if (data && data.data) {
          enclosures = data.data;
        } else if (Array.isArray(data)) {
          enclosures = data;
        }
      });
    } catch (e) {
      console.error('Error loading enclosures:', e);
      error = 'Failed to load enclosures';
    }
  }

  function handleSubmit() {
    isSaving = true;
    error = '';
    console.log('Submitting feeder:', formData);

    const saveFunction = formData.id ? updateFeeder : addFeeder;
    const action = formData.id ? 'updated' : 'saved';
    
    saveFunction(formData, (data) => {
      console.log('Feeder save response:', data);
      isSaving = false;
      if (data && !data.error) {
        successNotification(
          $_(`notification.feeder.${action}`, { default: `Feeder ${action} successfully` }),
          $_('feeders.menu.title', { default: 'Feeders' })
        );
        console.log('Dispatching save event to reload feeders list');
        dispatch('save');
        hide();
      } else {
        error = data?.error || 'Failed to save feeder';
        console.error('Save error:', error);
        errorNotification(
          error,
          $_('feeders.menu.title', { default: 'Feeders' })
        );
      }
    });
  }

  function hide() {
    if (wrapper_hide) {
      wrapper_hide();
    }
  }

  export function show(item, cb) {
    if (item) {
      feeder = item;
      formData = { ...item };
      // Restore enclosure_id if it exists (backend sends both enclosure name and enclosure_id)
      if (item.enclosure_id && !item.enclosure.match(/^[0-9a-f-]{36}$/i)) {
        formData.enclosure = item.enclosure_id;
      }
    } else {
      feeder = null;
      formData = {
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
    }
    error = '';
    loadEnclosures();
    if (wrapper_show) {
      wrapper_show();
    }
    if (cb) {
      cb();
    }
  }

  onMount(() => {
    console.log('FeedersFormModal mounted');
  });
</script>

<Modal bind:show="{wrapper_show}" bind:hide="{wrapper_hide}" title="{feeder ? $_('edit_feeder', { default: 'Edit Feeder' }) : $_('add_feeder', { default: 'Add Feeder' })}">
  <ModalCloseButton />
  
  {#if error}
    <div class="alert alert-danger">{error}</div>
  {/if}

  <form on:submit|preventDefault={handleSubmit}>
    <div class="form-group">
      <label for="name">{$_('name', { default: 'Name' })}:</label>
      <input
        id="name"
        type="text"
        bind:value={formData.name}
        required
        placeholder="e.g., Main Tank Feeder"
        class="form-control"
      />
    </div>

    <div class="form-group">
      <label for="enclosure">{$_('enclosure', { default: 'Enclosure' })}:</label>
      <select id="enclosure" bind:value={formData.enclosure} required class="form-control">
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
        class="form-control"
      />
    </div>

    <div class="form-group">
      <label>
        <input type="checkbox" bind:checked={formData.enabled} />
        {$_('enabled', { default: 'Enabled' })}
      </label>
    </div>

    <div class="form-section">
      <h5>Servo Configuration</h5>

      <div class="form-row">
        <div class="form-group col-md-6">
          <label for="feed_angle">Feed Angle:</label>
          <input
            id="feed_angle"
            type="number"
            bind:value={formData.servo_config.feed_angle}
            min="0"
            max="180"
            class="form-control"
          />
        </div>

        <div class="form-group col-md-6">
          <label for="rest_angle">Rest Angle:</label>
          <input
            id="rest_angle"
            type="number"
            bind:value={formData.servo_config.rest_angle}
            min="0"
            max="180"
            class="form-control"
          />
        </div>
      </div>

      <div class="form-row">
        <div class="form-group col-md-6">
          <label for="rotate_duration">Rotate Duration (ms):</label>
          <input
            id="rotate_duration"
            type="number"
            bind:value={formData.servo_config.rotate_duration}
            min="100"
            class="form-control"
          />
        </div>

        <div class="form-group col-md-6">
          <label for="feed_hold_duration">Feed Hold Duration (ms):</label>
          <input
            id="feed_hold_duration"
            type="number"
            bind:value={formData.servo_config.feed_hold_duration}
            min="100"
            class="form-control"
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
          class="form-control"
        />
      </div>
    </div>

    <div class="form-section">
      <h5>Feeding Schedule</h5>

      {#each Object.entries(formData.schedule) as [schedName, schedData] (schedName)}
        <div class="schedule-item card p-3 mb-3">
          <div class="form-row">
            <div class="form-group col-md-4">
              <label for="{schedName}-time">
                {schedName.charAt(0).toUpperCase() + schedName.slice(1)} Time:
              </label>
              <input
                id="{schedName}-time"
                type="time"
                bind:value={schedData.time}
                class="form-control"
              />
            </div>

            <div class="form-group col-md-4">
              <label for="{schedName}-portion">Portion Size:</label>
              <input
                id="{schedName}-portion"
                type="number"
                bind:value={schedData.portion_size}
                min="0.1"
                step="0.1"
                class="form-control"
              />
            </div>

            <div class="form-group col-md-4 d-flex align-items-end">
              <label class="mb-0">
                <input type="checkbox" bind:checked={schedData.enabled} />
                {$_('enabled', { default: 'Enabled' })}
              </label>
            </div>
          </div>
        </div>
      {/each}
    </div>

    <div class="form-group">
      <button type="submit" class="btn btn-primary" disabled={isSaving}>
        {isSaving ? $_('saving', { default: 'Saving...' }) : $_('save', { default: 'Save' })}
      </button>
    </div>
  </form>
</Modal>

<style>
  .form-section {
    margin-top: 20px;
    padding-top: 20px;
    border-top: 1px solid #eee;
  }

  .form-section h5 {
    margin-bottom: 15px;
  }

  .schedule-item {
    background-color: #f9f9f9;
  }
</style>
