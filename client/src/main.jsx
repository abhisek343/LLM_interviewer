import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'
import { AuthProvider } from './contexts/AuthContext.jsx';
// Import BrowserRouter
import { BrowserRouter } from 'react-router-dom';

console.log("1. Main.jsx: Starting application initialization");
console.log("2. Main.jsx: React, ReactDOM, and BrowserRouter imported successfully");

const rootElement = document.getElementById('root');
console.log("3. Main.jsx: Root element found:", rootElement);

// Ensure root element exists
if (rootElement) {
  console.log("4. Main.jsx: Creating React root");
  const root = ReactDOM.createRoot(rootElement);

  console.log("5. Main.jsx: Preparing to render application within BrowserRouter and AuthProvider");

  root.render(
    <React.StrictMode>
      {/* Wrap the application with BrowserRouter */}
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </React.StrictMode>,
  );
   console.log("6. Main.jsx: Initial render process started"); // Adjusted log message
} else {
  console.error("Failed to find the root element with ID 'root'");
}