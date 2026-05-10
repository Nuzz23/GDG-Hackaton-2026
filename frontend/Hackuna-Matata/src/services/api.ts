import apiClient from './apiClient';
import type {
  User, /* UserUpdate ,*/ Group, GroupCreate, GroupUpdate,
  Subject, SubjectCreate, Material,
  SubjectUpdate, /* MaterialCreate */
  IndexResponse, QuizResponse, EvaluateResponse,
  ItemTypeCode, Difficulty,
} from '@/types/apiTypes';

export const groupApi = {
  listGroups: () => 
    apiClient.get<Group[]>('/v1/group/list'),

  getGroupMembers: (groupId: number) => 
    apiClient.get<User[]>(`/v1/group/${groupId}/members`),

  getGroupSubjects: (groupId: number) => 
    apiClient.get<Subject[]>(`/v1/group/${groupId}/subjects`),

  createGroup: (data: GroupCreate) => 
    apiClient.post<Group>('/v1/group/create', data),

  addUserToGroup: (payload: { group_id: number; user_id: number }) => 
    apiClient.post('/v1/group/add', payload),

  getGroup: (groupId: number) => 
    apiClient.get<Group>(`/v1/group/${groupId}`),

  updateGroup: (groupId: number, data: GroupUpdate) => 
    apiClient.patch<Group>(`/v1/group/${groupId}`, data),

  deleteGroup: (groupId: number) => 
    apiClient.delete(`/v1/group/${groupId}`),
};

export const subjectApi = {
  listSubjects: (groupId: number) => 
    apiClient.get<Subject[]>('/v1/subject/list', { params: { group_id: groupId } }),

  createSubject: (groupId: number, data: SubjectCreate) => 
    apiClient.post<Subject>('/v1/subject/create', data, { params: { group_id: groupId } }),

  getSubject: (groupId: number, subjectId: number) => 
    apiClient.get<Subject>(`/v1/subject/${subjectId}`, { params: { group_id: groupId } }),

  updateSubject: (groupId: number, subjectId: number, data: SubjectUpdate) => 
    apiClient.patch<Subject>(`/v1/subject/${subjectId}`, data, { params: { group_id: groupId } }),

  deleteSubject: (groupId: number, subjectId: number) => 
    apiClient.delete(`/v1/subject/${subjectId}`, { params: { group_id: groupId } }),
};

export const materialApi = {
  uploadMaterial: (groupId: number, file: File, name: string, subjectId: number) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('name', name);
    formData.append('subject_id', subjectId.toString());

    return apiClient.post<Material>('/v1/material/upload', formData, {
      params: { group_id: groupId },
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  /** List all materials for a subject (within a group). */
  listBySubject: (groupId: number, subjectId: number) =>
    apiClient.get<Material[]>('/v1/material/list', {
      params: { group_id: groupId, subject_id: subjectId },
    }),

  getMaterial: (groupId: number, materialId: number) =>
    apiClient.get<Material>(`/v1/material/${materialId}`, { params: { group_id: groupId } }),

  updateMaterial: (groupId: number, materialId: number, data: any) => 
    apiClient.patch<Material>(`/v1/material/${materialId}`, data, { params: { group_id: groupId } }),

  deleteMaterial: (groupId: number, materialId: number) => 
    apiClient.delete(`/v1/material/${materialId}`, { params: { group_id: groupId } }),
};

export const artifactApi = {
  createArtifact: (materialId: number, data: any) =>
    apiClient.post(`/v1/material/${materialId}/artifact/`, data),

  getArtifacts: (materialId: number, type?: string) =>
    apiClient.get(`/v1/material/${materialId}/artifact/`, {
      params: { artifact_type: type }
    }),

  getArtifact: (materialId: number, artifactId: number) =>
    apiClient.get(`/v1/material/${materialId}/artifact/${artifactId}`),

  updateArtifact: (materialId: number, artifactId: number, data: any) =>
    apiClient.patch(`/v1/material/${materialId}/artifact/${artifactId}`, data),

  deleteArtifact: (materialId: number, artifactId: number) =>
    apiClient.delete(`/v1/material/${materialId}/artifact/${artifactId}`),
};

/* ════════════════════════════════════════════════════════════════════════
 * agentApi — wraps the four AI-agent endpoints (Learn Different track)
 * ════════════════════════════════════════════════════════════════════════ */

export const agentApi = {
  /** Trigger processing_agent on a material's stored file. Synchronous.
   *  PDFs return in seconds; audio/video can take 30s–3min. */
  indexMaterial: (groupId: number, materialId: number) =>
    apiClient.post<IndexResponse>(
      `/v1/material/${materialId}/agent/index`,
      null,
      { params: { group_id: groupId }, timeout: 600000 },
    ),

  /** Read the latest INDEX artifact for a material. */
  getLatestIndex: (materialId: number) =>
    apiClient.get<IndexResponse>(
      `/v1/material/${materialId}/agent/index`,
    ),

  /** Generate quiz items from a node of the latest index. */
  generateQuiz: (
    materialId: number,
    body: { node_id: string; item_type: ItemTypeCode; n: number; difficulty?: Difficulty },
  ) =>
    apiClient.post<QuizResponse>(
      `/v1/material/${materialId}/agent/quiz`,
      body,
      { timeout: 120000 },
    ),

  /** List all QUIZ artifacts for a material. */
  listQuizzes: (materialId: number) =>
    apiClient.get<QuizResponse[]>(
      `/v1/material/${materialId}/agent/quiz`,
    ),

  /** Evaluate a student response. Pass either responseText OR responseAudio. */
  evaluateResponse: (
    materialId: number,
    quizId: number,
    payload: {
      itemIndex: number;
      responseText?: string;
      responseAudio?: Blob;
      sessionId?: string;
    },
  ) => {
    const fd = new FormData();
    fd.append('item_index', String(payload.itemIndex));
    if (payload.sessionId) fd.append('session_id', payload.sessionId);
    if (payload.responseAudio) {
      const filename = (payload.responseAudio as any).name || 'response.webm';
      fd.append('response_audio', payload.responseAudio, filename);
    } else if (payload.responseText !== undefined) {
      fd.append('response_text', payload.responseText);
    }
    return apiClient.post<EvaluateResponse>(
      `/v1/material/${materialId}/agent/quiz/${quizId}/evaluate`,
      fd,
      { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 600000 },
    );
  },

  /** List all TRACE artifacts (eval history) for a material. */
  listTraces: (materialId: number) =>
    apiClient.get(`/v1/material/${materialId}/agent/trace`),
};

