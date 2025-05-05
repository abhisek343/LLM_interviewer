import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
// Import tailwindcss and autoprefixer using import statements
import tailwindcss from 'tailwindcss';
import autoprefixer from 'autoprefixer';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  css: {
    postcss: {
      plugins: [
        // Reference the imported modules here
        tailwindcss,
        autoprefixer,
      ],
    },
  },
  // --- Vitest configuration added ---
  test: {
    globals: true, // Use global APIs like describe, it, expect
    environment: 'jsdom', // Simulate browser environment
    setupFiles: './src/SetupTest.js', // Match the actual file name 'SetupTest.js'
    // Optionally add coverage configuration
    // coverage: {
    //   provider: 'v8', // or 'istanbul'
    //   reporter: ['text', 'json', 'html'],
    // },
  },
  // --- End Vitest configuration ---
  server: {
    port: 3000, // Or the port you prefer
    open: true, // Open browser automatically
     // Proxy API requests to your backend
     proxy: {
       // Adjust '/api' if your client makes requests like /api/auth/login
       // If your client requests are like /auth/login directly, adjust baseURL in apiClient.js instead
       '/api': { // Example: If client requests start with /api
           target: 'http://localhost:8000', // Your backend server address
           changeOrigin: true,
           rewrite: (path) => path.replace(/^\/api/, ''), // Removes /api prefix before forwarding
       }
       // If your client directly calls http://localhost:8000/auth/login etc (using VITE_API_BASE_URL),
       // you might not need this proxy section in dev, assuming CORS is handled by the backend.
     }
  }
});