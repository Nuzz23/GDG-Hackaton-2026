import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
/*
import { AuthAPI } from '@/services/api';

export const useAuth = () => {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const login = async (email: string, pass: string) => {
    setLoading(true);
    try {
      const response = await AuthAPI.login({ email, password: pass });
      //save token in localStorage (or cookie) for future authenticated requests
      localStorage.setItem('token', response.data.token); 
      navigate('/dashboard');
    } catch (err) {
      alert("Failed to login. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  const register = async (username: string, email: string, pass: string) => {
    setLoading(true);
    try {
      await AuthAPI.register({ username, email, password: pass });
      alert("Registration completed! You can now log in.");
      navigate('/login');
    } catch (err) {
      alert("Error occurred during registration. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem('token'); 
    navigate('/login');               
  };

  return { login, register, logout, loading };
};
*/