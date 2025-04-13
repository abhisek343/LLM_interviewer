export default function CandidateQuestionHistory() {
  return (
    <div className="min-h-screen bg-[#1c1f2e] text-white p-6">
      <div className="max-w-3xl mx-auto bg-[#2a2e42] p-6 rounded-xl">
        <h2 className="text-2xl font-bold mb-4">Past Interview Questions</h2>
        <ul className="space-y-4">
          <li className="bg-[#1c1f2e] p-4 rounded">
            <p className="font-semibold">Session on April 10, 2025</p>
            <ul className="list-disc list-inside text-sm text-gray-300 mt-2">
              <li>Explain closures in JavaScript.</li>
              <li>What is virtual DOM in React?</li>
              <li>Describe useEffect and its dependencies.</li>
              <li>What are HTTP status codes?</li>
              <li>How does Node.js handle async?</li>
            </ul>
          </li>
          <li className="bg-[#1c1f2e] p-4 rounded">
            <p className="font-semibold">Session on March 25, 2025</p>
            <p className="text-sm text-gray-300 mt-2">No questions recorded.</p>
          </li>
        </ul>
      </div>
    </div>
  );
}
