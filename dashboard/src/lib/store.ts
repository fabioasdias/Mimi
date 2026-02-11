/**
 * Shared state store for linked visualizations
 * All charts subscribe to this store and update when filters change
 */

import { writable } from 'svelte/store';

export interface Filters {
  selectedKeywords: Set<string>;
  selectedIssueTypes: Set<string>;
  selectedPeople: Set<string>;
}

// Create the store with empty filters
function createFilterStore() {
  const { subscribe, set, update } = writable<Filters>({
    selectedKeywords: new Set(),
    selectedIssueTypes: new Set(),
    selectedPeople: new Set()
  });

  return {
    subscribe,

    // Toggle a keyword filter
    toggleKeyword: (keyword: string) => update(filters => {
      const newKeywords = new Set(filters.selectedKeywords);
      if (newKeywords.has(keyword)) {
        newKeywords.delete(keyword);
      } else {
        newKeywords.add(keyword);
      }
      return { ...filters, selectedKeywords: newKeywords };
    }),

    // Toggle an issue type filter
    toggleIssueType: (type: string) => update(filters => {
      const newTypes = new Set(filters.selectedIssueTypes);
      if (newTypes.has(type)) {
        newTypes.delete(type);
      } else {
        newTypes.add(type);
      }
      return { ...filters, selectedIssueTypes: newTypes };
    }),

    // Toggle a person filter
    togglePerson: (person: string) => update(filters => {
      const newPeople = new Set(filters.selectedPeople);
      if (newPeople.has(person)) {
        newPeople.delete(person);
      } else {
        newPeople.add(person);
      }
      return { ...filters, selectedPeople: newPeople };
    }),

    // Clear all filters
    clearAll: () => set({
      selectedKeywords: new Set(),
      selectedIssueTypes: new Set(),
      selectedPeople: new Set()
    }),

    // Check if any filters are active
    hasActiveFilters: (filters: Filters) =>
      filters.selectedKeywords.size > 0 ||
      filters.selectedIssueTypes.size > 0 ||
      filters.selectedPeople.size > 0
  };
}

export const filters = createFilterStore();

// Helper function to check if an issue matches current filters
export function issueMatchesFilters(
  issue: any,
  currentFilters: Filters
): boolean {
  // If no filters are active, show everything
  if (!filters.hasActiveFilters(currentFilters)) {
    return true;
  }

  // Check issue type filter
  if (currentFilters.selectedIssueTypes.size > 0) {
    if (!currentFilters.selectedIssueTypes.has(issue.classification.type)) {
      return false;
    }
  }

  // Check keyword filter (issue must have at least one selected keyword)
  if (currentFilters.selectedKeywords.size > 0) {
    const hasKeyword = issue.classification.keywords.some((kw: string) =>
      currentFilters.selectedKeywords.has(kw)
    );
    if (!hasKeyword) {
      return false;
    }
  }

  // Check people filter (issue must have at least one selected person)
  if (currentFilters.selectedPeople.size > 0) {
    const hasPerson = issue.people?.some((p: any) =>
      currentFilters.selectedPeople.has(p.name)
    );
    if (!hasPerson) {
      return false;
    }
  }

  return true;
}
