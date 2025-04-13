import axios from 'axios';

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Create axios instance with default config
const apiClient = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor to include auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add response interceptor to handle errors
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized access
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  login: (data) => apiClient.post('/auth/login', data),
  register: (data) => apiClient.post('/auth/register', data),
};

// Interview API
export const interviewAPI = {
  schedule: (data) => apiClient.post('/interview/schedule', data),
  getResults: (candidateId) => apiClient.get(`/interview/results/${candidateId}`),
  submitResponse: (data) => apiClient.post('/interview/submit-response', data),
  getCandidateInterviews: () => apiClient.get('/interview/candidate/me'),
};

// Candidate API
export const candidateAPI = {
  uploadResume: (formData) => apiClient.post('/candidate/resume', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  }),
};

// Admin API
export const adminAPI = {
  getUsers: () => apiClient.get('/admin/users'),
  getSystemStatus: () => apiClient.get('/admin/system-status'),
};

export { apiClient }; 