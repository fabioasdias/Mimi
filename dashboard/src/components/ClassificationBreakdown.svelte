<script lang="ts">
  import { onMount } from 'svelte';
  import * as d3 from 'd3';
  import type { IssueAnalysis } from '../lib/types';
  import { filters, issueMatchesFilters } from '../lib/store';
  import { getIssueTypeColor, ISSUE_TYPES } from '../lib/colors';

  interface Props {
    issues: IssueAnalysis[];
  }

  let { issues }: Props = $props();
  let container: HTMLDivElement;
  let svg: any;
  let mounted = $state(false);

  // Subscribe to filters and trigger update
  $effect(() => {
    const currentFilters = $filters;  // Track dependency
    if (mounted) updateChart();
  });

  function updateChart() {
    // Filter issues based on current filters
    const filteredIssues = issues.filter(issue => issueMatchesFilters(issue, $filters));

    const width = 400;
    const height = 400;
    const radius = Math.min(width, height) / 2;

    // Count by classification type
    const counts = d3.rollup(
      filteredIssues,
      v => v.length,
      d => d.classification.type
    );

    const data = Array.from(counts, ([type, count]) => ({ type, count }))
      .sort((a, b) => b.count - a.count);

    const color = (type: string) => getIssueTypeColor(type);

    const pie = d3.pie<{type: string; count: number}>()
      .value(d => d.count)
      .sort(null);

    const arc = d3.arc<d3.PieArcDatum<{type: string; count: number}>>()
      .innerRadius(radius * 0.5)
      .outerRadius(radius * 0.8);

    const labelArc = d3.arc<d3.PieArcDatum<{type: string; count: number}>>()
      .innerRadius(radius * 0.9)
      .outerRadius(radius * 0.9);

    // Clear and redraw
    d3.select(svg).selectAll('*').remove();
    const g = d3.select(svg)
      .attr('transform', `translate(${width / 2},${height / 2})`);

    // Arcs with click handler
    g.selectAll('path')
      .data(pie(data))
      .join('path')
      .attr('d', arc)
      .attr('fill', d => color(d.data.type))
      .attr('stroke', d => $filters.selectedIssueTypes.has(d.data.type) ? '#000' : 'white')
      .attr('stroke-width', d => $filters.selectedIssueTypes.has(d.data.type) ? 3 : 2)
      .attr('opacity', d => {
        if ($filters.selectedIssueTypes.size === 0) return 1;
        return $filters.selectedIssueTypes.has(d.data.type) ? 1 : 0.3;
      })
      .style('cursor', 'pointer')
      .on('click', function(_event, d) {
        filters.toggleIssueType(d.data.type);
      })
      .on('mouseover', function() {
        d3.select(this).attr('opacity', 1);
      })
      .on('mouseout', function(event, d) {
        if ($filters.selectedIssueTypes.size === 0 || $filters.selectedIssueTypes.has(d.data.type)) {
          d3.select(this).attr('opacity', 1);
        } else {
          d3.select(this).attr('opacity', 0.3);
        }
      })
      .append('title')
      .text(d => `${d.data.type}: ${d.data.count} (${(d.data.count / filteredIssues.length * 100).toFixed(1)}%) - Click to filter`);

    // Labels
    g.selectAll('text.value')
      .data(pie(data))
      .join('text')
      .attr('class', 'value')
      .attr('transform', d => `translate(${labelArc.centroid(d)})`)
      .attr('text-anchor', 'middle')
      .attr('font-size', '12px')
      .attr('font-weight', 'bold')
      .attr('fill', 'white')
      .style('text-shadow', '0 1px 2px rgba(0,0,0,0.6)')
      .style('pointer-events', 'none')
      .text(d => d.data.count);

    // Legend
    const legend = g.append('g')
      .attr('transform', `translate(${-width / 2 + 20}, ${-height / 2 + 20})`);

    data.forEach((d, i) => {
      const legendG = legend.append('g')
        .attr('transform', `translate(0, ${i * 20})`)
        .style('cursor', 'pointer')
        .on('click', () => filters.toggleIssueType(d.type));

      legendG.append('rect')
        .attr('width', 12)
        .attr('height', 12)
        .attr('fill', color(d.type))
        .attr('rx', 2)
        .attr('stroke', $filters.selectedIssueTypes.has(d.type) ? '#000' : 'none')
        .attr('stroke-width', 2);

      legendG.append('text')
        .attr('x', 18)
        .attr('y', 6)
        .attr('dy', '0.35em')
        .attr('font-size', '11px')
        .attr('font-weight', $filters.selectedIssueTypes.has(d.type) ? 'bold' : 'normal')
        .text(`${d.type} (${d.count})`);
    });

    // Title
    g.append('text')
      .attr('y', -height / 2 + 10)
      .attr('text-anchor', 'middle')
      .attr('font-size', '16px')
      .attr('font-weight', 'bold')
      .text('Issue Classification');
  }

  onMount(() => {
    const width = 400;
    const height = 400;

    const svgElement = d3.select(container)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .append('g');

    svg = svgElement.node();
    mounted = true;
    updateChart();
  });
</script>

<div>
  <div bind:this={container}></div>
  {#if $filters.selectedIssueTypes.size > 0}
    <div class="filter-info">
      <button class="clear-btn" onclick={() => filters.clearAll()}>
        Clear filters ({$filters.selectedIssueTypes.size} selected)
      </button>
    </div>
  {/if}
</div>

<style>
  div {
    margin: 20px 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }

  .filter-info {
    margin-top: 10px;
  }

  .clear-btn {
    background: #ef4444;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 12px;
    cursor: pointer;
    transition: background 0.2s;
  }

  .clear-btn:hover {
    background: #dc2626;
  }
</style>
