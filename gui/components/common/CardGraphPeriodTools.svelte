<script>
  import { _ } from 'svelte-i18n';
  import { graphs } from '../../stores/terrariumpi';
  import { toggleGraphPeriod } from '../../helpers/graph-helpers';
  import { tick } from 'svelte';

  export let id;
  export let replaced = false;

  let customStart = '';
  let customEnd = '';
  let showCustom = false;
  let customStartInput;

  // When clicking Custom, initialize local dates from store and show inputs
  async function onCustomClick(event) {
    // stopPropagation to prevent Bootstrap from closing the dropdown
    event.stopPropagation();
    const graph = $graphs[id];
    customStart = graph.customStart || '';
    customEnd = graph.customEnd || '';
    showCustom = true;
    await tick();
    if (customStartInput) customStartInput.focus();
  }

  // Handle custom date change and trigger fetch only when both dates are valid
  function onCustomDateChange(event) {
    // stopPropagation to keep dropdown open while interacting with inputs
    event.stopPropagation();
    if (customStart && customEnd && customStart <= customEnd) {
      toggleGraphPeriod(id, 'custom', { start: customStart, end: customEnd });
      showCustom = false;
    }
  }
</script>

<div class="btn-group">
  <button type="button" class="btn btn-tool dropdown-toggle" data-toggle="dropdown">
    <i class="fas fa-calendar-alt"></i>
  </button>
  <div class="dropdown-menu dropdown-menu-right" role="menu" style="min-width: auto !important;">
    <button
      class="dropdown-item"
      class:active="{$graphs[id].period === 'hour'}"
      on:click={() => toggleGraphPeriod(id, 'hour')}>{$_('graph.period.hour', { default: 'Hour' })}</button
    >
    <button
      class="dropdown-item"
      class:active="{$graphs[id].period === 'day'}"
      on:click={() => toggleGraphPeriod(id, 'day')}
    >{$_('graph.period.day', { default: 'Day' })}</button>

    <button
      class="dropdown-item"
      class:active="{$graphs[id].period === 'week'}"
      on:click={() => toggleGraphPeriod(id, 'week')}
    >{$_('graph.period.week', { default: 'Week' })}</button>

    <button
      class="dropdown-item"
      class:active="{$graphs[id].period === 'month'}"
      on:click={() => toggleGraphPeriod(id, 'month')}
    >{$_('graph.period.month', { default: 'Month' })}</button>

    <button
      class="dropdown-item"
      class:active="{$graphs[id].period === 'year'}"
      on:click={() => toggleGraphPeriod(id, 'year')}
    >{$_('graph.period.year', { default: 'Year' })}</button>

    {#if replaced}
      <button
        class="dropdown-item"
        class:active="{$graphs[id].period === 'replaced'}"
        on:click={() => toggleGraphPeriod(id, 'replaced')}
      >{$_('graph.period.replaced', { default: 'Replaced' })}</button>
    {/if}

    <!-- Custom period option: initialize and show date inputs.
         Use stopPropagation on the click so Bootstrap does not auto-close the dropdown -->
    <button
      class="dropdown-item"
      class:active="{$graphs[id].period === 'custom'}"
      on:click|stopPropagation={onCustomClick}
    >Custom</button>

    {#if showCustom}
      <!-- stopPropagation on this container keeps the menu open while interacting with inputs -->
      <div class="dropdown-item" style="white-space: nowrap; display: flex; gap: 0.5rem;" on:click|stopPropagation role="presentation">
        <input type="date" bind:this={customStartInput} bind:value={customStart} on:change={onCustomDateChange} />
        <input type="date" bind:value={customEnd} on:change={onCustomDateChange} />
      </div>
    {/if}
  </div>
</div>
