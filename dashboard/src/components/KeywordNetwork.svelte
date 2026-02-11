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
    const width = 1200;
    const height = 700;

    // Filter to top keywords and their connections
    const topKeywords = keywordGraph.nodes
      .sort((a, b) => b.issue_count - a.issue_count)
      .slice(0, 30)
      .map(n => n.id);

    const topKeywordsSet = new Set(topKeywords);

    const nodes = keywordGraph.nodes
      .filter(n => topKeywordsSet.has(n.id))
      .map(n => ({ ...n, x: 0, y: 0, vx: 0, vy: 0 }));

    const edges = keywordGraph.edges
      .filter(e => topKeywordsSet.has(e.from) && topKeywordsSet.has(e.to))
      .filter(e => e.co_occurrence > 1) // Only show meaningful connections
      .map(e => ({ source: e.from, target: e.to, co_occurrence: e.co_occurrence })); // Map to d3 format

    if (nodes.length === 0) {
      d3.select(container).append('p').text('No keyword relationships found');
      return;
    }

    const svg = d3.select(container)
      .append('svg')
      .attr('width', width)
      .attr('height', height);

    const g = svg.append('g');

    // Zoom behavior
    const zoom = d3.zoom()
      .scaleExtent([0.5, 3])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });

    svg.call(zoom as any);

    // Size scale
    const sizeScale = d3.scaleSqrt()
      .domain([0, d3.max(nodes, d => d.issue_count) || 1])
      .range([5, 30]);

    // Edge width scale
    const edgeWidth = d3.scaleLinear()
      .domain([0, d3.max(edges, d => d.co_occurrence) || 1])
      .range([1, 8]);

    // Force simulation
    const simulation = d3.forceSimulation(nodes as any)
      .force('link', d3.forceLink(edges)
        .id((d: any) => d.id)
        .distance(100)
        .strength(d => (d as any).co_occurrence / 20))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius((d: any) => sizeScale(d.issue_count) + 5));

    // Draw edges
    const link = g.append('g')
      .selectAll('line')
      .data(edges)
      .join('line')
      .attr('stroke', '#94a3b8')
      .attr('stroke-width', d => edgeWidth(d.co_occurrence))
      .attr('stroke-opacity', 0.6);

    // Draw nodes
    const node = g.append('g')
      .selectAll('g')
      .data(nodes)
      .join('g')
      .call(d3.drag()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended) as any);

    node.append('circle')
      .attr('r', d => sizeScale(d.issue_count))
      .attr('fill', '#4f46e5')
      .attr('stroke', '#fff')
      .attr('stroke-width', 2);

    node.append('text')
      .text(d => d.id)
      .attr('font-size', '11px')
      .attr('dx', d => sizeScale(d.issue_count) + 5)
      .attr('dy', '0.35em')
      .attr('fill', '#1f2937');

    node.append('title')
      .text(d => `${d.id}\n${d.issue_count} issues`);

    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);

      node.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    function dragstarted(event: any) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      event.subject.fx = event.subject.x;
      event.subject.fy = event.subject.y;
    }

    function dragged(event: any) {
      event.subject.fx = event.x;
      event.subject.fy = event.y;
    }

    function dragended(event: any) {
      if (!event.active) simulation.alphaTarget(0);
      event.subject.fx = null;
      event.subject.fy = null;
    }

    // Title
    svg.append('text')
      .attr('x', width / 2)
      .attr('y', 30)
      .attr('text-anchor', 'middle')
      .attr('font-size', '18px')
      .attr('font-weight', 'bold')
      .attr('fill', '#111827')
      .text('Keyword Co-occurrence Network (Top 30)');

    // Info text
    svg.append('text')
      .attr('x', width / 2)
      .attr('y', 55)
      .attr('text-anchor', 'middle')
      .attr('font-size', '12px')
      .attr('fill', '#6b7280')
      .text('Line thickness = how often keywords appear together | Circle size = issue count | Drag to explore');
    } catch (e) {
      console.error('KeywordNetwork error:', e);
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
    overflow: hidden;
  }
</style>
