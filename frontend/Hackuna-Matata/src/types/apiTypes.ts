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
  creationDate: string; // ISO Date string
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