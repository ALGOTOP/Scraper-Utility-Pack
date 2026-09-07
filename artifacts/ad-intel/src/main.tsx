import { createRoot } from 'react-dom/client';
import { setBaseUrl } from '@workspace/api-client-react';

import App from './App';
import './index.css';

const apiUrl = import.meta.env.VITE_API_URL?.trim();

// Vercel is frontend-only. When configured, API traffic goes directly to the
// Railway API. Do not throw during startup if the variable is missing: a
// configuration problem should never turn the entire SPA into a blank screen.
if (apiUrl) {
  setBaseUrl(apiUrl);
}

createRoot(document.getElementById('root')!).render(<App />);
