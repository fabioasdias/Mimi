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
    const margin = { top: 20, right: 20, bottom: 60, left: 150 };
    const width = 800 - margin.left - margin.right;
    const height = 500 - margin.top - margin.bottom;

    // Filter for documentation-related issues (questions and user errors)
    const docIssues = issues.filter(
      i => i.classification.type === 'question' || i.classification.type === 'user_error'
    );

    // Count by service
    const serviceMap = new Map<string, {questions: number; userErrors: number}>();

    docIssues.forEach(issue => {
      issue.classification.services.forEach(service => {
        if (!serviceMap.has(service)) {
          serviceMap.set(service, { questions: 0, userErrors: 0 });
        }
        const counts = serviceMap.get(service)!;
        if (issue.classification.type === 'question') {
          counts.questions++;
        } else {
          counts.userErrors++;
        }
      });
    });

    const data = Array.from(serviceMap, ([service, counts]) => ({
      service,
      questions: counts.questions,
      userErrors: counts.userErrors,
      total: counts.questions + counts.userErrors
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
      .domain(data.map(d => d.service))
      .range([0, height])
      .padding(0.3);

    const barHeight = y.bandwidth();

    // User errors (darker)
    svg.selectAll('rect.user-error')
      .data(data)
      .join('rect')
      .attr('class', 'user-error')
      .attr('x', 0)
      .attr('y', d => y(d.service)!)
      .attr('width', d => x(d.userErrors))
      .attr('height', barHeight)
      .attr('fill', '#dc2626')
      .attr('rx', 4);

    // Questions (lighter, stacked)
    svg.selectAll('rect.question')
      .data(data)
      .join('rect')
      .attr('class', 'question')
      .attr('x', d => x(d.userErrors))
      .attr('y', d => y(d.service)!)
      .attr('width', d => x(d.questions))
      .attr('height', barHeight)
      .attr('fill', '#f97316')
      .attr('rx', 4);

    // Total labels
    svg.selectAll('text.total')
      .data(data)
      .join('text')
      .attr('class', 'total')
      .attr('x', d => x(d.total) + 5)
      .attr('y', d => y(d.service)! + barHeight / 2)
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
      .text('Documentation Gaps (Questions + User Errors)');

    // Legend
    const legend = svg.append('g')
      .attr('transform', `translate(${width - 150}, 10})`);

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
      .text('User Errors');

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
      .text('Questions');
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
