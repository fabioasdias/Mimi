/**
 * TypeScript types matching the analyzed.json schema
 */

export interface Classification {
  type: string;
  confidence: number;
  services: string[];
  summary: string;
}

export interface IssueAnalysis {
  id: string;
  classification: Classification;
}

export interface Identity {
  source: string;
  source_id: string;
  email?: string;
  display_name?: string;
}

export interface PersonNode {
  id: string;
  label: string;
  identities: Identity[];
}

export interface GraphEdge {
  from: string;
  to: string;
  role?: string;
  relation?: string;
  confidence?: number;
}

export interface PeopleGraph {
  nodes: PersonNode[];
  edges: GraphEdge[];
}

export interface ServiceNode {
  id: string;
  issue_count: number;
}

export interface ServiceEdge {
  from: string;
  to: string;
  co_occurrence: number;
}

export interface ServiceGraph {
  nodes: ServiceNode[];
  edges: ServiceEdge[];
}

export interface AnalysisMetadata {
  analyzed_at: string;
  classifier: string;
}

export interface AnalyzedData {
  issues: IssueAnalysis[];
  people_graph: PeopleGraph;
  service_graph: ServiceGraph;
  metadata: AnalysisMetadata;
}
