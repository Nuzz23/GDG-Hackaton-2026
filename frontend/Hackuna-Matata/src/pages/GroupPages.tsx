// src/pages/GroupsPage.tsx
import React from 'react';
import { useGroups } from '../hooks/useGroups';
import '@/styles/GroupPage.css';
import apiClient from '@/services/apiClient';

export const GroupsPage: React.FC = () => {
  const { groups, loading, error } = useGroups();

  if (loading) return <div>Fetching groups...</div>;
  if (error) return <div className="text-red-500">Error: {error}</div>;

  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">Your Groups</h1>
      <button className="mb-4 px-4 py-2 bg-blue-500 text-white rounded">
        Create New Group
      </button>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {groups.map((group) => (
          <div key={group.id} className="border p-4 rounded shadow-sm">
            <h2 className="text-xl font-semibold">{group.name}</h2>
            <p className="text-sm text-gray-500">
              Created on: {new Date(group.created_at).toLocaleDateString()}
            </p>
            <p className="mt-2">Members: {group.users?.length || 0}</p>
          </div>
        ))}
      </div>
    </div>
  );
};