import { useState, type JSX } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom';
import { LoginPage } from '@/pages/LoginPage';
import { RegisterPage} from '@/pages/RegisterPage';
import { GroupsPage } from '@/pages/GroupPages';
import { Navbar } from '@/components/Navbar';

import './App.css'

//helper protecting routes that require authentication
const ProtectedRoute = ({ children }: { children: JSX.Element }) => {
  const token = localStorage.getItem('token');
  
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return children;
};

function App() {
  const isAuthenticated = !!localStorage.getItem('token');

  return (
    <div className="min-h-screen bg-gray-50">

      {isAuthenticated && <Navbar />}

      <main className="container mx-auto p-4">
        <Routes>
          {/* public routes LoginPage*/}
          <Route path="/login" element={<GroupsPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* protected routes */}
          <Route 
            path="/groups" 
            element={
              <ProtectedRoute>
                <GroupsPage />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="*" 
            element={<Navigate to={isAuthenticated ? "/groups" : "/login"} replace />} 
          />
        </Routes>
      </main>
    </div>
  );
}

export default App;