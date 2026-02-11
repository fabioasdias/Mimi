<script lang="ts">
  import { onMount } from 'svelte';
  import * as d3 from 'd3';
  import type { IssueAnalysis, PeopleGraph } from '../lib/types';

  interface Props {
    issues: IssueAnalysis[];
    peopleGraph: PeopleGraph;
  }

  let { issues, peopleGraph }: Props = $props();
  let container: HTMLDivElement;
  let error = $state('');

  onMount(() => {
    try {
    const margin = { top: 120, right: 20, bottom: 80, left: 200 };
    const cellSize = 25;

    // Build person -> keyword matrix
    const personKeywordMap = new Map<string, Map<string, number>>();
    const allKeywords = new Set<string>();

    // Map person IDs to names
    const personNames = new Map<string, string>();
    peopleGraph.nodes.forEach(node => {
      personNames.set(node.id, node.label);
    });

    issues.forEach(issue => {
      issue.people?.forEach((person: any) => {
        // Use person ID from people_graph if available
        const personKey = `${person.source}:${person.source_id}`;
        const personName = person.name;

        if (!personKeywordMap.has(personName)) {
          personKeywordMap.set(personName, new Map());
        }
        const keywordMap = personKeywordMap.get(personName)!;

        issue.classification.keywords.forEach(keyword => {
          allKeywords.add(keyword);
          keywordMap.set(keyword, (keywordMap.get(keyword) || 0) + 1);
        });
      });
    });

    // Get top people and keywords
    const topPeople = Array.from(personKeywordMap.entries())
      .map(([person, keywords]) => ({
        person,
        total: Array.from(keywords.values()).reduce((a, b) => a + b, 0)
      }))
      .sort((a, b) => b.total - a.total)
      .slice(0, 15)
      .map(d => d.person);

    const keywordCounts = new Map<string, number>();
    issues.forEach(issue => {
      issue.classification.keywords.forEach(kw => {
        keywordCounts.set(kw, (keywordCounts.get(kw) || 0) + 1);
      });
    });

    const topKeywords = Array.from(keywordCounts.entries())
      .sort(([, a], [, b]) => b - a)
      .slice(0, 20)
      .map(([kw]) => kw);

    const width = topKeywords.length * cellSize + margin.left + margin.right;
    const height = topPeople.length * cellSize + margin.top + margin.bottom;

    const svg = d3.select(container)
      .append('svg')
      .attr('width', width)
      .attr('height', height);

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Color scale
    const maxCount = d3.max(
      topPeople.flatMap(person =>
        topKeywords.map(keyword =>
          personKeywordMap.get(person)?.get(keyword) || 0
        )
      )
    ) || 1;

    const colorScale = d3.scaleSequential(d3.interpolateBlues)
      .domain([0, maxCount]);

    // Draw cells
    topPeople.forEach((person, i) => {
      topKeywords.forEach((keyword, j) => {
        const count = personKeywordMap.get(person)?.get(keyword) || 0;

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
          .text(`${person} × ${keyword}: ${count} issues`);

        // Add count text if significant
        if (count > 0) {
          g.append('text')
            .attr('x', j * cellSize + cellSize / 2)
            .attr('y', i * cellSize + cellSize / 2)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('font-size', '9px')
            .attr('fill', count > maxCount / 2 ? 'white' : '#1f2937')
            .attr('pointer-events', 'none')
            .text(count);
        }
      });
    });

    // Y-axis labels (people)
    g.selectAll('text.person')
      .data(topPeople)
      .join('text')
      .attr('class', 'person')
      .attr('x', -5)
      .attr('y', (d, i) => i * cellSize + cellSize / 2)
      .attr('text-anchor', 'end')
      .attr('dominant-baseline', 'middle')
      .attr('font-size', '11px')
      .text(d => d.length > 25 ? d.substring(0, 22) + '...' : d);

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
      .text(d => d.length > 20 ? d.substring(0, 17) + '...' : d);

    // Title
    svg.append('text')
      .attr('x', width / 2)
      .attr('y', 25)
      .attr('text-anchor', 'middle')
      .attr('font-size', '18px')
      .attr('font-weight', 'bold')
      .attr('fill', '#111827')
      .text('People × Keywords Heatmap');

    svg.append('text')
      .attr('x', width / 2)
      .attr('y', 50)
      .attr('text-anchor', 'middle')
      .attr('font-size', '12px')
      .attr('fill', '#6b7280')
      .text('Shows how many issues each person has worked on for each keyword (Top 15 people × Top 20 keywords)');

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
      .attr('id', 'legend-gradient');

    gradient.selectAll('stop')
      .data(d3.range(0, 1.1, 0.1))
      .join('stop')
      .attr('offset', d => `${d * 100}%`)
      .attr('stop-color', d => colorScale(d * maxCount));

    legend.append('rect')
      .attr('width', legendWidth)
      .attr('height', legendHeight)
      .style('fill', 'url(#legend-gradient)');

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
      console.error('PeopleKeywordMatrix error:', e);
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
