export default function AdminDashboard() {
  return (
    <div className="min-h-screen bg-[#1c1f2e] text-white font-sans">
      {/* Sidebar */}
      <div className="flex">
        <aside className="w-64 h-screen bg-[#212437] p-4 hidden md:block">
          <div className="mb-8 text-2xl font-bold">Admin Panel</div>
          <ul className="space-y-4 text-sm text-gray-300">
            <li className="flex items-center space-x-2 text-white"><span>🏠</span><span>Dashboard</span></li>
            <li className="flex items-center space-x-2"><span>👨‍🎓</span><span>Manage Candidates</span></li>
            <li className="flex items-center space-x-2"><span>🧑‍💼</span><span>Manage HR</span></li>
            <li className="flex items-center space-x-2"><span>⚙️</span><span>System Status</span></li>
            <li className="flex items-center space-x-2"><span>🚪</span><span>Signout</span></li>
          </ul>
        </aside>

        {/* Main Content */}
        <main className="flex-1 p-6 space-y-6">
          {/* Top Bar */}
          <div className="flex justify-between items-center bg-[#2a2e42] p-4 rounded-xl">
            <input type="text" placeholder="Search users or settings..." className="bg-[#1c1f2e] text-sm text-white px-4 py-2 rounded w-full max-w-md focus:outline-none" />
            <div className="flex items-center space-x-4 ml-auto">
              <span>🔔</span>
              <span className="rounded-full w-8 h-8 bg-white text-black flex items-center justify-center">👤</span>
            </div>
          </div>

          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-[#2a2e42] p-4 rounded-xl">
              <p className="text-sm text-gray-400">Total Candidates</p>
              <h3 className="text-xl font-bold">320</h3>
              <p className="text-green-400 text-xs">+15 this month</p>
            </div>
            <div className="bg-[#2a2e42] p-4 rounded-xl">
              <p className="text-sm text-gray-400">HR Members</p>
              <h3 className="text-xl font-bold">12</h3>
              <p className="text-blue-400 text-xs">+1 new HR</p>
            </div>
            <div className="bg-[#2a2e42] p-4 rounded-xl">
              <p className="text-sm text-gray-400">Interviews Conducted</p>
              <h3 className="text-xl font-bold">58</h3>
              <p className="text-yellow-400 text-xs">Up 12%</p>
            </div>
            <div className="bg-[#2a2e42] p-4 rounded-xl">
              <p className="text-sm text-gray-400">System Health</p>
              <h3 className="text-xl font-bold">✅ Normal</h3>
              <p className="text-gray-400 text-xs">Last checked: 10 min ago</p>
            </div>
          </div>

          {/* Management Panels */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="bg-[#2a2e42] p-4 rounded-xl min-h-[200px]">
              <h4 className="text-lg font-semibold mb-2">Candidate Management</h4>
              <p className="text-sm text-gray-400">Add, remove, or update candidates.</p>
              <p className="text-sm text-gray-400 mt-2">(CRUD table or component placeholder)</p>
            </div>

            <div className="bg-[#2a2e42] p-4 rounded-xl min-h-[200px]">
              <h4 className="text-lg font-semibold mb-2">HR Management</h4>
              <p className="text-sm text-gray-400">Manage HR access and privileges.</p>
              <p className="text-sm text-gray-400 mt-2">(CRUD table or component placeholder)</p>
            </div>
          </div>

          <div className="bg-[#2a2e42] p-4 rounded-xl min-h-[200px]">
            <h4 className="text-lg font-semibold mb-2">System Overview</h4>
            <p className="text-sm text-gray-400">Monitor system usage, performance, and LLM service health.</p>
            <p className="text-sm text-gray-400 mt-2">(System logs or uptime metrics placeholder)</p>
          </div>
        </main>
      </div>
    </div>
  );
}
