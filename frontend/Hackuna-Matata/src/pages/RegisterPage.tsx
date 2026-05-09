import React, { useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import '@/styles/Auth.css';

export const RegisterPage: React.FC = () => {
  const [form, setForm] = useState({ username: '', email: '', password: '' });
  const { register, loading } = useAuth();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    register(form.username, form.email, form.password);
  };

  return (
    <div className="auth-container">
      <h1>Sign Up</h1>
      <form onSubmit={handleSubmit}>
        <input 
          type="text" 
          placeholder="Username" 
          onChange={(e) => setForm({...form, username: e.target.value})} 
          required 
        />
        <input 
          type="email" 
          placeholder="Email" 
          onChange={(e) => setForm({...form, email: e.target.value})} 
          required 
        />
        <input 
          type="password" 
          placeholder="Password" 
          onChange={(e) => setForm({...form, password: e.target.value})} 
          required 
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Creating account...' : 'Sign Up'}
        </button>
      </form>
    </div>
  );
};