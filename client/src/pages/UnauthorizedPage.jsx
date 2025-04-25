import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const UnauthorizedPage = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
      <div className="max-w-md w-full space-y-8 p-8 bg-gray-800 rounded-lg shadow-lg">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-red-500 mb-4">Access Denied</h1>
          <div className="text-6xl mb-6">🔒</div>
          <p className="text-gray-300 mb-6">
            You don't have permission to access this page. This could be because:
          </p>
          <ul className="text-left text-gray-400 space-y-2 mb-6">
            <li>• Your account doesn't have the required role</li>
            <li>• Your session has expired</li>
            <li>• You're trying to access a restricted resource</li>
          </ul>
        </div>

        <div className="space-y-4">
          {user ? (
            <>
              <p className="text-gray-300 text-center">
                You are currently logged in as: <span className="font-semibold">{user.username}</span> ({user.role})
              </p>
              <div className="flex flex-col space-y-3">
                <button
                  onClick={handleLogout}
                  className="w-full bg-red-600 hover:bg-red-700 text-white font-bold py-2 px-4 rounded-md transition duration-200"
                >
                  Logout and Try Again
                </button>
                <Link
                  to="/dashboard"
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-md text-center transition duration-200"
                >
                  Return to Dashboard
                </Link>
              </div>
            </>
          ) : (
            <Link
              to="/login"
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-md text-center block transition duration-200"
            >
              Go to Login Page
            </Link>
          )}
        </div>

        <div className="text-center text-sm text-gray-500 mt-6">
          <p>If you believe this is an error, please contact your system administrator.</p>
        </div>
      </div>
    </div>
  );
};

export default UnauthorizedPage; 