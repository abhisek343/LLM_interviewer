import React, { createContext, useContext, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../utils/apiClient';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    console.log("AuthContext: useEffect triggered.");
    const token = localStorage.getItem('token');
    if (token) {
      console.log("AuthContext: Token found in localStorage.");
      apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      fetchUser();
    } else {
      console.log("AuthContext: No token found in localStorage.");
      setLoading(false);
    }
  }, []);

  const fetchUser = async () => {
    console.log("AuthContext: fetchUser called.");
    setLoading(true); // Set loading to true while fetching user
    try {
      // --- Corrected Endpoint Path ---
      // The correct path for the backend user details endpoint is /auth/me
      const response = await apiClient.get('/auth/me');
      // --- End Corrected Endpoint Path ---
      console.log("AuthContext: User fetched successfully:", response.data);
      setUser(response.data);
    } catch (error) {
      console.error('AuthContext: Error fetching user:', error);
      localStorage.removeItem('token');
      delete apiClient.defaults.headers.common['Authorization'];
      setUser(null);
      console.log("AuthContext: Token and user data cleared due to fetch error.");
      // Optionally navigate to login page if fetchUser fails, indicating invalid session
      // navigate('/login');
    } finally {
      console.log("AuthContext: fetchUser finished, setting loading to false.");
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    console.log("AuthContext: login called for email:", email);
    try {
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);

      const response = await apiClient.post('/auth/login', formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });

      const { access_token, token_type } = response.data;
      console.log("AuthContext: Login API successful, received token.");

      localStorage.setItem('token', access_token);
      apiClient.defaults.headers.common['Authorization'] = `${token_type} ${access_token}`;

      // Call fetchUser to get user details using the new token
      await fetchUser();
      console.log("AuthContext: fetchUser called after successful login to populate user state.");

      return { access_token, token_type };

    } catch (error) {
      console.error('AuthContext: Login error:', error);
      throw error;
    }
  };

  const register = async (username, email, password) => {
    console.log("AuthContext: register called for email:", email);
    try {
      const response = await apiClient.post('/auth/register', {
        username,
        email,
        password,
        role: 'candidate',
      });
      console.log("AuthContext: Registration API successful.");
      return response.data;
    } catch (error) {
      console.error('AuthContext: Registration error:', error);
      throw error;
    }
  };

  const logout = () => {
    console.log("AuthContext: logout called.");
    localStorage.removeItem('token');
    delete apiClient.defaults.headers.common['Authorization'];
    setUser(null);
    console.log("AuthContext: Token and user data cleared.");
    navigate('/login');
  };

  const value = {
    user,
    loading,
    login,
    register,
    logout,
    fetchUser
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};