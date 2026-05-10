import { useState, useEffect } from 'react';
import { groupApi } from '../services/api';
import type { Group } from '@/types/apiTypes';

export const useGroups = () => {
  const [groups, setGroups] = useState<Group[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchGroups = async () => {
      try {
        setLoading(true);
        const response = await groupApi.listGroups();
        setGroups(response.data);
      } catch (err: any) {
        setError(err.response?.data?.msg || 'Failed to fetch groups');
      } finally {
        setLoading(false);
      }
    };

    fetchGroups();
  }, []);

  return { groups, loading, error };
};