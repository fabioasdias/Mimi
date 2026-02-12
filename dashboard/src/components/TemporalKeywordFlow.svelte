<script lang="ts">
  import { onMount } from 'svelte';
  import * as d3 from 'd3';
  import type { IssueAnalysis } from '../lib/types';
  import { filters, issueMatchesFilters } from '../lib/store';
  import { getIssueTypeColor, ISSUE_TYPES, ISSUE_TYPE_COLORS } from '../lib/colors';

  interface Props {
    issues: IssueAnalysis[];
  }

  let { issues }: Props = $props();
  let container: HTMLDivElement;
  let mounted = $state(false);

  // Subscribe to filters and trigger update
  $effect(() => {
    const currentFilters = $filters;
    if (mounted) updateChart();
  });

  function updateChart() {
    d3.select(container).selectAll('*').remove();

    // Filter issues and ensure they have timestamps
    const filteredIssues = issues
      .filter(issue => issueMatchesFilters(issue, $filters))
      .filter(issue => issue.created_at);

    if (filteredIssues.length === 0) {
      d3.select(container).append('p')
        .style('text-align', 'center')
        .style('color', '#6b7280')
        .text('No issues with timestamps found. Run analyze with updated code to include timestamps.');
      return;
    }

    const margin = { top: 60, right: 200, bottom: 80, left: 150 };

    // Parse dates
    const parseDate = d3.isoParse;
    const issuesWithDates = filteredIssues.map(issue => ({
      ...issue,
      date: parseDate(issue.created_at!)!
    }));

    // Get top keywords
    const keywordCounts = new Map<string, number>();
    filteredIssues.forEach(issue => {
      issue.classification.keywords.forEach(kw => {
        keywordCounts.set(kw, (keywordCounts.get(kw) || 0) + 1);
      });
    });
    const topKeywords = Array.from(keywordCounts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 12)
      .map(([kw]) => kw);

    // Create time bins - adaptive granularity based on date range
    const dateExtent = d3.extent(issuesWithDates, d => d.date) as [Date, Date];
    const daySpan = (dateExtent[1].getTime() - dateExtent[0].getTime()) / (1000 * 60 * 60 * 24);

    // Choose bin interval: day, week, or month based on span
    let binInterval: d3.TimeInterval;
    let binLabel: string;
    if (daySpan <= 30) {
      binInterval = d3.timeDay;
      binLabel = 'day';
    } else if (daySpan <= 180) {
      binInterval = d3.timeWeek;
      binLabel = 'week';
    } else {
      binInterval = d3.timeMonth;
      binLabel = 'month';
    }

    const timeBins = binInterval.range(dateExtent[0], binInterval.offset(dateExtent[1], 1));

    // Fixed width - cells will scale to fit
    const maxContentWidth = 1050; // Fixed max width for content
    const width = maxContentWidth;
    const height = 500 - margin.top - margin.bottom;

    // Now create SVG with calculated dimensions
    const svg = d3.select(container)
      .append('svg')
      .attr('width', width + margin.left + margin.right)
      .attr('height', height + margin.top + margin.bottom)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Build heatmap data structure
    interface HeatmapCell {
      keyword: string;
      date: Date;
      typeCounts: Map<string, number>;
      total: number;
      dominantType: string;
    }

    const heatmapData: HeatmapCell[] = [];

    topKeywords.forEach(keyword => {
      timeBins.forEach(binDate => {
        const nextBinDate = binInterval.offset(binDate, 1);
        const issuesInCell = issuesWithDates.filter(issue =>
          issue.date >= binDate &&
          issue.date < nextBinDate &&
          issue.classification.keywords.includes(keyword)
        );

        const typeCounts = new Map<string, number>();
        issuesInCell.forEach(issue => {
          const type = issue.classification.type;
          typeCounts.set(type, (typeCounts.get(type) || 0) + 1);
        });

        const total = issuesInCell.length;
        let dominantType = '';
        let maxCount = 0;
        typeCounts.forEach((count, type) => {
          if (count > maxCount) {
            maxCount = count;
            dominantType = type;
          }
        });

        heatmapData.push({
          keyword,
          date: binDate,
          typeCounts,
          total,
          dominantType
        });
      });
    });

    // Scales
    const x = d3.scaleBand()
      .domain(timeBins.map(d => d.toISOString()))
      .range([0, width])
      .padding(0.05);

    const y = d3.scaleBand()
      .domain(topKeywords)
      .range([0, height])
      .padding(0.1);

    // Use 95th percentile instead of max to avoid outlier domination
    const nonZeroCounts = heatmapData.filter(d => d.total > 0).map(d => d.total).sort((a, b) => a - b);
    const p95Index = Math.floor(nonZeroCounts.length * 0.95);
    const maxTotal = nonZeroCounts[p95Index] || nonZeroCounts[nonZeroCounts.length - 1] || 1;

    // Use square root scale for better visual distribution
    const opacityScale = d3.scaleSqrt()
      .domain([0, maxTotal])
      .range([0.2, 1.0])
      .clamp(true);

    // Draw heatmap cells
    heatmapData.forEach(cell => {
      const cellWidth = x.bandwidth();
      const cellHeight = y.bandwidth();
      const cellX = x(cell.date.toISOString()) || 0;
      const cellY = y(cell.keyword) || 0;

      if (cell.total === 0) {
        // Empty cell
        svg.append('rect')
          .attr('x', cellX)
          .attr('y', cellY)
          .attr('width', cellWidth)
          .attr('height', cellHeight)
          .attr('fill', '#f3f4f6')
          .attr('stroke', '#e5e7eb')
          .attr('stroke-width', 0.5);
        return;
      }

      // Draw stacked bars in each cell showing type distribution
      const types = Array.from(cell.typeCounts.entries())
        .sort((a, b) => b[1] - a[1]);

      let offset = 0;
      types.forEach(([type, count]) => {
        const barHeight = (count / cell.total) * cellHeight;

        const baseOpacity = opacityScale(cell.total);

        svg.append('rect')
          .attr('x', cellX)
          .attr('y', cellY + offset)
          .attr('width', cellWidth)
          .attr('height', barHeight)
          .attr('fill', getIssueTypeColor(type))
          .attr('opacity', baseOpacity)
          .attr('stroke', '#fff')
          .attr('stroke-width', 0.5)
          .style('cursor', 'pointer')
          .on('click', () => {
            filters.toggleKeyword(cell.keyword);
          })
          .on('mouseover', function() {
            d3.select(this).attr('opacity', '1');
          })
          .on('mouseout', function() {
            d3.select(this).attr('opacity', String(baseOpacity));
          })
          .append('title')
          .text(() => {
            const typeBreakdown = types.map(([t, c]) => `  ${t}: ${c}`).join('\n');
            return `${cell.keyword}\n${cell.date.toLocaleDateString()}\nTotal: ${cell.total}\n${typeBreakdown}\n\nClick to filter by keyword`;
          });

        offset += barHeight;
      });
    });

    // X-axis (time) - adaptive tick frequency
    const tickInterval = Math.max(1, Math.ceil(timeBins.length / 12));
    svg.append('g')
      .attr('transform', `translate(0,${height})`)
      .call(d3.axisBottom(x)
        .tickValues(x.domain().filter((_, i) => i % tickInterval === 0))
        .tickFormat(d => {
          const date = new Date(d);
          if (binLabel === 'month') {
            return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
          } else if (binLabel === 'week') {
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
          } else {
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
          }
        })
      )
      .selectAll('text')
      .attr('transform', 'rotate(-45)')
      .style('text-anchor', 'end')
      .attr('font-size', '11px');

    // Y-axis (keywords) - clickable
    svg.append('g')
      .call(d3.axisLeft(y))
      .selectAll('text')
      .attr('font-size', '12px')
      .attr('font-weight', d => $filters.selectedKeywords.has(d) ? 'bold' : 'normal')
      .attr('fill', d => $filters.selectedKeywords.has(d) ? '#4f46e5' : '#000')
      .style('cursor', 'pointer')
      .on('click', (_event, d) => filters.toggleKeyword(d))
      .append('title')
      .text('Click to filter by this keyword');

    // Title
    svg.append('text')
      .attr('x', width / 2)
      .attr('y', -30)
      .attr('text-anchor', 'middle')
      .attr('font-size', '16px')
      .attr('font-weight', 'bold')
      .text('Keyword Activity Heatmap');

    svg.append('text')
      .attr('x', width / 2)
      .attr('y', -10)
      .attr('text-anchor', 'middle')
      .attr('font-size', '12px')
      .attr('fill', '#6b7280')
      .text(`Each cell shows issue type distribution (${binLabel}ly bins) | Brightness = volume | Click to filter`);

    // Legend
    const legend = svg.append('g')
      .attr('transform', `translate(${width + 20}, 0)`);

    legend.append('text')
      .attr('font-size', '12px')
      .attr('font-weight', 'bold')
      .attr('fill', '#374151')
      .text('Issue Types');

    ISSUE_TYPES.forEach((type, i) => {
      const legendRow = legend.append('g')
        .attr('transform', `translate(0, ${i * 25 + 20})`)
        .style('cursor', 'pointer')
        .on('click', () => filters.toggleIssueType(type));

      legendRow.append('rect')
        .attr('width', 16)
        .attr('height', 16)
        .attr('fill', getIssueTypeColor(type))
        .attr('opacity', 0.7)
        .attr('stroke', $filters.selectedIssueTypes.has(type) ? '#000' : '#fff')
        .attr('stroke-width', $filters.selectedIssueTypes.has(type) ? 2 : 1);

      legendRow.append('text')
        .attr('x', 22)
        .attr('y', 12)
        .attr('font-size', '11px')
        .attr('font-weight', $filters.selectedIssueTypes.has(type) ? 'bold' : 'normal')
        .text(type)
        .append('title')
        .text('Click to filter');
    });
  }

  onMount(() => {
    mounted = true;
    updateChart();
  });
</script>

<div>
  <div bind:this={container}></div>
</div>

<style>
  div {
    margin: 20px 0;
  }
</style>
