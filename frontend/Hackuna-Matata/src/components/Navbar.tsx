import React from 'react';
import '@/styles/Navbar.css';

export const Navbar: React.FC = () => {
  const isAuthenticated = !!localStorage.getItem('token');
  return (
    <nav className="navbar">
      <span className="navbar-brand">Braynr</span>
      {isAuthenticated && (
        <button onClick={() => localStorage.removeItem('token')} className="logout-btn">
          Log out
        </button>
      )}
    </nav>
  );
};