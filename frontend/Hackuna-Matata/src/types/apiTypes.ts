export interface User {
  id: number;
  username: string;
  email: string;
}

export interface UserUpdate {
  username?: string | null;
  email?: string | null;
}

export interface Group {
  id: number;
  name: string;
  created_at: string; // ISO Date string
  users: number[];
}

export interface GroupCreate {
  name: string;
  users?: number[];
}

export interface GroupUpdate {
  name?: string | null;
  users?: number[] | null;
}

export interface Subject {
  id: number;
  name: string;
  deadline: string; // ISO Date string
  materials: number[];
}

export interface SubjectCreate {
  name: string;
  deadline: string;
  materials?: number[];
}

export interface Material {
  id: number;
  name: string;
  uploadDate: string;
  path: string;
  fileSize: number;
}

export interface MaterialCreate {
  name: string;
  path: string;
  fileSize: number;
}

/**
 * ARTIFACT TYPES
 */
export const ArtifactType = {
  HIGHLIGHT: "highlight",
  MINDMAP: "mindmap",
  KEYWORD: "keyword",
  NOTE: "note",
  QUESTION: "question",
  // AI-agent outputs (Learn Different track)
  INDEX: "index",
  QUIZ: "quiz",
  TRACE: "trace",
} as const;

export type ArtifactType = typeof ArtifactType[keyof typeof ArtifactType];

export interface Artifact {
  id: number;
  material_id: number;
  artifact_type: ArtifactType;
  page_number?: number | null;
  content: any; // Struttura JSON flessibile
  created_at: string;
  updated_at?: string | null;
}

export interface ArtifactCreate {
  artifact_type: ArtifactType;
  content: any;
  page_number?: number;
}

export interface ArtifactUpdate {
  content?: any;
  page_number?: number | null;
}

// Alias per coerenza con il controller
export type ArtifactResponse = Artifact;

/**
 * MISSING SUBJECT TYPES
 */
export interface SubjectUpdate {
  name?: string;
  deadline?: string;
  materials?: number[];
}

/**
 * MISSING MATERIAL TYPES
 */
export interface MaterialUpdate {
  name?: string;
  path?: string;
  fileSize?: number;
}

/**
 * MISSING GROUP TYPES
 */
export interface GroupUserAdd {
  group_id: number;
  user_id: number;
}

/**
 * AUTH & GENERIC (Opzionali ma utili)
 */
export interface ApiError {
  detail: {
    loc: (string | number)[];
    msg: string;
    type: string;
  }[];
}

/* ═══════════════════════════════════════════════════════════════════════
 * AI AGENT TYPES — mirror processing_agent / quiz_creation_agent / eval_agent
 * Pydantic schemas. Loose typing where the backend's `content: any` makes
 * stricter typing not worth the friction.
 * ═══════════════════════════════════════════════════════════════════════ */

// ───── processing_agent / IndexOutput ─────

export type SourceType =
  | "pdf" | "pdf_notes" | "pdf_slides" | "pptx" | "md" | "audio" | "video";

export type Language = "it" | "en";

export interface SourceLocator {
  type: "pdf" | "slide" | "md" | "time";
  page_start?: number;
  page_end?: number;
  char_range?: [number, number] | null;
  bbox?: [number, number, number, number] | null;
  slide_index_start?: number;
  slide_index_end?: number;
  char_offset_start?: number;
  char_offset_end?: number;
  t_start?: number;
  t_end?: number;
}

export type NodeKind = "root" | "chapter" | "section" | "subsection" | "paragraph";

export interface HierarchyNode {
  node_id: string;
  level: number;
  kind: NodeKind;
  label?: string | null;
  text?: string | null;       // only on leaf paragraphs
  locator: SourceLocator;
  children: HierarchyNode[];
}

export interface SourceInfo {
  type: SourceType;
  filename: string;
  language: Language;
  size_metric: Record<string, number>;
}

