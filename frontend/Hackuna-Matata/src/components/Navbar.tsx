import React from 'react';
import { useAuth } from '../hooks/useAuth';

export const Navbar: React.FC = () => {
  const { logout } = useAuth();

  return (
    <nav>
      <span>Braynr</span>
      <button onClick={logout} className="logout-btn">
        Log out
      </button>
    </nav>
  );
};