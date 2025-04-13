import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { interviewAPI } from '../utils/apiClient';

const HRDashboard = () => {
  const navigate = useNavigate();
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [formData, setFormData] = useState({
    candidate_id: '',
    scheduled_time: '',
    role: '',
    tech_stack: '',
  });

  useEffect(() => {
    // In a real app, you'd fetch candidates from your backend
    setCandidates([
      { id: '1', name: 'John Doe', email: 'john@example.com' },
      { id: '2', name: 'Jane Smith', email: 'jane@example.com' },
    ]);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const response = await interviewAPI.schedule(formData);
      setSuccess('Interview scheduled successfully!');
      setFormData({
        candidate_id: '',
        scheduled_time: '',
        role: '',
        tech_stack: '',
      });
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to schedule interview');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  return (
    <div className="min-h-screen bg-[#1c1f2e] text-white font-sans">
      <div className="flex">
        {/* Sidebar */}
        <aside className="w-64 h-screen bg-[#212437] p-4 hidden md:block">
          <div className="mb-8 text-2xl font-bold">HR Dashboard</div>
          <ul className="space-y-4 text-sm text-gray-300">
            <li className="flex items-center space-x-2 text-white">
              <span>🏠</span>
              <Link to="/hr" className="hover:text-white">Dashboard</Link>
            </li>
            <li className="flex items-center space-x-2">
              <span>📧</span>
              <span>Invite Candidates</span>
            </li>
            <li className="flex items-center space-x-2">
              <span>📑</span>
              <Link to="/hr/results/1" className="hover:text-white">View Results</Link>
            </li>
            <li className="flex items-center space-x-2">
              <span>⚙️</span>
              <span>Settings</span>
            </li>
            <li className="flex items-center space-x-2">
              <span>🚪</span>
              <button onClick={() => navigate('/')} className="hover:text-white">Signout</button>
            </li>
          </ul>
        </aside>

        {/* Main Content */}
        <main className="flex-1 p-6 space-y-6">
          {/* Top Bar */}
          <div className="flex justify-between items-center bg-[#2a2e42] p-4 rounded-xl">
            <h1 className="text-xl font-bold">Welcome, HR!</h1>
            <div className="flex items-center space-x-4 ml-auto">
              <span>🔔</span>
              <span className="rounded-full w-8 h-8 bg-white text-black flex items-center justify-center">🧑‍💼</span>
            </div>
          </div>

          {/* Invite Section */}
          <div className="bg-[#2a2e42] p-4 rounded-xl">
            <h4 className="text-lg font-semibold mb-2">Invite Candidate</h4>
            <p className="text-sm text-gray-400 mb-4">Enter candidate's email to send an interview invite:</p>
            <div className="flex space-x-4">
              <input type="email" placeholder="candidate@example.com" className="bg-[#1c1f2e] text-white px-4 py-2 rounded w-full focus:outline-none" />
              <button className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded text-white text-sm">Send Invite</button>
            </div>
          </div>

          {/* Results Section */}
          <div className="bg-[#2a2e42] p-4 rounded-xl">
            <h4 className="text-lg font-semibold mb-2">Candidate Interview Results</h4>
            <p className="text-sm text-gray-400">Review scores and feedback from recent interviews.</p>
            <p className="text-sm text-gray-400 mt-2">(Results table placeholder)</p>
          </div>

          <div className="max-w-md mx-auto">
            <div className="divide-y divide-gray-200">
              <div className="py-8 text-base leading-6 space-y-4 text-gray-700 sm:text-lg sm:leading-7">
                <h2 className="text-2xl font-bold mb-6">Schedule Interview</h2>
                
                {error && (
                  <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                    <span className="block sm:inline">{error}</span>
                  </div>
                )}
                
                {success && (
                  <div className="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative" role="alert">
                    <span className="block sm:inline">{success}</span>
                  </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Candidate</label>
                    <select
                      name="candidate_id"
                      value={formData.candidate_id}
                      onChange={handleChange}
                      className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
                      required
                    >
                      <option value="">Select a candidate</option>
                      {candidates.map(candidate => (
                        <option key={candidate.id} value={candidate.id}>
                          {candidate.name} ({candidate.email})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Scheduled Time</label>
                    <input
                      type="datetime-local"
                      name="scheduled_time"
                      value={formData.scheduled_time}
                      onChange={handleChange}
                      className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Role</label>
                    <input
                      type="text"
                      name="role"
                      value={formData.role}
                      onChange={handleChange}
                      placeholder="e.g., Software Engineer"
                      className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Tech Stack</label>
                    <input
                      type="text"
                      name="tech_stack"
                      value={formData.tech_stack}
                      onChange={handleChange}
                      placeholder="e.g., Python, React, MongoDB"
                      className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
                      required
                    />
                  </div>

                  <div>
                    <button
                      type="submit"
                      disabled={loading}
                      className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                    >
                      {loading ? 'Scheduling...' : 'Schedule Interview'}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
};

export default HRDashboard;
