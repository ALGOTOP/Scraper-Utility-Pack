import { createRoot } from 'react-dom/client';
import { setBaseUrl } from '@workspace/api-client-react';

import App from './App';

import './index.css';

// In production, the browser must call the Railway API instead of trying to
// resolve /api/* against the Vercel frontend origin.
//
// When VITE_API_URL is not provided, the API client keeps its default
// same-origin behavior. This preserves the existing local-development setup,
// where Vite proxies /api requests to the local Express server.
const apiUrl = import.meta.env.VITE_API_URL?.trim();

if (apiUrl) {
  setBaseUrl(apiUrl);
}

createRoot(document.getElementById('root')!).render(<App />);
