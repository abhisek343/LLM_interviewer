import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { useAuth } from './contexts/AuthContext';
import LoginRegisterPage from './pages/LoginRegisterPage';
import CandidateDashboard from './pages/CandidateDashboard';
import HRDashboard from './pages/HRDashboard';
import AdminDashboard from './pages/AdminDashboard';
import UnauthorizedPage from './pages/UnauthorizedPage';
import NotFoundPage from './pages/NotFoundPage';
import ServerErrorPage from './pages/ServerErrorPage';

// --- Import Page Components ---
import ResultDetailPage from './pages/ResultDetailPage'; // Import the results page
// import InterviewPage from './pages/InterviewPage'; // Placeholder import - This component needs to be created

// --- End Import Page Components ---

// Theme definition (remains the same)
const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: '#1976d2' },
    secondary: { main: '#dc004e', },
    background: { default: '#1a1a1a', paper: '#2d2d2d', },
    error: { main: '#f44336', },
    warning: { main: '#ff9800', },
  },
});

// Protected Route component (remains the same, assuming it's defined correctly)
const ProtectedRoute = ({ children, allowedRoles }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
        <p className="mt-4 text-gray-300">Loading user data...</p>
      </div>
    </div>;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return children;
};

// Role-based dashboard component (remains the same)
const RoleBasedDashboard = () => {
  const { user, loading } = useAuth();

   if (loading) {
       return <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
           {/* Spinner */}
       </div>;
   }

  switch (user?.role) {
    case 'candidate': return <CandidateDashboard />;
    case 'hr': return <HRDashboard />;
    case 'admin': return <AdminDashboard />;
    default: return <Navigate to="/unauthorized" replace />;
  }
};

// Error boundary component (remains the same)
class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { hasError: false, error: null }; }
  static getDerivedStateFromError(error) { return { hasError: true, error: error }; }
  componentDidCatch(error, errorInfo) { console.error('Error caught by boundary:', error, errorInfo); }
  render() { if (this.state.hasError) { return <ServerErrorPage error={this.state.error} />; } return this.props.children; }
}

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <ErrorBoundary>
        <Routes>
          {/* Public Routes */}
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="/login" element={<LoginRegisterPage />} />
          <Route path="/unauthorized" element={<UnauthorizedPage />} />
          <Route path="/500" element={<ServerErrorPage />} />

          {/* Protected Routes */}
          <Route
                path="/dashboard"
                element={
                     <ProtectedRoute allowedRoles={['candidate', 'hr', 'admin']}>
                         <RoleBasedDashboard />
                     </ProtectedRoute>
                 }
            />

           {/* --- Added/Updated Interview and Result Routes --- */}

           {/* Route for Candidate taking an interview */}
           <Route
                path="/interview/:interviewId"
                element={
                    <ProtectedRoute allowedRoles={['candidate']}> {/* Only candidates take interviews */}
                        {/* This component needs to be created: client/src/pages/InterviewPage.jsx */}
                        {/* <InterviewPage /> */}
                        <div>Interview Page Placeholder (Interview ID: {':interviewId'})</div> {/* Placeholder content */}
                    </ProtectedRoute>
                }
            />

           {/* Route for viewing interview results */}
           <Route
                path="/results/:interviewId"
                element={
                    <ProtectedRoute allowedRoles={['candidate', 'hr', 'admin']}> {/* Candidate, HR, Admin can view */}
                        <ResultDetailPage />
                    </ProtectedRoute>
                }
            />

           {/* --- End Added/Updated Routes --- */}


          {/* Catch-all for not found pages */}
          <Route path="*" element={<NotFoundPage />} />

        </Routes>
      </ErrorBoundary>
    </ThemeProvider>
  );
}

export default App;