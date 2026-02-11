<script lang="ts">
  import { onMount } from 'svelte';
  import * as d3 from 'd3';
  import type { KeywordGraph, IssueAnalysis } from '../lib/types';

  interface Props {
    keywordGraph: KeywordGraph;
    issues: IssueAnalysis[];
  }

  let { keywordGraph, issues }: Props = $props();
  let container: HTMLDivElement;

  onMount(() => {
    const width = 1200;
    const height = 600;

    // Build keyword -> issue type breakdown
    const keywordBreakdown = new Map<string, Record<string, number>>();

    issues.forEach(issue => {
      const issueType = issue.classification.type;
      issue.classification.keywords.forEach(keyword => {
        if (!keywordBreakdown.has(keyword)) {
          keywordBreakdown.set(keyword, {});
        }
        const breakdown = keywordBreakdown.get(keyword)!;
        breakdown[issueType] = (breakdown[issueType] || 0) + 1;
      });
    });

    // Prepare data for word cloud with issue type info
    const keywords = keywordGraph.nodes
      .filter(n => n.issue_count > 0)
      .map(node => {
        const breakdown = keywordBreakdown.get(node.id) || {};
        const entries = Object.entries(breakdown).sort(([,a], [,b]) => b - a);
        const dominantType = entries[0]?.[0] || 'unknown';
        return {
          ...node,
          breakdown,
          dominantType
        };
      })
      .sort((a, b) => b.issue_count - a.issue_count)
      .slice(0, 100); // Top 100 keywords

    if (keywords.length === 0) {
      d3.select(container).append('p').text('No keywords found');
      return;
    }

    // Create simple tag cloud layout (spiral positioning)
    const maxCount = d3.max(keywords, d => d.issue_count) || 1;
    const minCount = d3.min(keywords, d => d.issue_count) || 1;

    // Font size scale
    const fontSize = d3.scaleLog()
      .domain([minCount, maxCount])
      .range([12, 72]);

    // Color scale by issue type (more distinct colors)
    const typeColors: Record<string, string> = {
      'outage': '#dc2626',      // Red
      'defect': '#7c3aed',      // Purple
      'enhancement': '#10b981',  // Green
      'clarification': '#f59e0b', // Yellow
      'inquiry': '#3b82f6',     // Blue
      'routing_issue': '#64748b', // Gray
      'action': '#ec4899'       // Pink
    };

    const getColor = (type: string) => typeColors[type] || '#9ca3af';

    const svg = d3.select(container)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .append('g')
      .attr('transform', `translate(${width / 2},${height / 2})`);

    // Simple spiral layout
    const angleStep = 0.1;
    const radiusStep = 5;
    let angle = 0;
    let radius = 0;

    const positions: Array<{
      x: number;
      y: number;
      keyword: string;
      size: number;
      count: number;
      dominantType: string;
      breakdown: Record<string, number>;
    }> = [];
    const occupied: Array<{x: number; y: number; width: number; height: number}> = [];

    keywords.forEach(keyword => {
      const size = fontSize(keyword.issue_count);
      const textWidth = keyword.id.length * size * 0.6; // Approximate width
      const textHeight = size;

      let placed = false;
      let attempts = 0;
      const maxAttempts = 1000;

      while (!placed && attempts < maxAttempts) {
        const x = radius * Math.cos(angle);
        const y = radius * Math.sin(angle);

        // Check if this position overlaps with any existing text
        const overlaps = occupied.some(box => {
          return !(x + textWidth < box.x ||
                   x > box.x + box.width ||
                   y + textHeight < box.y ||
                   y > box.y + box.height);
        });

        if (!overlaps && Math.abs(x) < width / 2 - 50 && Math.abs(y) < height / 2 - 50) {
          positions.push({
            x,
            y,
            keyword: keyword.id,
            size,
            count: keyword.issue_count,
            dominantType: keyword.dominantType,
            breakdown: keyword.breakdown
          });
          occupied.push({ x, y, width: textWidth, height: textHeight });
          placed = true;
        }

        angle += angleStep;
        radius += radiusStep * angleStep;
        attempts++;
      }
    });

    // Render text elements
    svg.selectAll('text')
      .data(positions)
      .join('text')
      .attr('x', d => d.x)
      .attr('y', d => d.y)
      .attr('font-size', d => `${d.size}px`)
      .attr('font-weight', 'bold')
      .attr('fill', d => getColor(d.dominantType))
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'middle')
      .style('cursor', 'pointer')
      .text(d => d.keyword)
      .on('mouseover', function(event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('font-size', `${d.size * 1.2}px`)
          .style('opacity', 0.8);
      })
      .on('mouseout', function(event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('font-size', `${d.size}px`)
          .style('opacity', 1);
      })
      .append('title')
      .text(d => {
        const breakdown = Object.entries(d.breakdown)
          .sort(([,a], [,b]) => b - a)
          .map(([type, count]) => `  ${type}: ${count}`)
          .join('\n');
        return `${d.keyword} (${d.count} total)\n${breakdown}`;
      });

    // Title
    svg.append('text')
      .attr('x', 0)
      .attr('y', -height / 2 + 30)
      .attr('text-anchor', 'middle')
      .attr('font-size', '20px')
      .attr('font-weight', 'bold')
      .attr('fill', '#111827')
      .text('Keywords by Dominant Issue Type (Top 100)');

    // Legend
    const legend = svg.append('g')
      .attr('transform', `translate(${-width / 2 + 20}, ${-height / 2 + 60})`);

    const issueTypes = [
      { type: 'outage', label: 'Outage' },
      { type: 'defect', label: 'Defect' },
      { type: 'enhancement', label: 'Enhancement' },
      { type: 'clarification', label: 'Clarification' },
      { type: 'inquiry', label: 'Inquiry' },
      { type: 'routing_issue', label: 'Routing Issue' },
      { type: 'action', label: 'Action' }
    ];

    issueTypes.forEach((item, i) => {
      const g = legend.append('g')
        .attr('transform', `translate(0, ${i * 20})`);

      g.append('rect')
        .attr('width', 12)
        .attr('height', 12)
        .attr('fill', getColor(item.type))
        .attr('rx', 2);

      g.append('text')
        .attr('x', 18)
        .attr('y', 6)
        .attr('dy', '0.35em')
        .attr('font-size', '11px')
        .attr('fill', '#374151')
        .text(item.label);
    });
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
    background: white;
    border-radius: 12px;
    padding: 20px;
  }
</style>
