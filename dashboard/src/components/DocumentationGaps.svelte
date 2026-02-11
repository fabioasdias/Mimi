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
  let mounted = $state(false);

  // Subscribe to filters and trigger update
  $effect(() => {
    const currentFilters = $filters;  // Track dependency
    if (mounted) updateChart();
  });

  function updateChart() {
    d3.select(container).selectAll('*').remove();

    // Filter issues first
    const filteredIssues = issues.filter(issue => issueMatchesFilters(issue, $filters));
    const margin = { top: 20, right: 20, bottom: 60, left: 150 };
    const width = 800 - margin.left - margin.right;
    const height = 500 - margin.top - margin.bottom;

    // Filter for documentation-related issues (inquiries and clarifications)
    const docIssues = filteredIssues.filter(
      i => i.classification.type === 'inquiry' || i.classification.type === 'clarification'
    );

    // Count by keyword
    const keywordMap = new Map<string, {inquiries: number; clarifications: number}>();

    docIssues.forEach(issue => {
      issue.classification.keywords.forEach(keyword => {
        if (!keywordMap.has(keyword)) {
          keywordMap.set(keyword, { inquiries: 0, clarifications: 0 });
        }
        const counts = keywordMap.get(keyword)!;
        if (issue.classification.type === 'inquiry') {
          counts.inquiries++;
        } else {
          counts.clarifications++;
        }
      });
    });

    const data = Array.from(keywordMap, ([keyword, counts]) => ({
      keyword,
      inquiries: counts.inquiries,
      clarifications: counts.clarifications,
      total: counts.inquiries + counts.clarifications
    }))
      .filter(d => d.total > 0)
      .sort((a, b) => b.total - a.total)
      .slice(0, 10); // Top 10

    if (data.length === 0) {
      d3.select(container).append('p').text('No documentation gaps found');
      return;
    }

    const svg = d3.select(container)
      .append('svg')
      .attr('width', width + margin.left + margin.right)
      .attr('height', height + margin.top + margin.bottom)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const x = d3.scaleLinear()
      .domain([0, d3.max(data, d => d.total) || 0])
      .range([0, width]);

    const y = d3.scaleBand()
      .domain(data.map(d => d.keyword))
      .range([0, height])
      .padding(0.3);

    const barHeight = y.bandwidth();

    // Clarifications (darker)
    svg.selectAll('rect.clarification')
      .data(data)
      .join('rect')
      .attr('class', 'clarification')
      .attr('x', 0)
      .attr('y', d => y(d.keyword)!)
      .attr('width', d => x(d.clarifications))
      .attr('height', barHeight)
      .attr('fill', '#dc2626')
      .attr('rx', 4);

    // Inquiries (lighter, stacked)
    svg.selectAll('rect.inquiry')
      .data(data)
      .join('rect')
      .attr('class', 'inquiry')
      .attr('x', d => x(d.clarifications))
      .attr('y', d => y(d.keyword)!)
      .attr('width', d => x(d.inquiries))
      .attr('height', barHeight)
      .attr('fill', '#f97316')
      .attr('rx', 4);

    // Total labels
    svg.selectAll('text.total')
      .data(data)
      .join('text')
      .attr('class', 'total')
      .attr('x', d => x(d.total) + 5)
      .attr('y', d => y(d.keyword)! + barHeight / 2)
      .attr('dy', '0.35em')
      .text(d => d.total)
      .attr('font-size', '12px')
      .attr('fill', '#374151');

    // Y axis
    svg.append('g')
      .call(d3.axisLeft(y))
      .selectAll('text')
      .attr('font-size', '12px');

    // Title
    svg.append('text')
      .attr('x', width / 2)
      .attr('y', -5)
      .attr('text-anchor', 'middle')
      .attr('font-size', '16px')
      .attr('font-weight', 'bold')
      .text('Documentation Gaps (Inquiries + Clarifications)');

    // Legend
    const legend = svg.append('g')
      .attr('transform', `translate(${width - 150}, 10)`);

    legend.append('rect')
      .attr('width', 12)
      .attr('height', 12)
      .attr('fill', '#dc2626')
      .attr('rx', 2);

    legend.append('text')
      .attr('x', 18)
      .attr('y', 6)
      .attr('dy', '0.35em')
      .attr('font-size', '11px')
      .text('Clarifications');

    legend.append('rect')
      .attr('y', 20)
      .attr('width', 12)
      .attr('height', 12)
      .attr('fill', '#f97316')
      .attr('rx', 2);

    legend.append('text')
      .attr('x', 18)
      .attr('y', 26)
      .attr('dy', '0.35em')
      .attr('font-size', '11px')
      .text('Inquiries');
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
