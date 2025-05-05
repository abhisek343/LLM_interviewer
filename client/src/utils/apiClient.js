import axios from 'axios';

// Ensure the environment variable is read correctly, with a fallback
const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
// console.log(`API Base URL: ${baseURL}`); // Log for debugging

// Create axios instance with default config
const apiClient = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
  // timeout: 10000, // Consider adding a timeout
});

// --- Interceptors ---
// Request Interceptor: Add Auth Token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    console.error("Request Interceptor Error:", error);
    return Promise.reject(error);
  }
);
// Response Interceptor: Handle Global Errors
apiClient.interceptors.response.use(
  (response) => {
    return response;
    },
  (error) => {
    // Log detailed error information
    console.error(`API Error: ${error.message}`, error.config, error.response || error.request || error); //

    if (error.response) {
      const { status, data, config } = error.response;
      console.error(`Error ${status} from ${config.url}:`, data);

      if (status === 401) {
        console.warn("Unauthorized access (401). Logging out and redirecting to login.");
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      } else if (status === 403) {
        console.warn("Forbidden access (403). User lacks permission for this resource.");
      }
    } else if (error.request) {
      console.error("Network Error: No response received from server.", error.request);
    } else {
       console.error('Error during request setup:', error.message);
    }
    return Promise.reject(error.response?.data || error.message || error);
  }
);
// --- End Interceptors ---


// --- API Modules ---

// Auth API
export const authAPI = {
  // Use the version from previous modifications that sends form data
  login: (credentials) => {
     const formData = new URLSearchParams();
     formData.append('username', credentials.email);
     formData.append('password', credentials.password);
     return apiClient.post('/auth/login', formData, { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } });
  },
  register: (userData) => apiClient.post('/auth/register', userData), //
  // Assuming getCurrentUser was added previously based on context needs
  getCurrentUser: () => apiClient.get('/auth/me'),
};

// Interview API
export const interviewAPI = {
  // Use the version from previous modifications including all needed functions
  schedule: (interviewData) => apiClient.post('/interview/schedule', interviewData),
  getInterviewDetails: (interviewId) => apiClient.get(`/interview/${interviewId}`),
  getAllInterviews: () => apiClient.get('/interview/all'),
  getAllResults: () => apiClient.get('/interview/results/all'), // Fetches completed InterviewOut for HR/Admin
  getSingleInterviewResult: (interviewId) => apiClient.get(`/interview/results/${interviewId}`), // Fetches potentially calculated result
  getInterviewResponsesList: (interviewId) => apiClient.get(`/interview/${interviewId}/responses`),
  getCandidateInterviews: () => apiClient.get('/interview/candidate/me'), // Fetches active/scheduled
  submitResponse: (responseData) => apiClient.post('/interview/submit-response', responseData), // Single response
  submitAllResponses: (submissionData) => apiClient.post('/interview/submit-all', submissionData), // Bulk candidate submission
  submitInterviewResult: (interviewId, resultData) => apiClient.post(`/interview/${interviewId}/results`, resultData), // HR/Admin manual results submission (incl per-response)
  // --- Added: Trigger AI Evaluation for a Response ---
  evaluateResponseWithAI: (responseId) => {
      // Makes a POST request to trigger evaluation, expects updated InterviewResponseOut back
      // The backend endpoint is POST /interview/responses/{response_id}/evaluate
      return apiClient.post(`/interview/responses/${responseId}/evaluate`); // No request body needed
  },
  // --- End Added ---
};

// Candidate Specific API
export const candidateAPI = {
  // Use the version from previous modifications
  uploadResume: (formData) => apiClient.post('/candidate/resume', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  getProfile: () => apiClient.get('/candidate/profile'),
  updateProfile: (profileData) => apiClient.put('/candidate/profile', profileData),
  getInterviewHistory: () => apiClient.get('/interview/candidate/history'),
};

// Admin Specific API
export const adminAPI = {
  // Use the version from previous modifications including deleteUser
  getUsers: () => apiClient.get('/admin/users'),
  getSystemStats: () => apiClient.get('/admin/stats'),
  deleteUser: (userId) => apiClient.delete(`/admin/users/${userId}`),
};

// Export the configured instance (keep if needed)
// export default apiClient; // Keep named export pattern below
export { apiClient };