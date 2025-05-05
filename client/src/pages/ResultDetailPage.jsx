import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import Layout from '../components/Layout'; // Assuming Layout component exists
import { interviewAPI } from '../utils/apiClient'; // Import the API functions
import { useAuth } from '../contexts/AuthContext'; // Import useAuth to check user role

const ResultDetailPage = () => {
  const { interviewId } = useParams(); // Get interviewId from URL parameters
  const { user } = useAuth(); // Get current user from AuthContext

  // State for fetched data
  const [resultData, setResultData] = useState(null); // From GET /results/{id}
  const [interviewDetails, setInterviewDetails] = useState(null); // From GET /interview/{id}
  const [responses, setResponses] = useState([]); // From GET /interview/{id}/responses
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(null); // Separate error for fetching

  // State for result submission form (for HR/Admin)
  const [overallScoreInput, setOverallScoreInput] = useState('');
  const [overallFeedbackInput, setOverallFeedbackInput] = useState('');
  // State for per-response feedback inputs
  const [responseFeedbacks, setResponseFeedbacks] = useState({}); // { question_id: { score: '', feedback: '' } }

  // UI states for submission/evaluation actions
  const [isSubmittingManualResult, setIsSubmittingManualResult] = useState(false);
  const [manualSubmitError, setManualSubmitError] = useState(null);
  const [manualSubmitSuccess, setManualSubmitSuccess] = useState(null);
  // State for AI evaluation status per response
  const [aiEvalStatus, setAiEvalStatus] = useState({}); // { response_id: { loading: boolean, error: string | null } }


  // Initialize feedback state based on fetched responses
  const initializeFeedbackState = useCallback((fetchedResponses) => {
    const initialFeedbacks = {};
    fetchedResponses.forEach(resp => {
      const qId = resp.question_id || null;
      if (qId) {
          initialFeedbacks[qId] = {
            score: resp.score !== null ? resp.score.toString() : '',
            feedback: resp.feedback || ''
          };
      }
    });
    setResponseFeedbacks(initialFeedbacks);
  }, []);

  // Fetch all necessary data
  const fetchAllData = useCallback(async () => {
    if (!interviewId) { setFetchError("Interview ID not found."); setLoading(false); return; }
    setLoading(true); setFetchError(null); setManualSubmitError(null); setManualSubmitSuccess(null); setAiEvalStatus({});
    try {
      // Fetch results, details, and responses concurrently
      const [resultRes, detailsRes, responsesRes] = await Promise.allSettled([
        interviewAPI.getSingleInterviewResult(interviewId),
        interviewAPI.getInterviewDetails(interviewId),
        interviewAPI.getInterviewResponsesList(interviewId)
      ]);
      let fetchedResultData = null; let fetchedInterviewDetails = null; let fetchedResponses = []; let errors = [];

      // Process result summary
      if (resultRes.status === 'fulfilled') {
         fetchedResultData = resultRes.value.data;
         setOverallScoreInput(fetchedResultData?.total_score !== null ? fetchedResultData.total_score.toString() : '');
         setOverallFeedbackInput(fetchedResultData?.overall_feedback || '');
      } else { errors.push(`Result Summary Error: ${resultRes.reason?.detail || resultRes.reason?.message || 'Unknown'}`); }

      // Process interview details
      if (detailsRes.status === 'fulfilled') { fetchedInterviewDetails = detailsRes.value.data; }
      else { errors.push(`Interview Details Error: ${detailsRes.reason?.detail || detailsRes.reason?.message || 'Unknown'}`); }

      // Process responses and initialize feedback state
      if (responsesRes.status === 'fulfilled') {
          fetchedResponses = responsesRes.value.data;
          setResponses(fetchedResponses);
          initializeFeedbackState(fetchedResponses);
      } else { errors.push(`Responses Error: ${responsesRes.reason?.detail || responsesRes.reason?.message || 'Unknown'}`); }

      setResultData(fetchedResultData); setInterviewDetails(fetchedInterviewDetails);
      if (errors.length > 0) { setFetchError(errors.join('; ')); } // Combine errors if multiple fetches failed
    } catch (err) { console.error("Fetch Error:", err); setFetchError(`Unexpected error loading data. ${err.message || err}`); }
    finally { setLoading(false); }
  }, [interviewId, initializeFeedbackState]); // Dependencies

  useEffect(() => { fetchAllData(); }, [fetchAllData]); // Fetch data on mount/id change

  // Handlers for manual per-response feedback inputs
  const handleResponseScoreChange = (questionId, value) => { setResponseFeedbacks(prev => ({ ...prev, [questionId]: { ...prev[questionId], score: value } })); setManualSubmitError(null); setManualSubmitSuccess(null); };
  const handleResponseFeedbackChange = (questionId, value) => { setResponseFeedbacks(prev => ({ ...prev, [questionId]: { ...prev[questionId], feedback: value } })); setManualSubmitError(null); setManualSubmitSuccess(null); };

  // Handle MANUAL Score/Feedback Submission by HR/Admin
  const handleManualResultSubmit = async (e) => {
     e.preventDefault();
     setIsSubmittingManualResult(true); setManualSubmitError(null); setManualSubmitSuccess(null);
     const overallScore = overallScoreInput.trim() !== '' ? parseFloat(overallScoreInput) : null;
     const overallFeedback = overallFeedbackInput.trim() !== '' ? overallFeedbackInput.trim() : null;
     if (overallScore !== null && (isNaN(overallScore) || overallScore < 0 || overallScore > 5)) { setManualSubmitError("Overall score must be between 0 and 5."); setIsSubmittingManualResult(false); return; }
     // Prepare per-response payload
     const responsesFeedbackPayload = Object.entries(responseFeedbacks).map(([questionId, feedbackData]) => {
            const score = feedbackData.score.trim() !== '' ? parseFloat(feedbackData.score) : null;
            const feedback = feedbackData.feedback.trim() !== '' ? feedbackData.feedback.trim() : null;
            if (score !== null && (isNaN(score) || score < 0 || score > 5)) { throw new Error(`Invalid score (${score}) for question ID ${questionId}. Must be 0-5.`); }
            if (score !== null || feedback !== null) { return { question_id: questionId, score: score, feedback: feedback }; } return null;
        }).filter(Boolean);
     const payload = { responses_feedback: responsesFeedbackPayload.length > 0 ? responsesFeedbackPayload : null, overall_score: overallScore, overall_feedback: overallFeedback, };
     if (!payload.responses_feedback && payload.overall_score === null && payload.overall_feedback === null) { setManualSubmitError("Please provide evaluation data."); setIsSubmittingManualResult(false); return; }
     try {
         await interviewAPI.submitInterviewResult(interviewId, payload);
         setManualSubmitSuccess("Manual evaluation submitted successfully!");
         fetchAllData(); // Refresh all data to show updated results
     } catch (err) { console.error("Failed to submit manual results:", err); const errorMsg = err instanceof Error ? err.message : (err.detail || err.message || "Unknown error"); setManualSubmitError(`Failed to submit results: ${errorMsg}`);
     } finally { setIsSubmittingManualResult(false); }
  };

  // Handler for triggering AI evaluation
  const handleEvaluateWithAI = async (responseId, questionId) => {
      if (aiEvalStatus[responseId]?.loading || isSubmittingManualResult) return;
      setAiEvalStatus(prev => ({ ...prev, [responseId]: { loading: true, error: null } }));
      setManualSubmitError(null); setManualSubmitSuccess(null);
      try {
          const response = await interviewAPI.evaluateResponseWithAI(responseId);
          const aiResult = response.data; // Expects updated InterviewResponseOut
          // Update main responses state
          setResponses(prevResponses => prevResponses.map(r =>
              r.response_id === responseId ? { ...r, score: aiResult.score, feedback: aiResult.feedback } : r
          ));
          // Update form state
          setResponseFeedbacks(prev => ({
              ...prev,
              [questionId]: { score: aiResult.score !== null ? aiResult.score.toString() : '', feedback: aiResult.feedback || '' }
          }));
          setAiEvalStatus(prev => ({ ...prev, [responseId]: { loading: false, error: null } })); // Clear status on success
      } catch (err) {
          console.error(`Failed to evaluate response ${responseId} with AI:`, err);
          const errorMsg = err.detail || err.message || "AI evaluation failed.";
          setAiEvalStatus(prev => ({ ...prev, [responseId]: { loading: false, error: errorMsg } }));
      }
  };

  // --- Render Logic ---
  const renderLoading = () => ( <div className="flex justify-center items-center min-h-[calc(100vh-theme_header_height)]"><div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div><p className="ml-3 text-gray-300">Loading results...</p></div> );
  const renderError = (errorMsg) => ( <div className="max-w-4xl mx-auto p-6 bg-red-900 border border-red-700 rounded-lg text-center"><h2 className="text-xl font-semibold mb-2 text-red-100">Error Loading Results</h2><p className="text-red-200">{errorMsg}</p><Link to="/dashboard" className="mt-4 inline-block bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-md">Go to Dashboard</Link></div> );

  const isHrOrAdmin = user?.role === 'hr' || user?.role === 'admin';
  const canEvaluate = isHrOrAdmin && interviewDetails?.status === 'completed';

  if (loading) return <Layout>{renderLoading()}</Layout>;
  if (fetchError && (!interviewDetails)) return <Layout>{renderError(fetchError)}</Layout>; // Show fatal fetch error
  if (!interviewDetails) return <Layout><p className="text-center text-gray-400">Interview data not available.</p></Layout>;

  return (
    <Layout>
      <div className="min-h-screen text-white p-4 md:p-6">
        {/* Wrap form only if evaluation is possible */}
        <form onSubmit={canEvaluate ? handleManualResultSubmit : (e) => e.preventDefault()}>
          <div className="max-w-4xl mx-auto bg-gray-800 p-6 rounded-xl shadow-lg">
            {/* Header */}
            <h2 className="text-2xl font-bold mb-4 border-b border-gray-700 pb-2">
              Interview Results: {interviewDetails.role || 'N/A'}
              <span className={`ml-3 text-xs font-semibold px-2 py-0.5 rounded-full ${ interviewDetails.status === 'completed' ? 'bg-green-200 text-green-900' : interviewDetails.status === 'scheduled' ? 'bg-yellow-200 text-yellow-900' : 'bg-gray-200 text-gray-900' }`}>{interviewDetails.status}</span>
            </h2>

            {/* Display non-fatal fetch errors */}
            {fetchError && <div className="mb-4 p-3 bg-yellow-900 border border-yellow-700 text-yellow-200 rounded text-sm">{fetchError}</div>}

            {/* Overall Summary Display */}
             <div className="mb-6 grid grid-cols-1 md:grid-cols-3 gap-4">
                 <div className="bg-gray-700 p-3 rounded"> <p className="text-sm text-gray-400">Candidate ID</p> <p className="font-semibold">{interviewDetails.candidate_id || 'N/A'}</p> </div>
                 <div className="bg-gray-700 p-3 rounded"> <p className="text-sm text-gray-400">Overall Score</p> <p className={`font-semibold ${resultData?.total_score !== null ? 'text-white' : 'text-gray-500 italic'}`}> {resultData?.total_score !== null ? `${resultData.total_score.toFixed(1)} / 5.0` : 'Pending Evaluation'} </p> </div>
                 <div className="bg-gray-700 p-3 rounded"> <p className="text-sm text-gray-400">Completed At</p> <p className={`font-semibold ${interviewDetails.completed_at ? 'text-white' : 'text-gray-500 italic'}`}> {interviewDetails.completed_at ? new Date(interviewDetails.completed_at).toLocaleString() : 'Not Completed'} </p> </div>
             </div>
             <div className="mb-6 bg-gray-700 p-4 rounded">
                 <h3 className="text-lg font-semibold mb-2 text-gray-300">Overall Feedback</h3>
                 <p className={`text-sm ${resultData?.overall_feedback ? 'text-gray-100 italic' : 'text-gray-500 italic'}`}> {resultData?.overall_feedback || 'Pending Evaluation'} </p>
             </div>

            {/* Questions, Answers & Evaluation Section */}
            <h3 className="text-xl font-semibold mb-4 text-gray-300">Questions, Answers & Evaluation</h3>
            <div className="space-y-6">
              {interviewDetails.questions?.map((question, index) => {
                  const response = responses.find(r => r.question_id === question.question_id);
                  const questionId = question.question_id;
                  const responseId = response?.response_id;
                  const currentFeedback = responseFeedbacks[questionId] || { score: '', feedback: '' };
                  const currentAiStatus = aiEvalStatus[responseId] || { loading: false, error: null };

                  return (
                    <div key={questionId || index} className="bg-gray-700 p-4 rounded-lg border border-gray-600">
                      {/* Question Display */}
                      <p className="font-semibold text-white mb-1"> Q{index + 1}: {question.text} </p>
                      <p className="text-xs text-gray-400 mb-2"> Category: {question.category || 'N/A'} | Difficulty: {question.difficulty || 'N/A'} </p>
                      {/* Answer Display */}
                      <div className="bg-gray-600 p-3 rounded mt-2 mb-3">
                         <p className="text-sm font-medium text-gray-300 mb-1">Candidate's Answer:</p>
                         {response ? ( <p className="text-sm text-gray-100 whitespace-pre-wrap">{response.answer}</p> ) : ( <p className="text-yellow-500 italic text-sm">(No answer submitted)</p> )}
                      </div>

                      {/* Evaluation Section */}
                      {response && ( // Only show evaluation if there is a response
                        <div className="mt-3 pt-3 border-t border-gray-500 space-y-3">
                          {/* AI Trigger Button + Status */}
                          <div className="flex justify-between items-center flex-wrap gap-2">
                              <h4 className="text-sm font-semibold text-blue-300 pt-1">Evaluate Answer #{index + 1}</h4>
                              {canEvaluate && responseId && (
                                  <button type="button" onClick={() => handleEvaluateWithAI(responseId, questionId)}
                                      className="bg-purple-600 hover:bg-purple-700 text-white px-3 py-1 rounded-md text-xs transition duration-150 disabled:opacity-50 disabled:cursor-wait flex items-center space-x-1" // Added flex items-center space-x-1
                                      disabled={currentAiStatus.loading || isSubmittingManualResult} title="Evaluate this answer using AI" >
                                       {currentAiStatus.loading && ( /* Simple inline spinner */
                                          <svg className="animate-spin h-3 w-3 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                                       )}
                                       <span>{currentAiStatus.loading ? 'Evaluating...' : 'Evaluate with AI'}</span>
                                  </button>
                              )}
                          </div>
                          {currentAiStatus.error && <p className="text-red-400 text-xs mt-1">{currentAiStatus.error}</p>}

                          {/* Manual Inputs (HR/Admin) OR Read-only display */}
                          {canEvaluate ? (
                             // Render inputs for HR/Admin
                              <div className="flex flex-col md:flex-row md:items-start gap-2 md:gap-4">
                                 {/* Score Input */}
                                 <div className="flex-shrink-0 w-full md:w-auto">
                                   <label htmlFor={`score-${questionId}`} className="block text-xs font-medium text-gray-300">Score (0-5)</label>
                                   <input type="number" id={`score-${questionId}`} value={currentFeedback.score} onChange={(e) => handleResponseScoreChange(questionId, e.target.value)}
                                     className="w-full md:w-24 mt-1 bg-gray-800 border border-gray-600 rounded px-2 py-1 text-white text-sm focus:ring-blue-500 focus:border-blue-500"
                                     min="0" max="5" step="0.1" disabled={isSubmittingManualResult} placeholder="?"/>
                                 </div>
                                 {/* Feedback Input */}
                                 <div className="flex-grow">
                                   <label htmlFor={`feedback-${questionId}`} className="block text-xs font-medium text-gray-300">Feedback</label>
                                   <textarea id={`feedback-${questionId}`} rows="2" value={currentFeedback.feedback} onChange={(e) => handleResponseFeedbackChange(questionId, e.target.value)}
                                     className="w-full mt-1 bg-gray-800 border border-gray-600 rounded px-2 py-1 text-white text-sm focus:ring-blue-500 focus:border-blue-500"
                                     maxLength="1000" placeholder="Feedback specific to this answer..." disabled={isSubmittingManualResult} />
                                 </div>
                              </div>
                          ) : ( // Read-only view for candidate or non-completed interviews
                              (response.score !== null || response.feedback) && (
                                  <div className="mt-2 pt-2 border-t border-gray-500">
                                     {response.score !== null && <p className="text-xs text-blue-300">Score: {response.score.toFixed(1)} / 5.0</p>}
                                     {response.feedback && <p className="text-xs text-gray-400 italic mt-1">Feedback: {response.feedback}</p>}
                                  </div>
                              )
                          )}
                        </div>
                      )}
                    </div>
                  );
                }) // End questions.map
             ( <p className="text-gray-400">No questions found for this interview.</p> )}
            </div>

            {/* Overall Manual Evaluation Form & Submit Button */}
            {canEvaluate && (
                <div className="mt-8 pt-6 border-t border-gray-600">
                    <h3 className="text-xl font-semibold mb-4 text-blue-300">Submit/Update Evaluation</h3>
                    <div className="space-y-4 p-4 bg-gray-700 rounded-lg">
                        {/* Overall Score Input */}
                        <div> <label htmlFor="overallScoreInput" className="block text-sm font-medium text-gray-300 mb-1"> Overall Score (0-5) <span className="text-gray-400 text-xs">(Optional - overrides calculation)</span> </label> <input type="number" id="overallScoreInput" value={overallScoreInput} onChange={(e) => setOverallScoreInput(e.target.value)} className="w-full md:w-1/3 mt-1 bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white focus:ring-blue-500 focus:border-blue-500" min="0" max="5" step="0.1" disabled={isSubmittingManualResult} placeholder="e.g. 4.2"/> </div>
                        {/* Overall Feedback Input */}
                        <div> <label htmlFor="overallFeedbackInput" className="block text-sm font-medium text-gray-300 mb-1"> Overall Feedback <span className="text-gray-400 text-xs">(Optional)</span> </label> <textarea id="overallFeedbackInput" rows="4" value={overallFeedbackInput} onChange={(e) => setOverallFeedbackInput(e.target.value)} className="w-full mt-1 bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white focus:ring-blue-500 focus:border-blue-500" maxLength="5000" disabled={isSubmittingManualResult} placeholder="Enter overall evaluation summary..."/> </div>
                        {/* Submission Status Messages */}
                        {manualSubmitError && <p className="text-red-400 text-sm">{manualSubmitError}</p>}
                        {manualSubmitSuccess && <p className="text-green-400 text-sm">{manualSubmitSuccess}</p>}
                        {/* Submit Button */}
                        <div> <button type="submit" className="bg-green-600 hover:bg-green-700 text-white px-5 py-2 rounded-md transition duration-150 disabled:opacity-50 flex items-center space-x-2" disabled={isSubmittingManualResult} >
                             {isSubmittingManualResult && ( /* Simple inline spinner */
                                <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                             )}
                             <span>{isSubmittingManualResult ? 'Submitting...' : 'Submit / Update Evaluation'}</span>
                        </button> <p className="text-xs text-gray-400 mt-2">Submits both overall and per-question evaluations entered above.</p> </div>
                    </div>
                </div>
            )}

            {/* Back Link */}
            <div className="mt-6 text-center"> <Link to="/dashboard" className="text-sm text-blue-400 hover:text-blue-300"> &larr; Back to Dashboard </Link> </div>
          </div>
        </form>
      </div>
    </Layout>
  );
};

export default ResultDetailPage;