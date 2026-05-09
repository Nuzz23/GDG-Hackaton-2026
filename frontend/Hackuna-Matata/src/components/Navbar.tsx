import React from 'react';
import { useAuth } from '../hooks/useAuth';

export const Navbar: React.FC = () => {
  const { logout } = useAuth();

  return (
    <nav>
      <span>MyApp</span>
      <button onClick={logout} className="logout-btn">
        Esci
      </button>
    </nav>
  );
};