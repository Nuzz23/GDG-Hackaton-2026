import React from 'react';
import { useAuth } from '../hooks/useAuth';
import '@/styles/Navbar.css';

export const Navbar: React.FC = () => {
  const { logout } = useAuth();
  const isAuthenticated = !!localStorage.getItem('token');
  return (
    <nav className="navbar">
      <span className="navbar-brand">Braynr</span>
      {isAuthenticated && (
        <button onClick={logout} className="logout-btn">
          Log out
        </button>
      )}
    </nav>
  );
};