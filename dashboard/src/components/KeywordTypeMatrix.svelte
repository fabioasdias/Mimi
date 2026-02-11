<script lang="ts">
  import { onMount } from 'svelte';
  import * as d3 from 'd3';
  import type { IssueAnalysis } from '../lib/types';
  import { filters, issueMatchesFilters } from '../lib/store';

  interface Props {
    issues: IssueAnalysis[];
  }

  let { issues }: Props = $props();
  let container: HTMLDivElement;
  let error = $state('');
  let svg: any;
  let mounted = $state(false);

  // Subscribe to filters and trigger update
  $effect(() => {
    const currentFilters = $filters;  // Track dependency
    if (mounted) updateChart();
  });

  function updateChart() {
    try {
      // Clear existing content
      d3.select(container).selectAll('*').remove();

      // Filter issues based on current filters
      const filteredIssues = issues.filter(issue => issueMatchesFilters(issue, $filters));
      const margin = { top: 100, right: 20, bottom: 80, left: 150 };
      const cellSize = 30;

      // Build keyword × issue type matrix
      const keywordTypeMap = new Map<string, Map<string, number>>();
      const issueTypes = new Set<string>();

      filteredIssues.forEach(issue => {
        const issueType = issue.classification.type;
        issueTypes.add(issueType);

        issue.classification.keywords.forEach(keyword => {
          if (!keywordTypeMap.has(keyword)) {
            keywordTypeMap.set(keyword, new Map());
          }
          const typeMap = keywordTypeMap.get(keyword)!;
          typeMap.set(issueType, (typeMap.get(issueType) || 0) + 1);
        });
      });

      // Get top keywords by total count
      const topKeywords = Array.from(keywordTypeMap.entries())
        .map(([keyword, types]) => ({
          keyword,
          total: Array.from(types.values()).reduce((a, b) => a + b, 0)
        }))
        .sort((a, b) => b.total - a.total)
        .slice(0, 20)
        .map(d => d.keyword);

      const issueTypesList = Array.from(issueTypes).sort();

      const width = topKeywords.length * cellSize + margin.left + margin.right;
      const height = issueTypesList.length * cellSize + margin.top + margin.bottom;

      const svg = d3.select(container)
        .append('svg')
        .attr('width', width)
        .attr('height', height);

      const g = svg.append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);

      // Color scale
      const maxCount = d3.max(
        issueTypesList.flatMap(type =>
          topKeywords.map(keyword =>
            keywordTypeMap.get(keyword)?.get(type) || 0
          )
        )
      ) || 1;

      const colorScale = d3.scaleSequential(d3.interpolateYlOrRd)
        .domain([0, maxCount]);

      // Draw cells
      issueTypesList.forEach((type, i) => {
        topKeywords.forEach((keyword, j) => {
          const count = keywordTypeMap.get(keyword)?.get(type) || 0;

          g.append('rect')
            .attr('x', j * cellSize)
            .attr('y', i * cellSize)
            .attr('width', cellSize - 1)
            .attr('height', cellSize - 1)
            .attr('fill', count > 0 ? colorScale(count) : '#f3f4f6')
            .attr('stroke', '#fff')
            .attr('rx', 2)
            .style('cursor', 'pointer')
            .on('mouseover', function() {
              d3.select(this).attr('stroke', '#4f46e5').attr('stroke-width', 2);
            })
            .on('mouseout', function() {
              d3.select(this).attr('stroke', '#fff').attr('stroke-width', 1);
            })
            .append('title')
            .text(`${type} × ${keyword}: ${count} issues`);

          // Add count text if significant
          if (count > 0) {
            g.append('text')
              .attr('x', j * cellSize + cellSize / 2)
              .attr('y', i * cellSize + cellSize / 2)
              .attr('text-anchor', 'middle')
              .attr('dominant-baseline', 'middle')
              .attr('font-size', '10px')
              .attr('fill', count > maxCount / 2 ? 'white' : '#1f2937')
              .attr('pointer-events', 'none')
              .text(count);
          }
        });
      });

      // Y-axis labels (issue types)
      g.selectAll('text.type')
        .data(issueTypesList)
        .join('text')
        .attr('class', 'type')
        .attr('x', -5)
        .attr('y', (d, i) => i * cellSize + cellSize / 2)
        .attr('text-anchor', 'end')
        .attr('dominant-baseline', 'middle')
        .attr('font-size', '11px')
        .attr('font-weight', d => $filters.selectedIssueTypes.has(d) ? 'bold' : 'normal')
        .attr('fill', d => $filters.selectedIssueTypes.has(d) ? '#4f46e5' : '#000')
        .style('cursor', 'pointer')
        .text(d => d)
        .on('click', (_event, d) => filters.toggleIssueType(d))
        .append('title')
        .text('Click to filter by this issue type');

      // X-axis labels (keywords)
      g.selectAll('text.keyword')
        .data(topKeywords)
        .join('text')
        .attr('class', 'keyword')
        .attr('x', (d, i) => i * cellSize + cellSize / 2)
        .attr('y', -5)
        .attr('text-anchor', 'start')
        .attr('transform', (d, i) => `rotate(-45, ${i * cellSize + cellSize / 2}, -5)`)
        .attr('font-size', '11px')
        .attr('font-weight', d => $filters.selectedKeywords.has(d) ? 'bold' : 'normal')
        .attr('fill', d => $filters.selectedKeywords.has(d) ? '#4f46e5' : '#000')
        .style('cursor', 'pointer')
        .text(d => d.length > 20 ? d.substring(0, 17) + '...' : d)
        .on('click', (_event, d) => filters.toggleKeyword(d))
        .append('title')
        .text('Click to filter by this keyword');

      // Title
      svg.append('text')
        .attr('x', width / 2)
        .attr('y', 25)
        .attr('text-anchor', 'middle')
        .attr('font-size', '18px')
        .attr('font-weight', 'bold')
        .attr('fill', '#111827')
        .text('Issue Types × Keywords Heatmap');

      svg.append('text')
        .attr('x', width / 2)
        .attr('y', 50)
        .attr('text-anchor', 'middle')
        .attr('font-size', '12px')
        .attr('fill', '#6b7280')
        .text('Shows which keywords appear in which issue types (Top 20 keywords)');

      // Legend
      const legendWidth = 200;
      const legendHeight = 15;
      const legend = svg.append('g')
        .attr('transform', `translate(${margin.left}, ${height - margin.bottom + 20})`);

      const legendScale = d3.scaleLinear()
        .domain([0, maxCount])
        .range([0, legendWidth]);

      const legendAxis = d3.axisBottom(legendScale)
        .ticks(5)
        .tickFormat(d3.format('d'));

      // Gradient
      const defs = svg.append('defs');
      const gradient = defs.append('linearGradient')
        .attr('id', 'legend-gradient-type');

      gradient.selectAll('stop')
        .data(d3.range(0, 1.1, 0.1))
        .join('stop')
        .attr('offset', d => `${d * 100}%`)
        .attr('stop-color', d => colorScale(d * maxCount));

      legend.append('rect')
        .attr('width', legendWidth)
        .attr('height', legendHeight)
        .style('fill', 'url(#legend-gradient-type)');

      legend.append('g')
        .attr('transform', `translate(0, ${legendHeight})`)
        .call(legendAxis)
        .selectAll('text')
        .attr('font-size', '10px');

      legend.append('text')
        .attr('x', legendWidth / 2)
        .attr('y', -5)
        .attr('text-anchor', 'middle')
        .attr('font-size', '11px')
        .text('Issue count');
    } catch (e) {
      console.error('KeywordTypeMatrix error:', e);
      error = e instanceof Error ? e.message : String(e);
    }
  }

  onMount(() => {
    mounted = true;
    updateChart();
  });
</script>

<div>
  {#if error}
    <p style="color: red; padding: 20px;">Error: {error}</p>
  {/if}
  <div bind:this={container}></div>
</div>

<style>
  div {
    margin: 20px 0;
    display: flex;
    justify-content: center;
    background: white;
    border-radius: 12px;
    padding: 20px;
    overflow-x: auto;
  }
</style>
