import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const ServerErrorPage = () => {
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
          <h1 className="text-4xl font-bold text-red-500 mb-4">500 - Server Error</h1>
          <div className="text-6xl mb-6">⚠️</div>
          <p className="text-gray-300 mb-6">
            Something went wrong on our end. We're working to fix the issue. In the meantime, you can:
          </p>
          <ul className="text-left text-gray-400 space-y-2 mb-6">
            <li>• Try refreshing the page</li>
            <li>• Check your internet connection</li>
            <li>• Try again in a few minutes</li>
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
                  onClick={() => window.location.reload()}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-md transition duration-200"
                >
                  Refresh Page
                </button>
                <Link
                  to="/dashboard"
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-md text-center transition duration-200"
                >
                  Return to Dashboard
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
          <p>If the problem persists, please contact your system administrator.</p>
        </div>
      </div>
    </div>
  );
};

export default ServerErrorPage; 