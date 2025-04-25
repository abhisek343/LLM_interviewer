import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Layout from '../components/Layout'; // Assuming Layout component exists
import { candidateAPI } from '../utils/apiClient'; // Import the API functions

const CandidateQuestionHistory = () => {
  // State for history data, loading, and errors
  const [historyData, setHistoryData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch history data on component mount
  useEffect(() => {
    const fetchHistory = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await candidateAPI.getInterviewHistory(); // Call the correct API function
        // Backend returns List[InterviewHistoryItem]
        setHistoryData(response.data || []); // Ensure it's an array even if null/undefined
      } catch (err) {
        console.error("Failed to fetch interview history:", err);
        setError(`Failed to load interview history. ${err.detail || err.message || err}`);
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
  }, []); // Empty dependency array runs once on mount

  // --- Render Logic ---
  const renderContent = () => {
    if (loading) {
      return (
        <div className="flex justify-center items-center py-10">
          {/* Simple spinner */}
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400"></div>
          <p className="ml-3 text-gray-300">Loading history...</p>
        </div>
      );
    }

    if (error) {
      return (
        <div className="p-4 bg-red-900 border border-red-700 text-red-200 rounded text-center">
          {error}
          <div className="mt-4">
             <Link to="/dashboard" className="text-sm bg-red-600 hover:bg-red-700 text-white px-3 py-1 rounded-md">
                 Go to Dashboard
             </Link>
          </div>
        </div>
      );
    }

    if (historyData.length === 0) {
      return <p className="text-gray-400 text-center py-5">No completed interview history found.</p>;
    }

    // Display history
    return (
      <ul className="space-y-5">
        {historyData.map((item) => (
          <li key={item.interview_id} className="bg-gray-700 p-4 rounded-lg shadow border border-gray-600">
            {/* Interview Header */}
            <div className="border-b border-gray-600 pb-2 mb-3 flex justify-between items-center">
                 <div>
                    <p className="font-semibold text-lg text-blue-300">
                        Interview for: {item.role || 'N/A'}
                    </p>
                    {item.completed_at && (
                      <p className="text-xs text-gray-400">
                        Completed: {new Date(item.completed_at).toLocaleString()}
                      </p>
                    )}
                    {item.tech_stack?.length > 0 && (
                      <p className="text-xs text-gray-400">
                        Tech Stack: {item.tech_stack.join(', ')}
                      </p>
                    )}
                 </div>
                 {/* Optional: Link to the full results page for this interview */}
                 <Link
                      to={`/results/${item.interview_id}`}
                      className="text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded transition duration-150"
                      title="View Full Results"
                    >
                      View Results
                 </Link>
            </div>

            {/* Questions and Answers List */}
            <h4 className="text-sm font-semibold text-gray-300 mb-2">Questions & Answers:</h4>
            {item.questions_answers && item.questions_answers.length > 0 ? (
              <ul className="space-y-3 pl-2">
                {item.questions_answers.map((qa, index) => (
                  <li key={index} className="border-l-2 border-gray-600 pl-3 py-1">
                    {/* Question */}
                    <p className="font-medium text-sm text-gray-100">{qa.question_text || 'Question text unavailable'}</p>
                    {/* Answer */}
                    <p className="text-xs text-gray-300 mt-1 whitespace-pre-wrap bg-gray-800 p-2 rounded shadow-inner">
                      <span className="font-semibold text-gray-400">Your Answer:</span> {qa.answer_text !== null && qa.answer_text !== '' ? qa.answer_text : <span className="italic text-gray-500">(No answer recorded)</span>}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-gray-500 italic pl-2">No questions or answers recorded for this interview.</p>
            )}
          </li>
        ))}
      </ul>
    );
  };


  return (
    <Layout> {/* Wrap content in Layout */}
      <div className="min-h-screen text-white p-4 md:p-6">
        <div className="max-w-3xl mx-auto bg-gray-800 p-6 rounded-xl shadow-lg">
          <h2 className="text-2xl font-bold mb-5 border-b border-gray-700 pb-3">
            Past Interview History
          </h2>
          {renderContent()}
           <div className="mt-6 text-center">
              <Link to="/dashboard" className="text-sm text-blue-400 hover:text-blue-300">
                  &larr; Back to Dashboard
              </Link>
           </div>
        </div>
      </div>
    </Layout>
  );
};

export default CandidateQuestionHistory;