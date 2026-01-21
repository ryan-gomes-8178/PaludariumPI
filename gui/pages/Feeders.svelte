<script>
  import { onMount } from 'svelte';
  import FeedersCard from '../components/feeders/FeedersCard.svelte';
  import FeedersForm from '../components/feeders/FeedersForm.svelte';
  import { fetchFeeders, deleteFeeder } from '../providers/api';

  let feeders = [];
  let showForm = false;
  let selectedFeeder = null;
  let loading = true;
  let error = '';

  onMount(() => {
    loadFeeders();
  });

  function loadFeeders() {
    loading = true;
    error = '';
    fetchFeeders(null, (data) => {
      if (data && data.data) {
        feeders = data.data;
      }
      loading = false;
    });
  }

  function handleAddFeeder() {
    selectedFeeder = null;
    showForm = true;
  }

  function handleEditFeeder(feeder) {
    selectedFeeder = feeder;
    showForm = true;
  }

  function handleFormClose() {
    showForm = false;
    selectedFeeder = null;
  }

  function handleFormSave() {
    loadFeeders();
    handleFormClose();
  }

  function handleDeleteFeeder(feeder) {
    if (confirm(`Are you sure you want to delete ${feeder.name}?`)) {
      deleteFeeder(feeder.id, (data) => {
        loadFeeders();
      });
    }
  }
</script>

<div class="feeders-page">
  <div class="page-header">
    <h1>Aquarium Feeders</h1>
    <button class="btn btn-primary" on:click={handleAddFeeder}>+ Add Feeder</button>
  </div>

  {#if error}
    <div class="alert alert-danger">{error}</div>
  {/if}

  {#if loading}
    <p>Loading feeders...</p>
  {:else if feeders.length === 0}
    <p class="text-muted">No feeders configured yet.</p>
  {:else}
    <div class="feeders-grid">
      {#each feeders as feeder (feeder.id)}
        <FeedersCard
          {feeder}
          on:edit={() => handleEditFeeder(feeder)}
          on:delete={() => handleDeleteFeeder(feeder)}
          on:reload={loadFeeders}
        />
      {/each}
    </div>
  {/if}

  {#if showForm}
    <FeedersForm
      feeder={selectedFeeder}
      on:close={handleFormClose}
      on:save={handleFormSave}
    />
  {/if}
</div>

<style>
  .feeders-page {
    padding: 20px;
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 30px;
  }

  .feeders-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 20px;
  }
</style>
