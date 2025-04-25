import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import Layout from '../components/Layout';
import { useNavigate } from 'react-router-dom';
// Import specific API objects for clarity
import { adminAPI, interviewAPI } from '../utils/apiClient';

const HRDashboard = () => {
  const { user } = useAuth(); // Assuming user object contains HR info if needed
  const navigate = useNavigate();

  // State for data display
  const [candidates, setCandidates] = useState([]);
  const [allInterviews, setAllInterviews] = useState([]); // Renamed for clarity
  const [completedInterviews, setCompletedInterviews] = useState([]); // Changed state name and purpose

  // Loading states
  const [loadingCandidates, setLoadingCandidates] = useState(true);
  const [loadingInterviews, setLoadingInterviews] = useState(true);
  const [loadingCompleted, setLoadingCompleted] = useState(true); // Changed state name

  // Error states
  const [errorCandidates, setErrorCandidates] = useState(null);
  const [errorInterviews, setErrorInterviews] = useState(null);
  const [errorCompleted, setErrorCompleted] = useState(null); // Changed state name

  // State for scheduling interview modal/form
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [scheduleData, setScheduleData] = useState({
    candidate_id: '', // This should be the candidate's User ID (string from MongoDB ObjectId)
    scheduled_time: '',
    role: '',
    tech_stack: [], // Keep as array
    // num_questions is part of form but not primary API input, backend uses default
  });
  const [schedulingError, setSchedulingError] = useState(null);
  const [isScheduling, setIsScheduling] = useState(false); // Loading state for schedule button

  // --- Data Fetching ---
  useEffect(() => {
    // Fetch data needed for the HR dashboard
    fetchCandidates();
    fetchAllInterviews();
    fetchCompletedInterviews(); // Fetch completed interviews instead of results

    // user dependency is okay if some filtering might happen based on HR user later
  }, [user]);

  const fetchCandidates = async () => {
    setLoadingCandidates(true);
    setErrorCandidates(null);
    try {
      // Use adminAPI to get all users, then filter for candidates
      const response = await adminAPI.getUsers();
      // Assuming response.data is an array of User objects based on UserResponse schema
      const candidateUsers = response.data.filter(u => u.role === 'candidate');
      setCandidates(candidateUsers);
    } catch (err) {
      console.error("Failed to fetch users (for candidates):", err);
      setErrorCandidates(`Failed to fetch candidates. ${err.message || err}`);
    } finally {
      setLoadingCandidates(false);
    }
  };

  const fetchAllInterviews = async () => {
    setLoadingInterviews(true);
    setErrorInterviews(null);
    try {
      // Use the specific API function for getting all interviews
      const response = await interviewAPI.getAllInterviews();
      setAllInterviews(response.data); // Assuming response.data is List[InterviewOut]
    } catch (err) {
      console.error("Failed to fetch all interviews:", err);
      setErrorInterviews(`Failed to fetch interviews. ${err.message || err}`);
    } finally {
      setLoadingInterviews(false);
    }
  };

  const fetchCompletedInterviews = async () => {
    setLoadingCompleted(true);
    setErrorCompleted(null);
    try {
      // Use the API function that gets completed interviews (which is /results/all on backend)
      // This endpoint returns List[InterviewOut] for completed interviews
      const response = await interviewAPI.getAllResults(); // Correct endpoint mapping
      setCompletedInterviews(response.data);
    } catch (err) {
      console.error("Failed to fetch completed interviews:", err);
      setErrorCompleted(`Failed to fetch completed interviews. ${err.message || err}`);
    } finally {
      setLoadingCompleted(false);
    }
  };

  // --- Scheduling Form Handlers ---
  const handleScheduleInputChange = (e) => {
    const { name, value } = e.target;
    setScheduleData({ ...scheduleData, [name]: value });
  };

   const handleTechStackChange = (e) => {
      const { value } = e.target;
      // Split comma-separated string into array, trim whitespace, filter empty strings
      const stackArray = value.split(',')
                            .map(item => item.trim())
                            .filter(item => item !== '');
      setScheduleData({ ...scheduleData, tech_stack: stackArray });
   };

  const handleScheduleSubmit = async (e) => {
    e.preventDefault();
    setSchedulingError(null);
    setIsScheduling(true);

    // Basic validation
    // **Important**: Ensure candidate_id here is the *string representation* of the MongoDB ObjectId
    if (!scheduleData.candidate_id || !scheduleData.scheduled_time || !scheduleData.role || scheduleData.tech_stack.length === 0) {
      setSchedulingError('Please fill in all required fields (Candidate ID, Time, Role, Tech Stack).');
      setIsScheduling(false);
      return;
    }

    // Prepare data matching InterviewCreate schema (role, tech_stack included)
    const dataToSubmit = {
        candidate_id: scheduleData.candidate_id,
        scheduled_time: scheduleData.scheduled_time,
        role: scheduleData.role,
        tech_stack: scheduleData.tech_stack,
    };

    try {
      await interviewAPI.schedule(dataToSubmit);
      setShowScheduleModal(false);
      setScheduleData({ // Reset form
        candidate_id: '', scheduled_time: '', role: '', tech_stack: []
      });
      fetchAllInterviews(); // Refresh interview list
      alert('Interview scheduled successfully!');
    } catch (err) {
      console.error("Failed to schedule interview:", err);
      // Display more specific backend error if available
      setSchedulingError(`Failed to schedule interview. ${err.detail || err.message || err}`);
    } finally {
      setIsScheduling(false);
    }
  };

  // Navigate to specific result/interview detail page
  // Since backend /results/all returns completed interviews, link to interview detail page
  const viewInterviewDetails = (interviewId) => {
    // We can navigate to a generic interview detail page if one exists,
    // or reuse the result detail page if it's adapted to show interview info.
    // Let's assume we navigate to a URL structure like /interview/detail/:id
    // If no such page exists, this navigation won't work.
    // navigate(`/interview/detail/${interviewId}`);
    // Or, for now, maybe just log it or disable the button
     console.log(`Navigate to details for interview ID: ${interviewId}`);
     alert(`Viewing details for interview ${interviewId} - Detail page needs implementation.`);
     // Alternatively, use the candidate's result view page if adaptable:
     // navigate(`/results/${interviewId}`); // If ResultDetailPage can handle InterviewOut data
  };


  // --- Render ---
  return (
    <Layout>
      <div className="space-y-6">
        {/* Schedule Interview Section */}
        <div className="bg-gray-800 p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Schedule New Interview</h2>
          <button
            onClick={() => setShowScheduleModal(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md disabled:opacity-50"
            disabled={loadingCandidates} // Disable if candidates haven't loaded
          >
            Schedule Interview
          </button>

          {/* Schedule Interview Modal */}
          {showScheduleModal && (
            <div className="fixed inset-0 bg-gray-900 bg-opacity-75 flex items-center justify-center z-50 transition-opacity duration-300">
              <div className="bg-gray-800 p-6 rounded-lg shadow-xl w-full max-w-lg transform transition-all duration-300 scale-100">
                <h3 className="text-lg font-semibold mb-4 text-white">Schedule Interview</h3>
                <form onSubmit={handleScheduleSubmit} className="space-y-4">
                  <div>
                    <label htmlFor="candidate_id" className="block text-sm font-medium text-gray-300">Candidate</label>
                    {/* Use a select dropdown populated from fetched candidates */}
                    <select
                      name="candidate_id"
                      id="candidate_id"
                      value={scheduleData.candidate_id}
                      onChange={handleScheduleInputChange}
                      className="mt-1 block w-full rounded-md bg-gray-700 border-gray-600 text-white py-2 px-3 focus:ring-blue-500 focus:border-blue-500"
                      required
                      disabled={loadingCandidates || candidates.length === 0}
                    >
                      <option value="" disabled>{loadingCandidates ? 'Loading...' : 'Select a Candidate'}</option>
                      {!loadingCandidates && candidates.map(c => (
                        <option key={c.id} value={c.id}>
                          {c.username} ({c.email})
                        </option>
                      ))}
                    </select>
                     {candidates.length === 0 && !loadingCandidates && <p className="text-xs text-yellow-500 mt-1">No candidates found. Register candidates first.</p>}
                  </div>
                  <div>
                    <label htmlFor="scheduled_time" className="block text-sm font-medium text-gray-300">Scheduled Time</label>
                    <input
                      type="datetime-local"
                      name="scheduled_time"
                      id="scheduled_time"
                      value={scheduleData.scheduled_time}
                      onChange={handleScheduleInputChange}
                      className="mt-1 block w-full rounded-md bg-gray-700 border-gray-600 text-white py-2 px-3 focus:ring-blue-500 focus:border-blue-500"
                      required
                    />
                  </div>
                   <div>
                    <label htmlFor="role" className="block text-sm font-medium text-gray-300">Job Role</label>
                    <input
                      type="text"
                      name="role"
                      id="role"
                      placeholder="e.g., Software Engineer, Data Scientist"
                      value={scheduleData.role}
                      onChange={handleScheduleInputChange}
                      className="mt-1 block w-full rounded-md bg-gray-700 border-gray-600 text-white py-2 px-3 focus:ring-blue-500 focus:border-blue-500"
                      required
                    />
                  </div>
                   <div>
                    <label htmlFor="tech_stack_input" className="block text-sm font-medium text-gray-300">Tech Stack (comma-separated)</label>
                    <input
                      type="text"
                      name="tech_stack_input" // Use different name to avoid direct state binding confusion
                      id="tech_stack_input"
                      placeholder="e.g., Python, React, Docker"
                      // Display current tech_stack array joined by comma
                      defaultValue={scheduleData.tech_stack.join(', ')}
                      // Use onBlur or a separate handler if needed, onChange handles parsing
                      onChange={handleTechStackChange}
                      className="mt-1 block w-full rounded-md bg-gray-700 border-gray-600 text-white py-2 px-3 focus:ring-blue-500 focus:border-blue-500"
                      required
                    />
                  </div>
                  {/* Removed num_questions from form - backend decides this */}
                  {schedulingError && <p className="text-red-500 text-sm mt-2">{schedulingError}</p>}
                  <div className="flex justify-end space-x-3 pt-4">
                    <button
                      type="button"
                      onClick={() => setShowScheduleModal(false)}
                      className="px-4 py-2 text-gray-300 rounded-md border border-gray-600 hover:bg-gray-700 transition duration-150"
                      disabled={isScheduling}
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md transition duration-150 disabled:opacity-50"
                      disabled={isScheduling || candidates.length === 0}
                    >
                      {isScheduling ? 'Scheduling...' : 'Schedule'}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>


        {/* Candidates Section (Unchanged - relies on adminAPI.getUsers) */}
        <div className="bg-gray-800 p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Registered Candidates</h2>
          {loadingCandidates ? <p>Loading candidates...</p> :
           errorCandidates ? <p className="text-red-500">{errorCandidates}</p> :
           candidates.length === 0 ? <p>No candidates registered.</p> : (
            <div className="space-y-3 max-h-60 overflow-y-auto">
              {candidates.map((candidate) => (
                <div key={candidate.id} className="bg-gray-700 p-3 rounded-lg">
                    <p className="font-medium text-white">{candidate.username}</p>
                    <p className="text-gray-400 text-sm">{candidate.email}</p>
                    <p className="text-gray-500 text-xs">ID: {candidate.id}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* All Scheduled/In-Progress Interviews Section */}
         <div className="bg-gray-800 p-6 rounded-lg shadow">
            <h2 className="text-xl font-semibold mb-4">Scheduled & In-Progress Interviews</h2>
             {loadingInterviews ? <p>Loading interviews...</p> :
              errorInterviews ? <p className="text-red-500">{errorInterviews}</p> :
              allInterviews.filter(i => i.status !== 'completed').length === 0 ? <p>No active interviews found.</p> : (
                <div className="space-y-3 max-h-80 overflow-y-auto">
                    {/* Filter interviews that are NOT completed */}
                    {allInterviews.filter(i => i.status !== 'completed').map((interview) => (
                        <div key={interview.interview_id} className="bg-gray-700 p-4 rounded-lg">
                             <h3 className="font-medium">{interview.role}</h3>
                             <p className="text-sm"><span className="text-gray-400">Candidate ID:</span> {interview.candidate_id}</p>
                             <p className="text-sm"><span className="text-gray-400">Status:</span> <span className={`font-semibold ${interview.status === 'scheduled' ? 'text-yellow-400' : 'text-blue-400'}`}>{interview.status}</span></p>
                             <p className="text-sm"><span className="text-gray-400">Tech Stack:</span> {interview.tech_stack.join(', ')}</p>
                              {interview.scheduled_time && (
                                    <p className="text-gray-400 text-sm">
                                        Scheduled: {new Date(interview.scheduled_time).toLocaleString()}
                                    </p>
                                )}
                             {/* Maybe add link to view questions? */}
                        </div>
                    ))}
                </div>
             )}
         </div>


        {/* Completed Interviews Section (formerly Results) */}
        <div className="bg-gray-800 p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Completed Interviews</h2>
          {loadingCompleted ? <p>Loading completed interviews...</p> :
           errorCompleted ? <p className="text-red-500">{errorCompleted}</p> :
           completedInterviews.length === 0 ? <p>No completed interviews found.</p> : (
            <div className="space-y-3 max-h-80 overflow-y-auto">
              {/* Display completed interviews based on the fetched List[InterviewOut] */}
              {completedInterviews.map((interview) => (
                <div key={interview.interview_id} className="bg-gray-700 p-4 rounded-lg flex justify-between items-center">
                  <div>
                    <h3 className="font-medium">{interview.role}</h3>
                    <p className="text-sm"><span className="text-gray-400">Candidate ID:</span> {interview.candidate_id}</p>
                     {/* Display completion time */}
                      {interview.completed_at && (
                         <p className="text-gray-400 text-sm">
                            Completed: {new Date(interview.completed_at).toLocaleString()}
                        </p>
                    )}
                    {/* Could add placeholder text about results being available */}
                    <p className="text-xs text-green-400">Completed</p>
                  </div>
                  {/* Update button to view details, actual results need calculation/another page */}
                  <button
                    // Link to the specific result page (or interview detail page)
                    onClick={() => viewInterviewDetails(interview.interview_id)}
                    className="bg-green-600 hover:bg-green-700 text-white px-3 py-1 rounded-md text-xs"
                  >
                    View Details/Result
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>
    </Layout>
  );
};

export default HRDashboard;