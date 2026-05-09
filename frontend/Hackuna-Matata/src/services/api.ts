import apiClient from './apiClient';
import type { 
  User, UserUpdate, Group, GroupCreate, GroupUpdate, 
  Subject, SubjectCreate, Material, MaterialCreate 
} from '@/types/apiTypes';

export const AuthAPI = {
  login: (credentials: { email: string; password: string }) => apiClient.get('/v1/auth/login', { params: credentials }),
  register: (data: { username: string; email: string; password: string }) => apiClient.get('/v1/auth/register', { params: data }),
};

export const UserAPI = {
  getProfile: () => apiClient.get<User>('/v1/user/profile'),
  updateProfile: (data: UserUpdate) => apiClient.patch<User>('/v1/user/profile', data),
  getGroups: () => apiClient.get<Group[]>('/v1/user/groups'),
  getSubjects: () => apiClient.get<Subject[]>('/v1/user/subjects'),
};

export const GroupAPI = {
  list: () => apiClient.get<Group[]>('/v1/group/list'),
  getById: (id: number) => apiClient.get<Group>(`/v1/group/${id}`),
  create: (data: GroupCreate) => apiClient.post<Group>('/v1/group/create', data),
  update: (id: number, data: GroupUpdate) => apiClient.patch<Group>(`/v1/group/${id}`, data),
  delete: (id: number) => apiClient.delete(`/v1/group/${id}`),
  getMembers: (id: number) => apiClient.get<User[]>(`/v1/group/${id}/members`),
  getSubjects: (id: number) => apiClient.get<Subject[]>(`/v1/group/${id}/subjects`),
  addUser: (data: { group_id: number; user_id: number }) => apiClient.post('/v1/group/add', data),
};

export const SubjectAPI = {
  list: () => apiClient.get<Subject[]>('/v1/subject/list'),
  getById: (id: number) => apiClient.get<Subject>(`/v1/subject/${id}`),
  create: (data: SubjectCreate) => apiClient.post<Subject>('/v1/subject/create', data),
  update: (id: number, data: any) => apiClient.patch<Subject>(`/v1/subject/${id}`, data),
  delete: (id: number) => apiClient.delete(`/v1/subject/${id}`),
};

export const MaterialAPI = {
  upload: (data: FormData) => apiClient.post<Material>('/v1/material/upload', data, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  getById: (id: number) => apiClient.get<Material>(`/v1/material/${id}`),
  delete: (id: number) => apiClient.delete(`/v1/material/${id}`),
};