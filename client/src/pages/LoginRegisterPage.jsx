import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
// Assuming apiClient is correctly configured and exported from apiClient.js
// If the import error persists, double-check path, export name, and try clearing cache/restarting.
import { apiClient } from '../utils/apiClient';

const LoginRegisterPage = () => {
  const navigate = useNavigate();
  const { login } = useAuth(); // Make sure useAuth provides login
  const [isLogin, setIsLogin] = useState(true);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('candidate');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Helper function to parse FastAPI validation errors
  const getErrorMessage = (errorDetail) => {
    if (!errorDetail) {
      return 'An unknown error occurred. Please try again.';
    }
    if (typeof errorDetail === 'string') {
      return errorDetail;
    }
    // Handle FastAPI validation errors (usually an array)
    if (Array.isArray(errorDetail) && errorDetail.length > 0) {
      return errorDetail.map(err => `${err.loc.join(' -> ')}: ${err.msg}`).join('; ');
    }
    // Handle other potential object structures (less common for detail)
    if (typeof errorDetail === 'object' && errorDetail !== null) {
        // Attempt to find a message field, adapt as needed based on actual server responses
        return errorDetail.message || errorDetail.msg || JSON.stringify(errorDetail);
    }
    return 'An unexpected error format was received.';
  };


  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      let response;
      if (isLogin) {
        // --- Handle login ---
        // Use URLSearchParams to send as application/x-www-form-urlencoded
        const loginData = new URLSearchParams();
        loginData.append('username', email); // FastAPI OAuth2PasswordRequestForm expects 'username'
        loginData.append('password', password);

        response = await apiClient.post('/auth/login', loginData, {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
        });
        // Assuming login function in AuthContext handles the response.data (token, user info)
        login(response.data.user, response.data.access_token); // Adjust based on your AuthContext
        navigate('/dashboard'); // Or navigate based on user role from response.data.user.role

      } else {
        // --- Handle registration ---
        response = await apiClient.post('/auth/register', {
          username,
          email,
          password,
          role,
        });
         // Assuming login function in AuthContext handles the response.data (token, user info)
        login(response.data.user, response.data.access_token); // Adjust based on your AuthContext
        navigate('/dashboard'); // Or navigate based on user role from response.data.user.role
      }

    } catch (err) {
       console.error("API Error:", err.response); // Log the full error response for debugging
       const errorMsg = getErrorMessage(err.response?.data?.detail);
       setError(errorMsg); // Use the helper function to get a displayable message
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            {isLogin ? 'Sign in to your account' : 'Create a new account'}
          </h2>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          {/* Conditional rendering for cleaner input structure */}
          <div className="rounded-md shadow-sm -space-y-px">
             {/* Username (Register only) */}
            {!isLogin && (
              <div>
                <label htmlFor="username" className="sr-only">
                  Username
                </label>
                <input
                  id="username"
                  name="username"
                  type="text"
                  required
                  className="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                  placeholder="Username (e.g., John)"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </div>
            )}

            {/* Email */}
            <div>
              <label htmlFor="email" className="sr-only">
                Email address
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                // Apply rounded-t-md class only if it's the first visible input
                className={`appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 ${isLogin ? 'rounded-t-md' : ''} focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm`}
                placeholder="Email address (e.g., example@xyz.com)"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            {/* Password */}
            <div>
              <label htmlFor="password" className="sr-only">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete={isLogin ? 'current-password' : 'new-password'}
                required
                 // Apply rounded-b-md class only if it's the last visible input (before role dropdown)
                className={`appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 ${isLogin || !isLogin ? 'rounded-b-md' : ''} focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm`}
                placeholder="Password (e.g., 12345678)"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

             {/* Role (Register only) */}
             {!isLogin && (
                <div className="pt-2"> {/* Add some padding top */}
                    <label htmlFor="role" className="sr-only">
                    Role
                    </label>
                    <select
                    id="role"
                    name="role"
                    required
                    className="appearance-none rounded-md relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    >
                    <option value="candidate">Candidate</option>
                    <option value="hr">HR</option>
                    {/* Keep admin registration disabled from UI unless intended */}
                    {/* <option value="admin">Admin</option> */}
                    </select>
                </div>
             )}
          </div>

          {/* Error Display */}
          {error && (
            <div className="text-red-600 text-sm text-center bg-red-100 border border-red-400 p-2 rounded">
                <p>Error:</p>
                <p>{error}</p>
            </div>
          )}

          <div>
            <button
              type="submit"
              disabled={loading}
              className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
            >
              {loading ? 'Processing...' : isLogin ? 'Sign in' : 'Register'}
            </button>
          </div>
        </form>

        <div className="text-center">
          <button
            type="button"
            className="text-sm font-medium text-indigo-600 hover:text-indigo-500"
            onClick={() => setIsLogin(!isLogin)}
          >
            {isLogin
              ? "Don't have an account? Register"
              : 'Already have an account? Sign in'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default LoginRegisterPage;