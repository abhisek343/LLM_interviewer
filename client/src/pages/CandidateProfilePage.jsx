export default function CandidateProfilePage() {
  return (
    <div className="min-h-screen bg-[#1c1f2e] text-white p-6">
      <div className="max-w-lg mx-auto bg-[#2a2e42] p-6 rounded-xl">
        <h2 className="text-2xl font-bold mb-4">My Profile</h2>
        <form className="space-y-4">
          <div>
            <label className="text-sm">Full Name</label>
            <input type="text" defaultValue="John Doe" className="w-full mt-1 bg-[#1c1f2e] border border-gray-600 rounded px-4 py-2 text-white" />
          </div>
          <div>
            <label className="text-sm">Email</label>
            <input type="email" defaultValue="john@example.com" className="w-full mt-1 bg-[#1c1f2e] border border-gray-600 rounded px-4 py-2 text-white" />
          </div>
          <div>
            <label className="text-sm">Tech Stack</label>
            <input type="text" placeholder="React, Node.js, MongoDB" className="w-full mt-1 bg-[#1c1f2e] border border-gray-600 rounded px-4 py-2 text-white" />
          </div>
          <button type="submit" className="bg-blue-600 px-4 py-2 rounded text-white mt-4 w-full">Update Profile</button>
        </form>
      </div>
    </div>
  );
}