export interface IndexOutput {
  doc_id: string;
  source: SourceInfo;
  tree: HierarchyNode;
  metadata: {
    generated_at: string;
    agent_version: string;
    warnings: string[];
  };
}

// ───── quiz_creation_agent / QuizOutput ─────

export type ItemTypeCode = "f" | "mcq" | "qa";
export type Difficulty = "facile" | "medio" | "difficile";

export interface QuizSourceRef {
  source_filename: string;
  excerpt: string;
  doc_id?: string | null;
  node_id?: string | null;
  source_label?: string | null;
  locator?: SourceLocator | null;
}

export interface FlashcardItem {
  item_id: string;
  item_type: "f";
  difficulty: Difficulty;
  source: QuizSourceRef;
  front: string;
  back: string;
}

export interface MCQItem {
  item_id: string;
  item_type: "mcq";
  difficulty: Difficulty;
  source: QuizSourceRef;
  question: string;
  options: string[];
  correct_index: number;
  explanation: string;
}

export interface OpenQuestionItem {
  item_id: string;
  item_type: "qa";
  difficulty: Difficulty;
  source: QuizSourceRef;
  question: string;
  expected_answer: string;
  key_points: string[];
}

export type AssessmentItemAny = FlashcardItem | MCQItem | OpenQuestionItem;

export interface QuizOutput {
  quiz_id: string;
  item_type: ItemTypeCode;
  difficulty: Difficulty;
  language: Language;
  n_requested: number;
  n_produced: number;
  source: QuizSourceRef;
  items: AssessmentItemAny[];
  metadata: {
    generated_at: string;
    agent_version: string;
    warnings: string[];
  };
}

// ───── eval_agent / TraceEvent ─────

export type AssessmentTypeCode = "closed_quiz" | "flashcard" | "open_question";
export type ResponseModality = "text" | "audio";
export type ConceptStatusValue = "pending" | "passed" | "fragile";
export type InterventionKind =
  | "advance" | "hint_plus_redirect" | "redirect_only"
  | "modality_switch" | "full_redirect";

export interface OpenQuestionJudgment {
  judgment_type: "open";
  completezza: "alta" | "parziale" | "assente";
  correttezza: "corretta" | "parzialmente_corretta" | "errata";
  elaborazione: "rielaborata" | "riportata" | "non_valutabile";
  missing_aspects: string[];
  incorrect_elements: string[];
  elaboration_evidence: string;
  paralinguistic_contribution?: string | null;
}

export interface ClosedJudgment {
  judgment_type: "closed";
  correct: boolean;
  selected_option: string;
  expected_option: string;
  fuzzy_match_score?: number | null;
  fuzzy_match_used: boolean;
}

export type Judgment = OpenQuestionJudgment | ClosedJudgment;

export interface SourceRedirect {
  node_id: string;
  excerpt?: string | null;
  locator_summary: string;
}

export interface Intervention {
  kind: InterventionKind;
  student_message: string;
  source_redirect?: SourceRedirect | null;
}

export interface TraceEvent {
  event_id: string;
  session_id: string;
  timestamp: string;
  node_id: string;
  assessment_type: AssessmentTypeCode;
  assessment_id: string;
  attempt_number: number;
  response_modality: ResponseModality;
  response_raw: string;
  paralinguistic_features?: Record<string, any> | null;
  judgment: Judgment;
  intervention: Intervention;
  concept_status_after: ConceptStatusValue;
}

// ───── Agent endpoint response wrappers ─────

export interface IndexResponse {
  artifact_id: number;
  material_id: number;
  index: IndexOutput;
  created_at?: string;
}

export interface QuizResponse {
  artifact_id: number;
  material_id: number;
  quiz: QuizOutput;
  created_at?: string;
}

export interface EvaluateResponse {
  artifact_id: number;
  material_id: number;
  session_id: string;
  trace: TraceEvent;
}