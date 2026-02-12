<script lang="ts">
  import type { IssueAnalysis } from '../lib/types';
  import { filters, issueMatchesFilters } from '../lib/store';
  import { getIssueTypeColor } from '../lib/colors';

  interface Props {
    issues: IssueAnalysis[];
  }

  let { issues }: Props = $props();
  let mounted = $state(false);
  let filteredIssues = $state<IssueAnalysis[]>([]);
  let currentPage = $state(0);
  const pageSize = 50;

  $effect(() => {
    const currentFilters = $filters;
    filteredIssues = issues.filter(issue => issueMatchesFilters(issue, currentFilters));
    currentPage = 0; // Reset to first page when filters change
  });

  const paginatedIssues = $derived(
    filteredIssues.slice(currentPage * pageSize, (currentPage + 1) * pageSize)
  );

  const totalPages = $derived(Math.ceil(filteredIssues.length / pageSize));

  function formatDate(dateStr: string | undefined): string {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString();
  }

  function exportToCSV() {
    // CSV header
    const headers = ['ID', 'Title', 'Type', 'Confidence', 'Keywords', 'Created', 'Updated', 'URL'];

    // CSV rows
    const rows = filteredIssues.map(issue => [
      issue.id,
      issue.title || '',
      issue.classification.type,
      issue.classification.confidence.toFixed(2),
      issue.classification.keywords.join('; '),
      issue.created_at || '',
      issue.updated_at || '',
      issue.url || ''
    ]);

    // Escape CSV values
    const escapeCSV = (value: string) => {
      if (value.includes(',') || value.includes('"') || value.includes('\n')) {
        return `"${value.replace(/"/g, '""')}"`;
      }
      return value;
    };

    // Build CSV content
    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(escapeCSV).join(','))
    ].join('\n');

    // Create download
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);

    link.setAttribute('href', url);
    link.setAttribute('download', `issues_export_${new Date().toISOString().split('T')[0]}.csv`);
    link.style.visibility = 'hidden';

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
</script>

<div class="issue-list">
  <div class="header">
    <h3>Issues ({filteredIssues.length})</h3>
    <div class="header-actions">
      <button class="export-btn" onclick={exportToCSV} disabled={filteredIssues.length === 0}>
        Export CSV ({filteredIssues.length})
      </button>
      {#if totalPages > 1}
        <div class="pagination">
          <button
            onclick={() => currentPage = Math.max(0, currentPage - 1)}
            disabled={currentPage === 0}>
            Previous
          </button>
          <span>Page {currentPage + 1} of {totalPages}</span>
          <button
            onclick={() => currentPage = Math.min(totalPages - 1, currentPage + 1)}
            disabled={currentPage >= totalPages - 1}>
            Next
          </button>
        </div>
      {/if}
    </div>
  </div>

  <div class="table-container">
    <table>
      <thead>
        <tr>
          <th>Title</th>
          <th>Type</th>
          <th>Keywords</th>
          <th>Date</th>
          <th>Link</th>
        </tr>
      </thead>
      <tbody>
        {#each paginatedIssues as issue}
          <tr>
            <td class="title">{issue.title || issue.id.substring(0, 8)}</td>
            <td>
              <span
                class="type-badge"
                style="background-color: {getIssueTypeColor(issue.classification.type)}">
                {issue.classification.type}
              </span>
            </td>
            <td class="keywords">
              {#if issue.classification.keywords.length > 0}
                {issue.classification.keywords.slice(0, 3).join(', ')}
                {#if issue.classification.keywords.length > 3}
                  <span class="more">+{issue.classification.keywords.length - 3}</span>
                {/if}
              {:else}
                -
              {/if}
            </td>
            <td class="date">{formatDate(issue.created_at)}</td>
            <td class="link">
              {#if issue.url}
                <a href={issue.url} target="_blank" rel="noopener noreferrer">
                  View
                </a>
              {:else}
                -
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>

  {#if filteredIssues.length === 0}
    <div class="empty">No issues match the current filters</div>
  {/if}
</div>

<style>
  .issue-list {
    margin: 20px 0;
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }

  h3 {
    font-size: 18px;
    font-weight: 600;
    color: #111827;
    margin: 0;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .export-btn {
    background: #10b981;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s;
  }

  .export-btn:hover:not(:disabled) {
    background: #059669;
  }

  .export-btn:disabled {
    background: #9ca3af;
    cursor: not-allowed;
  }

  .pagination {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .pagination button {
    background: #4f46e5;
    color: white;
    border: none;
    padding: 6px 12px;
    border-radius: 4px;
    font-size: 13px;
    cursor: pointer;
    transition: background 0.2s;
  }

  .pagination button:hover:not(:disabled) {
    background: #4338ca;
  }

  .pagination button:disabled {
    background: #9ca3af;
    cursor: not-allowed;
  }

  .pagination span {
    font-size: 13px;
    color: #6b7280;
  }

  .table-container {
    overflow-x: auto;
    border-radius: 8px;
    border: 1px solid #e5e7eb;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    background: white;
  }

  thead {
    background: #f9fafb;
    border-bottom: 2px solid #e5e7eb;
  }

  th {
    padding: 12px;
    text-align: left;
    font-size: 12px;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  tbody tr {
    border-bottom: 1px solid #f3f4f6;
  }

  tbody tr:hover {
    background: #f9fafb;
  }

  td {
    padding: 12px;
    font-size: 14px;
    color: #374151;
  }

  .title {
    font-weight: 500;
    max-width: 400px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .type-badge {
    display: inline-block;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    color: white;
    text-transform: uppercase;
  }

  .keywords {
    font-size: 13px;
    color: #6b7280;
    max-width: 300px;
  }

  .more {
    color: #9ca3af;
    font-size: 12px;
  }

  .date {
    font-size: 13px;
    color: #6b7280;
    white-space: nowrap;
  }

  .link a {
    color: #4f46e5;
    text-decoration: none;
    font-weight: 500;
    font-size: 13px;
  }

  .link a:hover {
    text-decoration: underline;
  }

  .empty {
    text-align: center;
    padding: 40px;
    color: #9ca3af;
    font-size: 14px;
  }
</style>
