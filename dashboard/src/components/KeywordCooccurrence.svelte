<script lang="ts">
  import { onMount } from 'svelte';
  import * as d3 from 'd3';
  import type { KeywordGraph } from '../lib/types';

  interface Props {
    keywordGraph: KeywordGraph;
  }

  let { keywordGraph }: Props = $props();
  let container: HTMLDivElement;
  let error = $state('');

  onMount(() => {
    try {
      const margin = { top: 100, right: 20, bottom: 80, left: 150 };
      const cellSize = 25;

      // Get top keywords
      const topKeywords = keywordGraph.nodes
        .sort((a, b) => b.issue_count - a.issue_count)
        .slice(0, 20)
        .map(n => n.id);

      const topKeywordsSet = new Set(topKeywords);

      // Build co-occurrence matrix
      const cooccurrenceMap = new Map<string, Map<string, number>>();

      topKeywords.forEach(kw => {
        cooccurrenceMap.set(kw, new Map());
      });

      keywordGraph.edges
        .filter(e => topKeywordsSet.has(e.from) && topKeywordsSet.has(e.to))
        .forEach(edge => {
          cooccurrenceMap.get(edge.from)?.set(edge.to, edge.co_occurrence);
          cooccurrenceMap.get(edge.to)?.set(edge.from, edge.co_occurrence);
        });

      const width = topKeywords.length * cellSize + margin.left + margin.right;
      const height = topKeywords.length * cellSize + margin.top + margin.bottom;

      const svg = d3.select(container)
        .append('svg')
        .attr('width', width)
        .attr('height', height);

      const g = svg.append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);

      // Color scale
      const maxCount = d3.max(
        topKeywords.flatMap(kw1 =>
          topKeywords.map(kw2 =>
            cooccurrenceMap.get(kw1)?.get(kw2) || 0
          )
        )
      ) || 1;

      const colorScale = d3.scaleSequential(d3.interpolatePurples)
        .domain([0, maxCount]);

      // Draw cells
      topKeywords.forEach((kw1, i) => {
        topKeywords.forEach((kw2, j) => {
          const count = cooccurrenceMap.get(kw1)?.get(kw2) || 0;

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
            .text(`${kw1} & ${kw2}: ${count} shared issues`);

          // Add count text if significant
          if (count > 2) {
            g.append('text')
              .attr('x', j * cellSize + cellSize / 2)
              .attr('y', i * cellSize + cellSize / 2)
              .attr('text-anchor', 'middle')
              .attr('dominant-baseline', 'middle')
              .attr('font-size', '8px')
              .attr('fill', count > maxCount / 2 ? 'white' : '#1f2937')
              .attr('pointer-events', 'none')
              .text(count);
          }
        });
      });

      // Y-axis labels
      g.selectAll('text.keyword-y')
        .data(topKeywords)
        .join('text')
        .attr('class', 'keyword-y')
        .attr('x', -5)
        .attr('y', (d, i) => i * cellSize + cellSize / 2)
        .attr('text-anchor', 'end')
        .attr('dominant-baseline', 'middle')
        .attr('font-size', '10px')
        .text(d => d.length > 20 ? d.substring(0, 17) + '...' : d);

      // X-axis labels
      g.selectAll('text.keyword-x')
        .data(topKeywords)
        .join('text')
        .attr('class', 'keyword-x')
        .attr('x', (d, i) => i * cellSize + cellSize / 2)
        .attr('y', -5)
        .attr('text-anchor', 'start')
        .attr('transform', (d, i) => `rotate(-45, ${i * cellSize + cellSize / 2}, -5)`)
        .attr('font-size', '10px')
        .text(d => d.length > 20 ? d.substring(0, 17) + '...' : d);

      // Title
      svg.append('text')
        .attr('x', width / 2)
        .attr('y', 25)
        .attr('text-anchor', 'middle')
        .attr('font-size', '18px')
        .attr('font-weight', 'bold')
        .attr('fill', '#111827')
        .text('Keyword Co-occurrence Heatmap');

      svg.append('text')
        .attr('x', width / 2)
        .attr('y', 50)
        .attr('text-anchor', 'middle')
        .attr('font-size', '12px')
        .attr('fill', '#6b7280')
        .text('Shows how often keywords appear together in the same issues (Top 20 × Top 20)');

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
        .attr('id', 'legend-gradient-cooccur');

      gradient.selectAll('stop')
        .data(d3.range(0, 1.1, 0.1))
        .join('stop')
        .attr('offset', d => `${d * 100}%`)
        .attr('stop-color', d => colorScale(d * maxCount));

      legend.append('rect')
        .attr('width', legendWidth)
        .attr('height', legendHeight)
        .style('fill', 'url(#legend-gradient-cooccur)');

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
        .text('Co-occurrence count');
    } catch (e) {
      console.error('KeywordCooccurrence error:', e);
      error = e instanceof Error ? e.message : String(e);
    }
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
