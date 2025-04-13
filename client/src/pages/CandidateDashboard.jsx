import React, { useState, useEffect } from 'react';
import { interviewAPI, candidateAPI } from '../utils/apiClient';

const CandidateDashboard = () => {
  const [interviews, setInterviews] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [selectedInterview, setSelectedInterview] = useState(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answer, setAnswer] = useState('');

  useEffect(() => {
    fetchInterviews();
  }, []);

  const fetchInterviews = async () => {
    setLoading(true);
    try {
      const response = await interviewAPI.getCandidateInterviews();
      setInterviews(response.data);
    } catch (err) {
      setError('Failed to fetch interviews');
    } finally {
      setLoading(false);
    }
  };

  const handleResumeUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('resume', file);

    setLoading(true);
    try {
      await candidateAPI.uploadResume(formData);
      setSuccess('Resume uploaded successfully');
    } catch (err) {
      setError('Failed to upload resume');
    } finally {
      setLoading(false);
    }
  };

  const handleStartInterview = (interview) => {
    setSelectedInterview(interview);
    setCurrentQuestionIndex(0);
    setAnswer('');
  };

  const handleSubmitAnswer = async () => {
    if (!selectedInterview || !answer.trim()) return;

    setLoading(true);
    try {
      await interviewAPI.submitResponse({
        interview_id: selectedInterview.id,
        question_id: selectedInterview.questions[currentQuestionIndex].id,
        answer: answer.trim(),
      });

      if (currentQuestionIndex < selectedInterview.questions.length - 1) {
        setCurrentQuestionIndex(prev => prev + 1);
        setAnswer('');
        setSuccess('Answer submitted successfully');
      } else {
        setSelectedInterview(null);
        setSuccess('Interview completed!');
        fetchInterviews(); // Refresh the list
      }
    } catch (err) {
      setError('Failed to submit answer');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 py-6 flex flex-col justify-center sm:py-12">
      <div className="relative py-3 sm:max-w-xl sm:mx-auto">
        <div className="relative px-4 py-10 bg-white shadow-lg sm:rounded-3xl sm:p-20">
          <div className="max-w-md mx-auto">
            {error && (
              <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-4" role="alert">
                <span className="block sm:inline">{error}</span>
              </div>
            )}
            
            {success && (
              <div className="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative mb-4" role="alert">
                <span className="block sm:inline">{success}</span>
              </div>
            )}

            {selectedInterview ? (
              <div className="space-y-4">
                <h2 className="text-2xl font-bold mb-4">Interview Questions</h2>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <p className="text-lg font-medium mb-2">
                    Question {currentQuestionIndex + 1} of {selectedInterview.questions.length}
                  </p>
                  <p className="mb-4">{selectedInterview.questions[currentQuestionIndex].text}</p>
                  <textarea
                    value={answer}
                    onChange={(e) => setAnswer(e.target.value)}
                    placeholder="Type your answer here..."
                    className="w-full h-32 p-2 border rounded-md"
                  />
                </div>
                <div className="flex justify-between">
                  <button
                    onClick={() => setSelectedInterview(null)}
                    className="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSubmitAnswer}
                    disabled={loading || !answer.trim()}
                    className="px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
                  >
                    {loading ? 'Submitting...' : 'Submit Answer'}
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="mb-6">
                  <h2 className="text-2xl font-bold mb-4">Upload Resume</h2>
                  <input
                    type="file"
                    accept=".pdf,.doc,.docx"
                    onChange={handleResumeUpload}
                    className="block w-full text-sm text-gray-500
                      file:mr-4 file:py-2 file:px-4
                      file:rounded-full file:border-0
                      file:text-sm file:font-semibold
                      file:bg-indigo-50 file:text-indigo-700
                      hover:file:bg-indigo-100"
                  />
                </div>

                <div>
                  <h2 className="text-2xl font-bold mb-4">Your Interviews</h2>
                  {loading ? (
                    <p>Loading interviews...</p>
                  ) : interviews.length === 0 ? (
                    <p>No interviews scheduled yet.</p>
                  ) : (
                    <div className="space-y-4">
                      {interviews.map((interview) => (
                        <div key={interview.id} className="border p-4 rounded-lg">
                          <h3 className="font-semibold">Role: {interview.role}</h3>
                          <p>Tech Stack: {interview.tech_stack}</p>
                          <p>Scheduled: {new Date(interview.scheduled_time).toLocaleString()}</p>
                          <button
                            onClick={() => handleStartInterview(interview)}
                            className="mt-2 px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700"
                          >
                            Start Interview
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default CandidateDashboard;
