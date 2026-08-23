export type MatchType = "exact" | "gene_context" | "none";

export interface VariantInfo {
  chrom: string;
  pos: string;
  gene: string;
  mutation: string;
}

export interface ClinicalMatch {
  disease: string;
  therapy: string;
  evidence_tier: string;
  source: string;
  match_type: MatchType;
}

export interface InputValidation {
  fileformat_header: boolean;
  column_header: boolean;
  data_rows: number;
  parsed_rows: number;
  skipped_rows: number;
  gene_annotated_rows: number;
  mutation_annotated_rows: number;
  duplicate_rows: number;
  valid_vcf_headers: boolean;
  annotation_coverage_percent: number;
  patients_observed: number;
  unique_variant_combinations: number;
}

export interface AnnotatedResult {
  variant_info: VariantInfo;
  clinical_matches: ClinicalMatch[];
}

export interface AnalysisResponse {
  status: string;
  variants_count: number;
  unique_genes: number;
  exact_matches: number;
  contextual_matches: number;
  no_matches: number;
  synthetic_data: boolean;
  input_validation: InputValidation;
  annotated_results: AnnotatedResult[];
}

export type KnowledgeBaseState = "missing" | "empty" | "loaded";

export interface HealthResponse {
  status: string;
  knowledge_base: KnowledgeBaseState;
  evidence_records: number;
}

/** Flat evidence row, mirroring the Streamlit matrix columns. */
export interface MatrixRow {
  gene: string;
  mutation: string;
  chromosome: string;
  disease: string;
  targetedDrug: string;
  evidenceLevel: string;
  source: string;
  matchType: MatchType | "unknown";
}

/** Wire shape expected by /api/v1/report/* endpoints (capitalized keys). */
export type ReportRow = Record<string, string>;

export interface CohortRow extends MatrixRow {
  patients: number;
}

export function toReportRow(r: MatrixRow): ReportRow {
  return {
    Gene: r.gene,
    Mutation: r.mutation,
    Chromosome: r.chromosome,
    Disease: r.disease,
    "Targeted Drug": r.targetedDrug,
    "Evidence Level": r.evidenceLevel,
    Source: r.source,
    "Match Type": r.matchType,
  };
}

export function buildAnalysisPayload(a: AnalysisResponse, validation: InputValidation) {
  return {
    variants_count: a.variants_count,
    exact_matches: a.exact_matches,
    contextual_matches: a.contextual_matches,
    no_matches: a.no_matches,
    synthetic_data: a.synthetic_data,
    input_validation: validation,
  };
}
