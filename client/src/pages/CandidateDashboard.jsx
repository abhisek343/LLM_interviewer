// client/src/pages/CandidateDashboard.test.jsx

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock dependencies
import { AuthProvider, useAuth } from '../contexts/AuthContext';
import { interviewAPI, candidateAPI } from '../utils/apiClient'; // Mock specific APIs
import CandidateDashboard from './CandidateDashboard';

// --- Mocking ---
vi.mock('../utils/apiClient', () => ({
  interviewAPI: {
    getCandidateInterviews: vi.fn(),
  },
  candidateAPI: {
    uploadResume: vi.fn(),
  },
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
    const actual = await importOriginal();
    return {
        ...actual,
        useNavigate: () => mockNavigate,
        Link: ({ children, to }) => <a href={to}>{children}</a>,
    };
});

const mockUser = {
    id: 'cand123',
    email: 'candidate@example.com',
    username: 'candidateuser',
    role: 'candidate'
};
vi.mock('../contexts/AuthContext', async (importOriginal) => {
    const actual = await importOriginal();
    return {
        ...actual,
        useAuth: () => ({
            user: mockUser,
            loading: false,
        }),
    };
});
// --- End Mocking ---


// Helper function - Render component with default mocks
const renderComponentWithDefaults = () => {
    // Reset mocks before each render
    vi.clearAllMocks();
    // ** Apply DEFAULT mocks used by most tests **
    interviewAPI.getCandidateInterviews.mockResolvedValue({ data: [] }); // Default: No interviews
    candidateAPI.uploadResume.mockResolvedValue({ data: { message: 'Success', parsing_status: 'ok' } }); // Default: Success

    return render(
        <BrowserRouter>
        <AuthProvider>
            <CandidateDashboard />
        </AuthProvider>
        </BrowserRouter>
    );
}


// --- Test Suite ---
describe('CandidateDashboard Component', () => {

  // Clear mocks between tests for safety
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders welcome message, resume upload, and interviews section', async () => {
    // Setup default mocks for this test case specifically
    interviewAPI.getCandidateInterviews.mockResolvedValue({ data: [] });
    candidateAPI.uploadResume.mockResolvedValue({ data: { message: 'Success', parsing_status: 'ok' } });

    render(
        <BrowserRouter><AuthProvider><CandidateDashboard /></AuthProvider></BrowserRouter>
    );

    expect(screen.getByText(/Welcome, candidateuser!/i)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /upload\/update resume/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /your interviews/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/choose file/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /upload resume/i })).toBeInTheDocument();
    expect(await screen.findByText(/no interviews scheduled/i)).toBeInTheDocument();
  });

  it('displays loading state while fetching interviews', () => {
      interviewAPI.getCandidateInterviews.mockImplementation(() => new Promise(() => {})); // Never resolve
      render(
        <BrowserRouter><AuthProvider><CandidateDashboard /></AuthProvider></BrowserRouter>
      );
      // Check for loading indicator (adjust text/role if needed)
      expect(screen.getByText(/loading interviews.../i)).toBeInTheDocument(); // Or check for a spinner role
  });

   it('displays error message if fetching interviews fails', async () => {
      const errorMsg = "Network Error fetching interviews";
      interviewAPI.getCandidateInterviews.mockRejectedValue({ response: { data: { detail: errorMsg } } }); // Simulate API error structure
      render(
        <BrowserRouter><AuthProvider><CandidateDashboard /></AuthProvider></BrowserRouter>
      );

      // ** Check how the error is ACTUALLY rendered in your component **
      // Option 1: If it's plain text within a specific role (e.g., alert)
      const errorAlert = await screen.findByRole('alert'); // Assuming you use role="alert" for errors
      expect(errorAlert).toHaveTextContent(new RegExp(errorMsg, 'i'));

      // Option 2: If it's just text somewhere
      // expect(await screen.findByText(new RegExp(errorMsg, 'i'))).toBeInTheDocument();
  });

  it('displays fetched interviews correctly', async () => {
    // ** VERIFY mockInterviews structure matches EXACT backend response **
    const mockInterviews = [
      { id: 'db_id_1', interview_id: 'int1', candidate_id: mockUser.id, scheduled_time: new Date().toISOString(), role: 'Frontend Dev', tech_stack: ['React', 'JS'], status: 'scheduled', /* other fields */ },
      { id: 'db_id_2', interview_id: 'int2', candidate_id: mockUser.id, scheduled_time: new Date().toISOString(), role: 'Backend Dev', tech_stack: ['Python'], status: 'completed', /* other fields */ },
    ];
    // Set mock BEFORE rendering
    interviewAPI.getCandidateInterviews.mockResolvedValue({ data: mockInterviews });
    render(
        <BrowserRouter><AuthProvider><CandidateDashboard /></AuthProvider></BrowserRouter>
    );

    expect(await screen.findByText(/frontend dev/i)).toBeInTheDocument();
    expect(await screen.findByText(/backend dev/i)).toBeInTheDocument();
    expect(screen.getByText(/React, JS/i)).toBeInTheDocument();
    expect(screen.getByText(/Python/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /start interview/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /view results/i })).toBeInTheDocument();
  });

  it('handles resume file selection and enables upload button', async () => {
    // Setup default mocks
    interviewAPI.getCandidateInterviews.mockResolvedValue({ data: [] });
    candidateAPI.uploadResume.mockResolvedValue({ data: { message: 'Success', parsing_status: 'ok' } });
    render(
        <BrowserRouter><AuthProvider><CandidateDashboard /></AuthProvider></BrowserRouter>
    );
    const fileInput = screen.getByLabelText(/choose file/i);
    const uploadButton = screen.getByRole('button', { name: /upload resume/i });

    expect(uploadButton).toBeDisabled();
    const file = new File(['dummy content'], 'resume.pdf', { type: 'application/pdf' });
    await userEvent.upload(fileInput, file);

    expect(uploadButton).toBeEnabled();
    expect(screen.getByText(/selected: resume.pdf/i)).toBeInTheDocument();
  });

  it('calls candidateAPI.uploadResume on form submission and shows success', async () => {
    // Setup default mocks
    interviewAPI.getCandidateInterviews.mockResolvedValue({ data: [] });
    candidateAPI.uploadResume.mockResolvedValue({ data: { message: 'Success', parsing_status: 'ok' } });
    render(
        <BrowserRouter><AuthProvider><CandidateDashboard /></AuthProvider></BrowserRouter>
    );

    const fileInput = screen.getByLabelText(/choose file/i);
    const uploadButton = screen.getByRole('button', { name: /upload resume/i });
    const file = new File(['dummy content'], 'resume.pdf', { type: 'application/pdf' });

    await userEvent.upload(fileInput, file);
    expect(uploadButton).toBeEnabled();
    await userEvent.click(uploadButton);

    await waitFor(() => {
        expect(candidateAPI.uploadResume).toHaveBeenCalledTimes(1);
        // ... (rest of assertion is likely okay)
    });

    // ** Check how success message is ACTUALLY rendered **
    // E.g., if using an Alert component with role="status" or "alert"
    const successAlert = await screen.findByRole('status'); // Or 'alert' depending on implementation
    expect(successAlert).toHaveTextContent(/resume uploaded successfully!/i);

    // Fallback if it's just plain text
    // expect(await screen.findByText(/resume uploaded successfully!/i)).toBeInTheDocument();
  });

  // --- FAILING TEST ---
  it('displays error message on resume upload failure', async () => {
      const uploadErrorMsg = "Invalid file type";
      // Set mock BEFORE rendering
      candidateAPI.uploadResume.mockRejectedValue({ response: { data: { detail: uploadErrorMsg } } }); // Simulate specific API error structure
      interviewAPI.getCandidateInterviews.mockResolvedValue({ data: [] }); // Still need this default

      render(
        <BrowserRouter><AuthProvider><CandidateDashboard /></AuthProvider></BrowserRouter>
      );

      const fileInput = screen.getByLabelText(/choose file/i);
      const uploadButton = screen.getByRole('button', { name: /upload resume/i });
      const file = new File(['dummy content'], 'resume.txt', { type: 'text/plain' });

      await userEvent.upload(fileInput, file);
      await userEvent.click(uploadButton);

      // ** ADJUST this query based on how your component shows the error **
      // Option 1: If inside an element with role="alert"
      const errorAlert = await screen.findByRole('alert');
      // Check the exact text content or use regex. Maybe the prefix "Upload failed: " is added by the component?
      expect(errorAlert).toHaveTextContent(`Upload failed: ${uploadErrorMsg}`); // Or use regex: /Upload failed: Invalid file type/i

      // Option 2: If just plain text (less likely for good UI)
      // expect(await screen.findByText(`Upload failed: ${uploadErrorMsg}`)).toBeInTheDocument();

  });

   // --- FAILING TEST ---
   it('navigates when "Start Interview" button is clicked', async () => {
      const mockScheduledInterview = [{
           id: 'db_id_sched', interview_id: 'int_sched', /* other required fields */ status: 'scheduled', role: 'Scheduled Role', tech_stack: ['T'],
       }];
      // Set mock BEFORE rendering
      interviewAPI.getCandidateInterviews.mockResolvedValue({ data: mockScheduledInterview });

      render(
        <BrowserRouter><AuthProvider><CandidateDashboard /></AuthProvider></BrowserRouter>
      );

      // Find the button (it should appear now that mock is set first)
      const startButton = await screen.findByRole('button', { name: /start interview/i });
      await userEvent.click(startButton);

      expect(mockNavigate).toHaveBeenCalledTimes(1);
      expect(mockNavigate).toHaveBeenCalledWith('/interview/int_sched');
  });

    // --- FAILING TEST ---
    it('navigates when "View Results" button is clicked', async () => {
       const mockCompletedInterview = [{
            id: 'db_id_comp', interview_id: 'int_comp', /* other required fields */ status: 'completed', role: 'Completed Role', tech_stack: ['T'],
       }];
       // Set mock BEFORE rendering
      interviewAPI.getCandidateInterviews.mockResolvedValue({ data: mockCompletedInterview });

      render(
        <BrowserRouter><AuthProvider><CandidateDashboard /></AuthProvider></BrowserRouter>
      );

      // Find the button
      const resultsButton = await screen.findByRole('button', { name: /view results/i });
      await userEvent.click(resultsButton);

      expect(mockNavigate).toHaveBeenCalledTimes(1);
      expect(mockNavigate).toHaveBeenCalledWith('/results/int_comp');
  });

   it('renders links to profile and history pages', async () => {
       // Setup default mocks
       interviewAPI.getCandidateInterviews.mockResolvedValue({ data: [] });
       render(
        <BrowserRouter><AuthProvider><CandidateDashboard /></AuthProvider></BrowserRouter>
       );
       expect(await screen.findByRole('link', { name: /view\/edit profile/i })).toHaveAttribute('href', '/candidate/profile');
       expect(await screen.findByRole('link', { name: /view interview history/i })).toHaveAttribute('href', '/candidate/history');
   });

});