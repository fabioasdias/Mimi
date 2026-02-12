/**
 * Standardized color scheme for issue types across all visualizations
 */
export const ISSUE_TYPE_COLORS: Record<string, string> = {
  'outage': '#dc2626',        // Red
  'defect': '#f97316',        // Orange
  'enhancement': '#10b981',    // Green
  'inquiry': '#3b82f6',       // Blue
  'routing_issue': '#64748b', // Gray
  'action': '#ec4899'         // Pink
};

/**
 * Get color for an issue type with fallback
 */
export function getIssueTypeColor(type: string): string {
  return ISSUE_TYPE_COLORS[type] || '#9ca3af'; // Default gray
}

/**
 * Get all issue types in a consistent order
 */
export const ISSUE_TYPES = [
  'outage',
  'defect',
  'enhancement',
  'inquiry',
  'routing_issue',
  'action'
] as const;
