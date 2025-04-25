import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

// --- React Toastify Imports ---
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
// --- End Imports ---


const Layout = ({ children }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* --- Toast Container --- */}
      {/* Add the container here. Position, theme, etc., can be configured. */}
      {/* It doesn't render anything visible itself until a toast is triggered. */}
      <ToastContainer
        position="top-right" // Or 'top-center', 'bottom-right', etc.
        autoClose={5000} // Auto close after 5 seconds
        hideProgressBar={false}
        newestOnTop={false}
        closeOnClick
        rtl={false}
        pauseOnFocusLoss
        draggable
        pauseOnHover
        theme="dark" // Use 'dark', 'light', or 'colored'
        // transition: Bounce // Optional transition effect
      />
      {/* --- End Toast Container --- */}

      {/* Navigation Bar */}
      <nav className="bg-gray-800 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center">
              <Link to="/dashboard" className="text-xl font-bold text-white">
                LLM Interview System
              </Link>
            </div>

            {user && (
              <div className="flex items-center space-x-4">
                <span className="text-gray-300 text-sm md:text-base"> {/* Added responsive text size */}
                   Welcome, {user.username || user.email} {/* Show username if available */}
                   <span className="hidden sm:inline"> ({user.role})</span> {/* Hide role on very small screens */}
                </span>
                <button
                  onClick={handleLogout}
                  className="bg-red-600 hover:bg-red-700 text-white px-3 py-1.5 md:px-4 md:py-2 rounded-md text-xs md:text-sm font-medium transition duration-150" /* Adjusted padding/size */
                >
                  Logout
                </button>
              </div>
            )}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        {children}
      </main>

      {/* Optional Footer */}
      {/* <footer className="bg-gray-800 mt-auto">
          <div className="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8 text-center text-gray-400 text-xs">
             &copy; {new Date().getFullYear()} LLM Interviewer. All rights reserved.
          </div>
      </footer> */}
    </div>
  );
};

export default Layout;