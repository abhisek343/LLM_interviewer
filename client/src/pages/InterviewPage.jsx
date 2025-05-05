import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import Layout from '../components/Layout';
import { interviewAPI } from '../utils/apiClient';
// import Spinner from '../components/Spinner'; // Import or define a spinner component

const InterviewPage = () => {
  const { interviewId } = useParams();
  const navigate = useNavigate();

  // State
  const [interviewData, setInterviewData] = useState(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [currentAnswer, setCurrentAnswer] = useState('');
  const [allAnswers, setAllAnswers] = useState({});
  const [loading, setLoading] = useState(true); // For initial fetch
  const [error, setError] = useState(null); // For fetch or general errors
  const [isSubmitting, setIsSubmitting] = useState(false); // For final submission
  const [submitError, setSubmitError] = useState(null); // Specific error during submission

  // Fetch Interview Details
  const fetchInterview = useCallback(async () => {
    if (!interviewId) { setError("Interview ID missing from URL."); setLoading(false); return; }
    setLoading(true); setError(null); setSubmitError(null); // Reset errors on fetch
    try {
      const response = await interviewAPI.getInterviewDetails(interviewId);
      // Basic validation
      if (!response.data || !response.data.questions || response.data.questions.length === 0) {
        throw new Error("Interview details or questions could not be loaded.");
      }
      if (response.data.status === 'completed') {
        throw new Error("This interview has already been completed. Redirecting...");
      }
      setInterviewData(response.data);
      // Initialize answers state
      const initialAnswers = {};
      response.data.questions.forEach(q => { initialAnswers[q.question_id] = ''; });
      setAllAnswers(initialAnswers);
    } catch (err) {
      console.error("Fetch Interview Error:", err);
      const errorMsg = err.detail || err.message || "Failed to load interview data.";
      setError(errorMsg); // Set fetch error
      if (errorMsg.includes("completed")) {
        // Optionally redirect if already completed after showing message briefly
        setTimeout(() => navigate('/dashboard'), 3000);
      }
    } finally {
      setLoading(false);
    }
  }, [interviewId, navigate]); // Include navigate if used in effect

  useEffect(() => { fetchInterview(); }, [fetchInterview]);

  // Handlers
  const handleAnswerChange = (event) => { setCurrentAnswer(event.target.value); };

  const saveCurrentAnswer = useCallback(() => {
     if (interviewData?.questions[currentQuestionIndex]) {
        const currentQuestionId = interviewData.questions[currentQuestionIndex].question_id;
        setAllAnswers(prev => ({ ...prev, [currentQuestionId]: currentAnswer }));
     }
  }, [currentQuestionIndex, currentAnswer, interviewData]);

  const handleNextQuestion = () => { saveCurrentAnswer(); if (currentQuestionIndex < interviewData.questions.length - 1) { const nextIdx = currentQuestionIndex + 1; const nextQId = interviewData.questions[nextIdx].question_id; setCurrentQuestionIndex(nextIdx); setCurrentAnswer(allAnswers[nextQId] || ''); } };
  const handlePreviousQuestion = () => { saveCurrentAnswer(); if (currentQuestionIndex > 0) { const prevIdx = currentQuestionIndex - 1; const prevQId = interviewData.questions[prevIdx].question_id; setCurrentQuestionIndex(prevIdx); setCurrentAnswer(allAnswers[prevQId] || ''); } };

  const handleSubmitInterview = async () => {
    saveCurrentAnswer();
    const finalAnswersMap = { ...allAnswers };
    if (interviewData?.questions[currentQuestionIndex]) {
        finalAnswersMap[interviewData.questions[currentQuestionIndex].question_id] = currentAnswer;
    }

    setIsSubmitting(true); setSubmitError(null); setError(null);

    const responsesPayload = Object.entries(finalAnswersMap).map(([qId, ans]) => ({
      question_id: qId, answer: ans.trim()
    }));
    const submissionData = { interview_id: interviewId, responses: responsesPayload };

    try {
      await interviewAPI.submitAllResponses(submissionData);
      alert("Interview submitted successfully! Redirecting..."); // Keep alert for now or replace with toast
      navigate(`/results/${interviewId}`);
    } catch (err) {
      console.error("Submit Interview Error:", err);
      const errorMsg = err.detail || err.message || "An unexpected error occurred during submission.";
      setSubmitError(errorMsg); // Set specific submission error
      setIsSubmitting(false);
    }
  };

  // --- Render Logic Refined ---

  // Loading state during initial fetch
  const renderLoading = () => (
      <div className="flex justify-center items-center min-h-[calc(100vh-100px)]"> {/* Adjusted height */}
           <div role="status" className="flex items-center space-x-2">
                <svg className="animate-spin h-8 w-8 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span className="text-gray-300 text-lg">Loading interview questions...</span>
           </div>
        </div>
  );

  // Error state during initial fetch or fatal error
  const renderError = (errorMsg) => (
       <div className="max-w-2xl mx-auto p-6 mt-10 bg-red-900 border border-red-700 rounded-lg text-center shadow-lg">
          <h2 className="text-xl font-semibold mb-3 text-red-100">Error Loading Interview</h2>
          <p className="text-red-200 mb-4">{errorMsg}</p>
          <Link to="/dashboard" className="bg-red-600 hover:bg-red-700 text-white px-5 py-2 rounded-md text-sm transition duration-150"> Go Back to Dashboard </Link>
       </div>
  );

  if (loading) return <Layout>{renderLoading()}</Layout>;
  if (error) return <Layout>{renderError(error)}</Layout>; // Show fatal fetch error
  if (!interviewData) return <Layout><p className="text-center text-gray-400">Could not load interview data.</p></Layout>; // Fallback

  // Main interview display
  const currentQuestion = interviewData.questions[currentQuestionIndex];
  const totalQuestions = interviewData.questions.length;
  const isLastQuestion = currentQuestionIndex === totalQuestions - 1;

  return (
    <Layout>
      <div className="max-w-3xl mx-auto p-4 md:p-6">
        <div className="bg-gray-800 p-6 rounded-lg shadow-xl border border-gray-700">
          {/* Header */}
          <div className="text-center mb-4">
              <h2 className="text-2xl font-bold text-blue-300"> {interviewData.role || 'Technical'} Interview </h2>
              <p className="text-sm text-gray-400 mt-1"> Question {currentQuestionIndex + 1} of {totalQuestions} </p>
          </div>

          {/* Question Display */}
          <div className="mb-5 p-4 bg-gray-700 rounded border border-gray-600 min-h-[100px] shadow-inner">
             <p className="font-semibold text-lg text-white mb-1"> {currentQuestion?.text || 'Loading question...'} </p>
             <p className="text-xs text-gray-400"> Category: {currentQuestion?.category || 'N/A'} | Difficulty: {currentQuestion?.difficulty || 'N/A'} </p>
          </div>

          {/* Answer Input */}
          <div className="mb-6">
            <label htmlFor="answer" className="block text-sm font-medium text-gray-300 mb-1"> Your Answer: </label>
            <textarea id="answer" rows="14" /* Further increased rows */
              className={`w-full p-3 rounded-md bg-gray-900 border ${submitError ? 'border-red-500 focus:border-red-500 focus:ring-red-500' : 'border-gray-600 focus:border-blue-500 focus:ring-blue-500'} text-white focus:ring-1 transition duration-150 ease-in-out`}
              placeholder="Type your answer here..."
              value={currentAnswer}
              onChange={handleAnswerChange}
              disabled={isSubmitting}
            />
          </div>

          {/* Submission Error Display */}
          {submitError && (
             <div className="my-4 p-3 bg-red-900 border border-red-700 text-red-200 rounded text-sm text-center shadow">
                <strong>Submission Error:</strong> {submitError}
             </div>
          )}

          {/* Navigation Buttons */}
          <div className="flex justify-between items-center mt-4">
              <button onClick={handlePreviousQuestion}
                 className="bg-gray-600 hover:bg-gray-500 text-white px-5 py-2 rounded-md transition duration-150 disabled:opacity-50 disabled:cursor-not-allowed shadow-md"
                 disabled={currentQuestionIndex === 0 || isSubmitting}
              > Previous </button>

              {!isLastQuestion ? (
                <button onClick={handleNextQuestion}
                   className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2 rounded-md transition duration-150 disabled:opacity-50 shadow-md"
                   disabled={isSubmitting}
                > Next Question </button>
              ) : (
                <button onClick={handleSubmitInterview}
                  className="bg-green-600 hover:bg-green-700 text-white px-5 py-2 rounded-md transition duration-150 disabled:opacity-50 flex items-center space-x-2 shadow-md"
                  disabled={isSubmitting}
                >
                  {isSubmitting && (
                     <svg className="animate-spin -ml-1 mr-1 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                  )}
                  <span>{isSubmitting ? 'Submitting...' : 'Submit Interview'}</span>
                </button>
              )}
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default InterviewPage;