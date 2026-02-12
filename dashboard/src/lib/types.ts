/**
 * TypeScript types matching the analyzed.json schema
 */

export interface Classification {
  type: string;
  confidence: number;
  keywords: string[];
  summary: string;
}

export interface IssueAnalysis {
  id: string;
  classification: Classification;
  created_at?: string;
  updated_at?: string;
  url?: string;
  title?: string;
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

export interface KeywordNode {
  id: string;
  issue_count: number;
}

export interface KeywordEdge {
  from: string;
  to: string;
  co_occurrence: number;
}

export interface KeywordGraph {
  nodes: KeywordNode[];
  edges: KeywordEdge[];
}

export interface AnalysisMetadata {
  analyzed_at: string;
  classifier: string;
}

export interface AnalyzedData {
  issues: IssueAnalysis[];
  people_graph: PeopleGraph;
  keyword_graph: KeywordGraph;
  metadata: AnalysisMetadata;
}
