<script lang="ts">
  import { filters } from '../lib/store';

  let currentFilters = $state($filters);
  $effect(() => {
    currentFilters = $filters;
  });

  const hasFilters = $derived(
    currentFilters.selectedKeywords.size > 0 ||
    currentFilters.selectedIssueTypes.size > 0 ||
    currentFilters.selectedPeople.size > 0
  );
</script>

{#if hasFilters}
  <div class="filter-banner">
    <div class="filter-content">
      <div class="filter-icon">[Filter]</div>
      <div class="filter-text">
        <strong>Active Filters:</strong>
        {#if currentFilters.selectedIssueTypes.size > 0}
          <span class="filter-chip">
            {currentFilters.selectedIssueTypes.size} issue type{currentFilters.selectedIssueTypes.size > 1 ? 's' : ''}
          </span>
        {/if}
        {#if currentFilters.selectedKeywords.size > 0}
          <span class="filter-chip">
            {currentFilters.selectedKeywords.size} keyword{currentFilters.selectedKeywords.size > 1 ? 's' : ''}
          </span>
        {/if}
        {#if currentFilters.selectedPeople.size > 0}
          <span class="filter-chip">
            {currentFilters.selectedPeople.size} {currentFilters.selectedPeople.size > 1 ? 'people' : 'person'}
          </span>
        {/if}
      </div>
      <button class="clear-btn" onclick={() => filters.clearAll()}>
        Clear All Filters
      </button>
    </div>
  </div>
{/if}

<style>
  .filter-banner {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 16px;
    border-radius: 8px;
    margin-bottom: 20px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  }

  .filter-content {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }

  .filter-icon {
    font-size: 20px;
  }

  .filter-text {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .filter-chip {
    background: rgba(255, 255, 255, 0.2);
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 13px;
    font-weight: 500;
  }

  .clear-btn {
    background: white;
    color: #667eea;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }

  .clear-btn:hover {
    transform: scale(1.05);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  }
</style>
