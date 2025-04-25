import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const NotFoundPage = () => {
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
          <h1 className="text-4xl font-bold text-yellow-500 mb-4">404 - Page Not Found</h1>
          <div className="text-6xl mb-6">🔍</div>
          <p className="text-gray-300 mb-6">
            The page you're looking for doesn't exist or has been moved. Here are some helpful links:
          </p>
        </div>

        <div className="space-y-4">
          {user ? (
            <>
              <p className="text-gray-300 text-center">
                You are currently logged in as: <span className="font-semibold">{user.username}</span> ({user.role})
              </p>
              <div className="flex flex-col space-y-3">
                <Link
                  to="/dashboard"
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-md text-center transition duration-200"
                >
                  Go to Dashboard
                </Link>
                <button
                  onClick={handleLogout}
                  className="w-full bg-red-600 hover:bg-red-700 text-white font-bold py-2 px-4 rounded-md transition duration-200"
                >
                  Logout
                </button>
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

export default NotFoundPage; 