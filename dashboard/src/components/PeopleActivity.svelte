<script lang="ts">
  import { onMount } from 'svelte';
  import * as d3 from 'd3';
  import type { IssueAnalysis, PeopleGraph } from '../lib/types';

  interface Props {
    issues: IssueAnalysis[];
    peopleGraph: PeopleGraph;
  }

  let { issues, peopleGraph }: Props = $props();
  let reportersContainer: HTMLDivElement;
  let respondersContainer: HTMLDivElement;

  onMount(() => {
    // Build person -> issue type mapping for reporters
    const personActivity = new Map<string, {
      reported: Map<string, number>;
      responded: number;
      name: string;
    }>();

    // Process each issue with its people data
    issues.forEach((issue) => {
      const issueType = issue.classification.type;

      issue.people?.forEach((person: any) => {
        const key = `${person.source}:${person.source_id}`;
        if (!personActivity.has(key)) {
          personActivity.set(key, {
            reported: new Map(),
            responded: 0,
            name: person.name
          });
        }
        const activity = personActivity.get(key)!;

        if (person.role === 'reporter') {
          activity.reported.set(issueType, (activity.reported.get(issueType) || 0) + 1);
        } else if (person.role === 'assignee' || person.role === 'commenter') {
          activity.responded++;
        }
      });
    });

    // Top reporters chart
    const reporterData = Array.from(personActivity.entries())
      .map(([key, activity]) => {
        const totalReported = Array.from(activity.reported.values()).reduce((a, b) => a + b, 0);
        return {
          name: activity.name,
          total: totalReported,
          byType: Array.from(activity.reported.entries()).map(([type, count]) => ({ type, count }))
        };
      })
      .filter(d => d.total > 0)
      .sort((a, b) => b.total - a.total)
      .slice(0, 10);

    renderReporters(reporterData);

    // Top responders chart
    const responderData = Array.from(personActivity.entries())
      .map(([key, activity]) => ({
        name: activity.name,
        count: activity.responded
      }))
      .filter(d => d.count > 0)
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);

    renderResponders(responderData);
  });

  function renderReporters(data: any[]) {
    const margin = { top: 40, right: 120, bottom: 60, left: 150 };
    const width = 700 - margin.left - margin.right;
    const height = 400 - margin.top - margin.bottom;

    const svg = d3.select(reportersContainer)
      .append('svg')
      .attr('width', width + margin.left + margin.right)
      .attr('height', height + margin.top + margin.bottom)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const y = d3.scaleBand()
      .domain(data.map(d => d.name))
      .range([0, height])
      .padding(0.2);

    const x = d3.scaleLinear()
      .domain([0, d3.max(data, d => d.total) || 0])
      .range([0, width]);

    const color = d3.scaleOrdinal<string>()
      .domain(['defect', 'inquiry', 'clarification', 'outage', 'enhancement', 'routing_issue'])
      .range(['#ef4444', '#f59e0b', '#f97316', '#dc2626', '#10b981', '#6b7280']);

    // Stacked bars
    data.forEach(person => {
      let xOffset = 0;
      person.byType.forEach((typeData: any) => {
        svg.append('rect')
          .attr('x', xOffset)
          .attr('y', y(person.name)!)
          .attr('width', x(typeData.count))
          .attr('height', y.bandwidth())
          .attr('fill', color(typeData.type))
          .attr('rx', 2)
          .append('title')
          .text(`${typeData.type}: ${typeData.count}`);
        xOffset += x(typeData.count);
      });

      // Total label
      svg.append('text')
        .attr('x', xOffset + 5)
        .attr('y', y(person.name)! + y.bandwidth() / 2)
        .attr('dy', '0.35em')
        .attr('font-size', '11px')
        .attr('fill', '#374151')
        .text(person.total);
    });

    // Y axis
    svg.append('g')
      .call(d3.axisLeft(y))
      .selectAll('text')
      .attr('font-size', '11px');

    // Title
    svg.append('text')
      .attr('x', width / 2)
      .attr('y', -20)
      .attr('text-anchor', 'middle')
      .attr('font-size', '14px')
      .attr('font-weight', 'bold')
      .text('Top Issue Reporters (by type)');

    // Legend
    const legend = svg.append('g')
      .attr('transform', `translate(${width + 20}, ${height / 2 - 50})`);

    const types = ['defect', 'inquiry', 'clarification', 'outage', 'enhancement', 'routing_issue'];
    types.forEach((type, i) => {
      const g = legend.append('g')
        .attr('transform', `translate(0, ${i * 18})`);

      g.append('rect')
        .attr('width', 10)
        .attr('height', 10)
        .attr('fill', color(type))
        .attr('rx', 2);

      g.append('text')
        .attr('x', 14)
        .attr('y', 5)
        .attr('dy', '0.35em')
        .attr('font-size', '10px')
        .text(type.replace('_', ' '));
    });
  }

  function renderResponders(data: any[]) {
    const margin = { top: 40, right: 20, bottom: 60, left: 150 };
    const width = 600 - margin.left - margin.right;
    const height = 400 - margin.top - margin.bottom;

    const svg = d3.select(respondersContainer)
      .append('svg')
      .attr('width', width + margin.left + margin.right)
      .attr('height', height + margin.top + margin.bottom)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const y = d3.scaleBand()
      .domain(data.map(d => d.name))
      .range([0, height])
      .padding(0.2);

    const x = d3.scaleLinear()
      .domain([0, d3.max(data, d => d.count) || 0])
      .range([0, width]);

    // Bars
    svg.selectAll('rect')
      .data(data)
      .join('rect')
      .attr('x', 0)
      .attr('y', d => y(d.name)!)
      .attr('width', d => x(d.count))
      .attr('height', y.bandwidth())
      .attr('fill', '#10b981')
      .attr('rx', 4);

    // Labels
    svg.selectAll('text.label')
      .data(data)
      .join('text')
      .attr('class', 'label')
      .attr('x', d => x(d.count) + 5)
      .attr('y', d => y(d.name)! + y.bandwidth() / 2)
      .attr('dy', '0.35em')
      .attr('font-size', '11px')
      .attr('fill', '#374151')
      .text(d => d.count);

    // Y axis
    svg.append('g')
      .call(d3.axisLeft(y))
      .selectAll('text')
      .attr('font-size', '11px');

    // Title
    svg.append('text')
      .attr('x', width / 2)
      .attr('y', -20)
      .attr('text-anchor', 'middle')
      .attr('font-size', '14px')
      .attr('font-weight', 'bold')
      .text('Top Responders (assignees + commenters)');
  }
</script>

<div class="people-activity">
  <div class="chart">
    <div bind:this={reportersContainer}></div>
  </div>
  <div class="chart">
    <div bind:this={respondersContainer}></div>
  </div>
</div>

<style>
  .people-activity {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 30px;
    margin: 20px 0;
  }

  @media (max-width: 1200px) {
    .people-activity {
      grid-template-columns: 1fr;
    }
  }

  .chart {
    background: white;
    padding: 20px;
    border-radius: 8px;
  }
</style>
