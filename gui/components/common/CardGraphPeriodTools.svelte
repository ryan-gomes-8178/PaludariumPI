<script>
  import { _ } from 'svelte-i18n';
  import { graphs } from '../../stores/terrariumpi';
  import { toggleGraphPeriod } from '../../helpers/graph-helpers';

  export let id;
  export let replaced = false;

  let customStart = '';
  let customEnd = '';
  let showCustom = false;

  // When clicking Custom, initialize local dates from store and show inputs
  function onCustomClick() {
    const graph = $graphs[id];
    customStart = graph.customStart || '';
    customEnd = graph.customEnd || '';
    showCustom = true;
  }

  // Handle custom date change and trigger fetch only when both dates are valid
  function onCustomDateChange() {
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
      on:click="{() => toggleGraphPeriod(id, 'hour')}">{$_('graph.period.hour', { default: 'Hour' })}</button
    >
    <button
      class="dropdown-item"
      class:active="{$graphs[id].period === 'day'}"
      on:click="{() => toggleGraphPeriod(id, 'day')}"
    >{$_('graph.period.day', { default: 'Day' })}</button>

    <button
      class="dropdown-item"
      class:active="{$graphs[id].period === 'week'}"
      on:click="{() => toggleGraphPeriod(id, 'week')}"
    >{$_('graph.period.week', { default: 'Week' })}</button>

    <button
      class="dropdown-item"
      class:active="{$graphs[id].period === 'month'}"
      on:click="{() => toggleGraphPeriod(id, 'month')}"
    >{$_('graph.period.month', { default: 'Month' })}</button>

    <button
      class="dropdown-item"
      class:active="{$graphs[id].period === 'year'}"
      on:click="{() => toggleGraphPeriod(id, 'year')}"
    >{$_('graph.period.year', { default: 'Year' })}</button>

    {#if replaced}
      <button
        class="dropdown-item"
        class:active="{$graphs[id].period === 'replaced'}"
        on:click="{() => toggleGraphPeriod(id, 'replaced')}"
      >{$_('graph.period.replaced', { default: 'Replaced' })}</button>
    {/if}

    <!-- Custom period option: initialize and show date inputs -->
    <button
      class="dropdown-item"
      class:active="{$graphs[id].period === 'custom'}"
      on:click="{onCustomClick}"
    >Custom</button>

    {#if showCustom}
      <div class="dropdown-item" style="white-space: nowrap; display: flex; gap: 0.5rem;">
        <input type="date" bind:value={customStart} on:change={onCustomDateChange} />
        <input type="date" bind:value={customEnd} on:change={onCustomDateChange} />
      </div>
    {/if}
  </div>
</div>
