<script lang="ts">
  import { onMount } from 'svelte';
  import * as d3 from 'd3';
  import type { KeywordGraph } from '../lib/types';

  interface Props {
    keywordGraph: KeywordGraph;
  }

  let { keywordGraph }: Props = $props();
  let container: HTMLDivElement;

  onMount(() => {
    const margin = { top: 20, right: 20, bottom: 60, left: 120 };
    const width = 800 - margin.left - margin.right;
    const height = 400 - margin.top - margin.bottom;

    // Sort keywords by issue count
    const sortedKeywords = [...keywordGraph.nodes]
      .sort((a, b) => b.issue_count - a.issue_count)
      .slice(0, 15); // Top 15

    const svg = d3.select(container)
      .append('svg')
      .attr('width', width + margin.left + margin.right)
      .attr('height', height + margin.top + margin.bottom)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const x = d3.scaleLinear()
      .domain([0, d3.max(sortedKeywords, d => d.issue_count) || 0])
      .range([0, width]);

    const y = d3.scaleBand()
      .domain(sortedKeywords.map(d => d.id))
      .range([0, height])
      .padding(0.2);

    // Bars
    svg.selectAll('rect')
      .data(sortedKeywords)
      .join('rect')
      .attr('x', 0)
      .attr('y', d => y(d.id)!)
      .attr('width', d => x(d.issue_count))
      .attr('height', y.bandwidth())
      .attr('fill', '#4f46e5')
      .attr('rx', 4);

    // Labels
    svg.selectAll('text.label')
      .data(sortedKeywords)
      .join('text')
      .attr('class', 'label')
      .attr('x', d => x(d.issue_count) + 5)
      .attr('y', d => y(d.id)! + y.bandwidth() / 2)
      .attr('dy', '0.35em')
      .text(d => d.issue_count)
      .attr('fill', '#374151')
      .attr('font-size', '12px');

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
      .text('Issues by Keyword (Top 15)');
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
