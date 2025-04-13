export default function ResultDetailPage() {
  return (
    <div className="min-h-screen bg-[#1c1f2e] text-white p-6">
      <div className="max-w-4xl mx-auto bg-[#2a2e42] p-6 rounded-xl">
        <h2 className="text-2xl font-bold mb-4">Candidate Interview Results</h2>
        <p className="text-sm text-gray-400 mb-2">Candidate: John Doe</p>
        <p className="text-sm text-gray-400 mb-2">Email: john@example.com</p>
        <p className="text-sm text-gray-400 mb-4">Score: 85%</p>
        <div className="space-y-2">
          <div className="bg-[#1c1f2e] p-4 rounded">
            <p className="font-semibold text-white">Q1: What is a closure in JavaScript?</p>
            <p className="text-sm text-gray-300 mt-2">A closure is a function that has access to its own scope, the outer function’s scope, and the global scope.</p>
          </div>
          <div className="bg-[#1c1f2e] p-4 rounded">
            <p className="font-semibold text-white">Q2: Explain REST vs GraphQL.</p>
            <p className="text-sm text-gray-300 mt-2">REST uses multiple endpoints and GraphQL uses a single endpoint with queries.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
