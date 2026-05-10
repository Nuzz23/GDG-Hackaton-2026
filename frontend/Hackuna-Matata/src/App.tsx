import { type JSX } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom';
//import { LoginPage } from '@/pages/LoginPage';
//import { RegisterPage } from '@/pages/RegisterPage';
import { GroupsPage } from '@/pages/GroupPages';
import { Navbar } from '@/components/Navbar';

import './App.css';
import { HomePage } from './pages/HomePage';

// Helper protecting routes that require authentication
/*
const ProtectedRoute = ({ children }: { children: JSX.Element }) => {
  const token = localStorage.getItem('token');
  
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return children;
};
*/

function App() {
  // Using a state or standard check to determine if user is logged in
  const isAuthenticated = true;
  //!!localStorage.getItem('token');

  return (
    <>
      <Navbar />
      <main>
        <Routes>
          {/* Public routes 
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          */}

          {/* Protected routes 
          <Route 
            path="/groups" 
            element={
              //<ProtectedRoute>
                <GroupsPage />
              //</ProtectedRoute>
            } 
          />*/}

          <Route 
            path="/home" 
            element={
              //<ProtectedRoute>
                <HomePage />
              //</ProtectedRoute>
            } 
          />
          
          <Route 
            path="*" 
            element={<Navigate to={isAuthenticated ? "/groups" : "/login"} replace />} 
          />
        </Routes>
      </main>
    </>
  );
}

export default App;