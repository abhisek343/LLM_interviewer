import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

console.log('1. Main.jsx: Starting application initialization');
console.log('2. Main.jsx: React and ReactDOM imported successfully');

const rootElement = document.getElementById('root');
console.log('3. Main.jsx: Root element found:', rootElement);

if (!rootElement) {
  console.error('4. Main.jsx: Root element not found! Check if index.html has div#root');
} else {
  console.log('5. Main.jsx: Creating React root');
  const root = ReactDOM.createRoot(rootElement);
  console.log('6. Main.jsx: Rendering App component');
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
  console.log('7. Main.jsx: Render complete');
}
