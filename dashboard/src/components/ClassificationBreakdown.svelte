<script lang="ts">
  import { onMount } from 'svelte';
  import * as d3 from 'd3';
  import type { IssueAnalysis } from '../lib/types';

  interface Props {
    issues: IssueAnalysis[];
  }

  let { issues }: Props = $props();
  let container: HTMLDivElement;

  onMount(() => {
    const width = 400;
    const height = 400;
    const radius = Math.min(width, height) / 2;

    // Count by classification type
    const counts = d3.rollup(
      issues,
      v => v.length,
      d => d.classification.type
    );

    const data = Array.from(counts, ([type, count]) => ({ type, count }))
      .sort((a, b) => b.count - a.count);

    const color = d3.scaleOrdinal<string>()
      .domain(data.map(d => d.type))
      .range(['#4f46e5', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']);

    const svg = d3.select(container)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .append('g')
      .attr('transform', `translate(${width / 2},${height / 2})`);

    const pie = d3.pie<{type: string; count: number}>()
      .value(d => d.count)
      .sort(null);

    const arc = d3.arc<d3.PieArcDatum<{type: string; count: number}>>()
      .innerRadius(radius * 0.5)
      .outerRadius(radius * 0.8);

    const labelArc = d3.arc<d3.PieArcDatum<{type: string; count: number}>>()
      .innerRadius(radius * 0.9)
      .outerRadius(radius * 0.9);

    // Arcs
    svg.selectAll('path')
      .data(pie(data))
      .join('path')
      .attr('d', arc)
      .attr('fill', d => color(d.data.type))
      .attr('stroke', 'white')
      .attr('stroke-width', 2)
      .append('title')
      .text(d => `${d.data.type}: ${d.data.count} (${(d.data.count / issues.length * 100).toFixed(1)}%)`);

    // Labels
    svg.selectAll('text')
      .data(pie(data))
      .join('text')
      .attr('transform', d => `translate(${labelArc.centroid(d)})`)
      .attr('text-anchor', 'middle')
      .attr('font-size', '12px')
      .attr('font-weight', 'bold')
      .attr('fill', 'white')
      .style('text-shadow', '0 1px 2px rgba(0,0,0,0.6)')
      .text(d => d.data.count);

    // Legend
    const legend = svg.append('g')
      .attr('transform', `translate(${-width / 2 + 20}, ${-height / 2 + 20})`);

    data.forEach((d, i) => {
      const g = legend.append('g')
        .attr('transform', `translate(0, ${i * 20})`);

      g.append('rect')
        .attr('width', 12)
        .attr('height', 12)
        .attr('fill', color(d.type))
        .attr('rx', 2);

      g.append('text')
        .attr('x', 18)
        .attr('y', 6)
        .attr('dy', '0.35em')
        .attr('font-size', '11px')
        .text(`${d.type} (${d.count})`);
    });

    // Title
    svg.append('text')
      .attr('y', -height / 2 + 10)
      .attr('text-anchor', 'middle')
      .attr('font-size', '16px')
      .attr('font-weight', 'bold')
      .text('Issue Classification');
  });
</script>

<div>
  <div bind:this={container}></div>
</div>

<style>
  div {
    margin: 20px 0;
    display: flex;
    justify-content: center;
  }
</style>
