import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const ProtectedRoute = ({ children, allowedRoles }) => {
  const { user, loading } = useAuth();

  // --- Added Console Log ---
  console.log("ProtectedRoute: Checking authentication and authorization...");
  console.log("ProtectedRoute: User loading state:", loading);
  console.log("ProtectedRoute: Current user:", user);
  console.log("ProtectedRoute: Allowed roles:", allowedRoles);
  // --- End Added Console Log ---

  if (loading) {
    console.log("ProtectedRoute: User data still loading, showing loading indicator.");
    // You might want a proper loading spinner component here
    return <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
        <p className="mt-4 text-gray-300">Loading user data...</p>
      </div>
    </div>;
  }

  if (!user) {
    console.log("ProtectedRoute: No user found, redirecting to login.");
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    console.log(`ProtectedRoute: User role '${user.role}' not allowed for this route. Redirecting to unauthorized.`);
    // Log unauthorized access attempt (using your logger if available)
    // errorLogger.logUnauthorizedAccess(user, window.location.pathname, allowedRoles);
    return <Navigate to="/unauthorized" replace />;
  }

  console.log("ProtectedRoute: User is authenticated and authorized, rendering children.");
  return children;
};

export default ProtectedRoute;