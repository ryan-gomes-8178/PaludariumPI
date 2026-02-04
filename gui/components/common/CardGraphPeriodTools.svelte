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
  let includeTime = false;

  function populateFromStore() {
    const graph = $graphs[id];
    customStart = graph.customStart || '';
    customEnd = graph.customEnd || '';
    includeTime = (customStart && customStart.includes('T')) || (customEnd && customEnd.includes('T'));
  }

  // Called when calendar icon is clicked (dropdown opens) — always show custom inputs prefilled
  function onCalendarClick() {
    populateFromStore();
    showCustom = true;
  }

  // When clicking Custom button (keeps dropdown open)
  async function onCustomClick(event) {
    event.stopPropagation();
    populateFromStore();
    showCustom = true;
    await tick();
    if (customStartInput) customStartInput.focus();
  }

  // Toggle include time and convert current values sensibly
  function toggleIncludeTime(event) {
    event.stopPropagation();
    // includeTime already updated by bind:checked, convert values
    if (includeTime) {
      if (customStart && !customStart.includes('T')) customStart = `${customStart}T00:00`;
      if (customEnd && !customEnd.includes('T')) customEnd = `${customEnd}T23:59`;
    } else {
      if (customStart && customStart.includes('T')) customStart = customStart.split('T')[0];
      if (customEnd && customEnd.includes('T')) customEnd = customEnd.split('T')[0];
    }
  }

  // Only submit when both are present and valid
  function onCustomDateChange(event) {
    event.stopPropagation();
    if (!customStart || !customEnd) return;

    // Compare strings: normalize to comparable Date objects
    const a = new Date(customStart);
    const b = new Date(customEnd);
    if (isNaN(a.getTime()) || isNaN(b.getTime())) return;
    if (a <= b) {
      toggleGraphPeriod(id, 'custom', { start: customStart, end: customEnd });
      showCustom = false;
    }
  }
</script>

<div class="btn-group">
  <button type="button" class="btn btn-tool dropdown-toggle" data-toggle="dropdown" on:click="{onCalendarClick}">
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
      on:click="{() => toggleGraphPeriod(id, 'day')}">{$_('graph.period.day', { default: 'Day' })}</button
    >

    <button
      class="dropdown-item"
      class:active="{$graphs[id].period === 'week'}"
      on:click="{() => toggleGraphPeriod(id, 'week')}">{$_('graph.period.week', { default: 'Week' })}</button
    >

    <button
      class="dropdown-item"
      class:active="{$graphs[id].period === 'month'}"
      on:click="{() => toggleGraphPeriod(id, 'month')}">{$_('graph.period.month', { default: 'Month' })}</button
    >

    <button
      class="dropdown-item"
      class:active="{$graphs[id].period === 'year'}"
      on:click="{() => toggleGraphPeriod(id, 'year')}">{$_('graph.period.year', { default: 'Year' })}</button
    >

    {#if replaced}
      <button
        class="dropdown-item"
        class:active="{$graphs[id].period === 'replaced'}"
        on:click="{() => toggleGraphPeriod(id, 'replaced')}"
        >{$_('graph.period.replaced', { default: 'Replaced' })}</button
      >
    {/if}

    <!-- Custom period option: initialize and show date inputs.
         Use stopPropagation on the click so Bootstrap does not auto-close the dropdown -->
    <button
      class="dropdown-item"
      class:active="{$graphs[id].period === 'custom'}"
      on:click|stopPropagation="{onCustomClick}">Custom</button
    >

    {#if showCustom}
      <div
        class="dropdown-item"
        style="white-space: nowrap; display:flex; flex-direction:column; gap:0.5rem;"
        on:click|stopPropagation
        role="presentation"
      >
        <div style="display:flex; gap:0.5rem; align-items:center;">
          {#if includeTime}
            <input
              bind:this="{customStartInput}"
              type="datetime-local"
              bind:value="{customStart}"
              on:change="{onCustomDateChange}"
            />
          {:else}
            <input
              bind:this="{customStartInput}"
              type="date"
              bind:value="{customStart}"
              on:change="{onCustomDateChange}"
            />
          {/if}
          <span style="align-self:center;">—</span>
          {#if includeTime}
            <input type="datetime-local" bind:value="{customEnd}" on:change="{onCustomDateChange}" />
          {:else}
            <input type="date" bind:value="{customEnd}" on:change="{onCustomDateChange}" />
          {/if}
        </div>

        <div style="display:flex; gap:0.5rem; align-items:center;">
          <input id="include-time-{id}" type="checkbox" bind:checked="{includeTime}" on:change="{toggleIncludeTime}" />
          <label for="include-time-{id}" style="font-size:0.85rem; margin:0;">Include time</label>
        </div>
      </div>
    {/if}
  </div>
</div>
