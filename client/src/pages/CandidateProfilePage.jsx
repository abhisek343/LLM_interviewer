import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../components/Layout'; // Assuming Layout component exists
import { candidateAPI } from '../utils/apiClient'; // Import the API functions
import { useAuth } from '../contexts/AuthContext'; // To potentially get user ID if needed

const CandidateProfilePage = () => {
  const { user } = useAuth(); // Get authenticated user context if needed

  // State for profile data fetched from backend
  const [profileData, setProfileData] = useState(null);
  // State for form inputs (controlled components)
  const [formData, setFormData] = useState({
    username: '',
    // Add other fields if they become editable, e.g., tech_stack: []
  });
  // UI states
  const [loading, setLoading] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  // Fetch profile data on component mount
  const fetchProfile = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSuccessMessage(null); // Clear previous success message
    try {
      const response = await candidateAPI.getProfile();
      if (response.data) {
        setProfileData(response.data);
        // Initialize form data with fetched profile data
        setFormData({
          username: response.data.username || '',
          // tech_stack: response.data.tech_stack || [], // Uncomment if tech_stack is added
        });
      } else {
        throw new Error("No profile data received.");
      }
    } catch (err) {
      console.error("Failed to fetch profile:", err);
      setError(`Failed to load profile. ${err.detail || err.message || err}`);
    } finally {
      setLoading(false);
    }
  }, []); // Empty dependency array means run once on mount

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]); // Include fetchProfile in dependency array

  // Handle changes in form inputs
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prevData => ({
      ...prevData,
      [name]: value
    }));
     // Clear success/error messages when user starts typing again
     setSuccessMessage(null);
     setError(null);
  };

  // Handle form submission for profile update
  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsUpdating(true);
    setError(null);
    setSuccessMessage(null);

    // Prepare only the data that can be updated
    const updatePayload = {
      username: formData.username,
      // tech_stack: formData.tech_stack, // Include if editable
    };

    // Optional: Send only changed fields (more complex)
    // const changedPayload = {};
    // if (formData.username !== profileData?.username) {
    //   changedPayload.username = formData.username;
    // }
    // if (JSON.stringify(formData.tech_stack) !== JSON.stringify(profileData?.tech_stack || [])) {
    //   changedPayload.tech_stack = formData.tech_stack;
    // }
    // if (Object.keys(changedPayload).length === 0) {
    //   setSuccessMessage("No changes detected.");
    //   setIsUpdating(false);
    //   return;
    // }

    try {
      const response = await candidateAPI.updateProfile(updatePayload);
      // Update local profile data state with the response from the API
      setProfileData(response.data);
      // Update formData as well to reflect saved state
      setFormData({
         username: response.data.username || '',
         // tech_stack: response.data.tech_stack || [],
      });
      setSuccessMessage('Profile updated successfully!');
      // Optionally refresh user context if username is used elsewhere from AuthContext
      // fetchUser(); // Assuming fetchUser exists in AuthContext
    } catch (err) {
      console.error("Failed to update profile:", err);
      setError(`Failed to update profile. ${err.detail || err.message || err}`);
       // Optionally revert formData back to profileData on error
       // setFormData({ username: profileData?.username || '' });
    } finally {
      setIsUpdating(false);
    }
  };

  // --- Render Logic ---
  if (loading) {
     return (
       <Layout>
         <div className="flex justify-center items-center min-h-[calc(100vh-theme_header_height)]">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500"></div>
            <p className="ml-3 text-gray-300">Loading profile...</p>
         </div>
       </Layout>
     );
   }

  return (
    <Layout> {/* Wrap content in Layout */}
      <div className="min-h-screen text-white p-6">
        <div className="max-w-lg mx-auto bg-gray-800 p-6 rounded-xl shadow-lg">
          <h2 className="text-2xl font-bold mb-6 border-b border-gray-700 pb-3">My Profile</h2>

           {/* Display Fetch Error */}
           {error && !isUpdating && (
             <div className="mb-4 p-3 bg-red-900 border border-red-700 text-red-200 rounded">
                {error}
             </div>
           )}

           {/* Display Update Success/Error */}
           {successMessage && (
             <div className="mb-4 p-3 bg-green-900 border border-green-700 text-green-200 rounded">
                {successMessage}
             </div>
           )}
           {error && isUpdating && ( // Show update-specific error separately?
              <div className="mb-4 p-3 bg-red-900 border border-red-700 text-red-200 rounded">
                 {error}
              </div>
           )}


          {profileData ? (
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Username */}
              <div>
                <label htmlFor="username" className="block text-sm font-medium text-gray-300 mb-1">Username</label>
                <input
                  type="text"
                  name="username"
                  id="username"
                  value={formData.username}
                  onChange={handleChange}
                  className="w-full mt-1 bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white focus:ring-blue-500 focus:border-blue-500"
                  disabled={isUpdating}
                  required
                  minLength="3"
                  maxLength="50"
                />
              </div>

              {/* Email (Read-Only) */}
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-400 mb-1">Email (Read-only)</label>
                <input
                    type="email"
                    id="email"
                    value={profileData.email || ''} // Use profileData here
                    className="w-full mt-1 bg-gray-600 border border-gray-500 rounded px-3 py-2 text-gray-300 cursor-not-allowed"
                    readOnly
                 />
              </div>

              {/* Role (Read-Only) */}
               <div>
                 <label htmlFor="role" className="block text-sm font-medium text-gray-400 mb-1">Role (Read-only)</label>
                 <input
                     type="text"
                     id="role"
                     value={profileData.role || ''}
                     className="w-full mt-1 bg-gray-600 border border-gray-500 rounded px-3 py-2 text-gray-300 cursor-not-allowed capitalize"
                     readOnly
                  />
               </div>

               {/* Resume Path (Read-Only) */}
                {profileData.resume_path && (
                   <div>
                      <label htmlFor="resume_path" className="block text-sm font-medium text-gray-400 mb-1">Uploaded Resume</label>
                      <input
                         type="text"
                         id="resume_path"
                         value={profileData.resume_path.split(/[\\/]/).pop() || profileData.resume_path} // Show only filename
                         className="w-full mt-1 bg-gray-600 border border-gray-500 rounded px-3 py-2 text-gray-300 cursor-not-allowed"
                         readOnly
                         title={profileData.resume_path} // Show full path on hover
                      />
                   </div>
                )}


              {/* Tech Stack (Example if added later) */}
              {/* <div>
                <label htmlFor="tech_stack" className="block text-sm font-medium text-gray-300 mb-1">Tech Stack (comma-separated)</label>
                <input
                  type="text"
                  name="tech_stack"
                  id="tech_stack"
                  placeholder="e.g., React, Node.js, MongoDB"
                  value={formData.tech_stack.join(', ')}
                  onChange={(e) => setFormData({...formData, tech_stack: e.target.value.split(',').map(s => s.trim()).filter(Boolean)})}
                  className="w-full mt-1 bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white focus:ring-blue-500 focus:border-blue-500"
                  disabled={isUpdating}
                />
              </div> */}

              <button
                type="submit"
                className="w-full bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md transition duration-150 disabled:opacity-50"
                disabled={isUpdating || formData.username === profileData.username /* Disable if no changes */}
              >
                {isUpdating ? 'Updating...' : 'Update Profile'}
              </button>
            </form>
          ) : (
             // Render message if profileData is null after loading and no error occurred
             !error && <p>Could not load profile information.</p>
          )}
        </div>
      </div>
    </Layout>
  );
};

export default CandidateProfilePage;