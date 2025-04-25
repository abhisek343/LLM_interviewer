import React, { useState, useEffect, useCallback } from 'react'; // Added useCallback
import { useAuth } from '../contexts/AuthContext'; // Import useAuth to get current admin ID
import Layout from '../components/Layout';
// Import the specific adminAPI object
import { adminAPI } from '../utils/apiClient'; // Corrected import

const AdminDashboard = () => {
  const { user } = useAuth(); // Get current authenticated user (admin)

  // Separate states for better loading/error handling per section
  const [users, setUsers] = useState([]);
  const [systemStats, setSystemStats] = useState(null);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [loadingStats, setLoadingStats] = useState(true);
  const [errorUsers, setErrorUsers] = useState(null);
  const [errorStats, setErrorStats] = useState(null);

  // State for delete operation
  const [deletingUserId, setDeletingUserId] = useState(null); // Track which user is being deleted
  const [deleteError, setDeleteError] = useState(null); // Specific error for delete actions


  // Fetch users function (separated for refresh)
  const fetchAdminUsers = useCallback(async () => {
    setLoadingUsers(true);
    setErrorUsers(null); // Clear previous user errors
    setDeleteError(null); // Clear previous delete errors
    try {
      const response = await adminAPI.getUsers(); // Use specific API function
      setUsers(response.data);
    } catch (err) {
      console.error("Failed to fetch users:", err);
      setErrorUsers(`Failed to fetch users. ${err.detail || err.message || err}`);
    } finally {
      setLoadingUsers(false);
    }
  }, []); // No dependencies needed if it doesn't rely on component state/props that change

  // Fetch stats function (separated)
  const fetchSystemStats = useCallback(async () => {
     setLoadingStats(true);
     setErrorStats(null);
     try {
        const response = await adminAPI.getSystemStats(); // Use specific API function
        setSystemStats(response.data);
     } catch (err) {
         console.error("Failed to fetch system stats:", err);
         setErrorStats(`Failed to fetch system stats. ${err.detail || err.message || err}`);
     } finally {
        setLoadingStats(false);
     }
  }, []); // No dependencies needed

  // Fetch initial data on mount
  useEffect(() => {
    fetchAdminUsers();
    fetchSystemStats();
  }, [fetchAdminUsers, fetchSystemStats]); // Include fetched functions in dependency array

  // --- NEW: Handle User Deletion ---
  const handleDeleteUser = async (userIdToDelete, usernameToDelete) => {
      // Prevent multiple delete clicks
      if (deletingUserId) return;

       // Confirmation dialog
       if (!window.confirm(`Are you sure you want to delete the user "${usernameToDelete}" (ID: ${userIdToDelete})? This action cannot be undone.`)) {
           return; // Abort if user cancels
       }

      setDeletingUserId(userIdToDelete); // Set loading state for this user
      setDeleteError(null); // Clear previous delete errors

      try {
          await adminAPI.deleteUser(userIdToDelete); // Call the API function
          alert(`User "${usernameToDelete}" deleted successfully.`);
          fetchAdminUsers(); // Refresh the user list after successful deletion
      } catch (err) {
          console.error(`Failed to delete user ${userIdToDelete}:`, err);
          // Display specific error from backend if available
          const errorDetail = err.detail || err.message || "An unknown error occurred";
          setDeleteError(`Failed to delete user "${usernameToDelete}": ${errorDetail}`);
           // Log the detailed error object for debugging
          console.error('Delete User Error Object:', err);
      } finally {
          setDeletingUserId(null); // Reset loading state regardless of outcome
      }
  };
  // --- End NEW ---


  return (
    <Layout>
      <div className="space-y-6">
        {/* System Stats */}
        <div className="bg-gray-800 p-6 rounded-lg shadow">
          {/* ... (Stats display code remains the same as previous version) ... */}
           <h2 className="text-xl font-semibold mb-4">System Statistics</h2>
            {loadingStats ? <p>Loading statistics...</p> : errorStats ? <p className="text-red-500">{errorStats}</p> : systemStats ? (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                     <div className="bg-gray-700 p-4 rounded-lg text-center"><h3 className="text-sm font-medium text-gray-400 uppercase">Total Users</h3><p className="text-3xl font-bold text-white mt-1">{systemStats.total_users ?? 'N/A'}</p></div>
                     <div className="bg-gray-700 p-4 rounded-lg text-center"><h3 className="text-sm font-medium text-gray-400 uppercase">Scheduled Interviews</h3><p className="text-3xl font-bold text-white mt-1">{systemStats.total_interviews_scheduled ?? 'N/A'}</p></div>
                     <div className="bg-gray-700 p-4 rounded-lg text-center"><h3 className="text-sm font-medium text-gray-400 uppercase">Completed Interviews</h3><p className="text-3xl font-bold text-white mt-1">{systemStats.total_interviews_completed ?? 'N/A'}</p></div>
                     {/* LLM Status Placeholder */}
                     <div className="bg-gray-700 p-4 rounded-lg text-center"><h3 className="text-sm font-medium text-gray-400 uppercase">LLM Service</h3><p className={`text-xl font-semibold mt-2 ${ systemStats.llm_service_status?.toLowerCase().includes('operational') ? 'text-green-400' : 'text-yellow-400' }`}>{systemStats.llm_service_status ?? 'Unknown'}</p></div>
                 </div>
            ) : ( <p>No statistics available.</p> )}
        </div>

        {/* User Management */}
        <div className="bg-gray-800 p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">User Management</h2>
           {/* Display user fetch error */}
           {errorUsers && <p className="text-red-500 mb-4">{errorUsers}</p>}
           {/* Display user delete error */}
           {deleteError && <p className="text-red-500 mb-4">{deleteError}</p>}

          {loadingUsers ? ( <p>Loading users...</p> ) : users.length === 0 && !errorUsers ? ( <p>No users found.</p> ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-700">
                <thead className="bg-gray-700">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider"> Username </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider"> Email </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider"> Role </th>
                    {/* Added Actions column */}
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider"> Actions </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-600">
                  {users.map((u) => (
                    <tr key={u.id || u.email} className="hover:bg-gray-700">
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-white">{u.username}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">{u.email}</td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {/* Role Badge */}
                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${ u.role === 'admin' ? 'bg-red-200 text-red-800' : u.role === 'hr' ? 'bg-blue-200 text-blue-800' : 'bg-green-200 text-green-800' }`}> {u.role} </span>
                      </td>
                      {/* Actions Column */}
                      <td className="px-6 py-4 whitespace-nowrap text-sm space-x-2">
                         {/* Role change select (commented out as backend not ready) */}
                         {/* <select ... /> */}

                         {/* Delete Button */}
                         <button
                             onClick={() => handleDeleteUser(u.id, u.username)}
                             className={`text-red-500 hover:text-red-700 disabled:opacity-50 disabled:cursor-not-allowed ${
                                 // Add specific styling while deleting this user
                                 deletingUserId === u.id ? 'animate-pulse' : ''
                             }`}
                             // Disable delete button for the currently logged-in admin
                             disabled={user?.id === u.id || !!deletingUserId} // Disable if deleting anyone OR if it's self
                             title={user?.id === u.id ? "Cannot delete self" : `Delete user ${u.username}`}
                          >
                             {deletingUserId === u.id ? 'Deleting...' : 'Delete'}
                         </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
};

export default AdminDashboard;