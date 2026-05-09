import apiClient from './apiClient';
import type { 
  User, UserUpdate, Group, GroupCreate, GroupUpdate, 
  Subject, SubjectCreate, Material,
  SubjectUpdate, /* MaterialCreate */ 
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

