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