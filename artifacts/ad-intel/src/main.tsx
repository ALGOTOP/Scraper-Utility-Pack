import { createRoot } from 'react-dom/client';
import { setBaseUrl } from '@workspace/api-client-react';

import App from './App';
import './index.css';

const apiUrl = import.meta.env.VITE_API_URL?.trim();

// Production is intentionally frontend-only on Vercel. API traffic must go
// directly to the Railway service configured through VITE_API_URL.
if (import.meta.env.PROD && !apiUrl) {
  throw new Error(
    'VITE_API_URL is required in the Vercel production environment. Configure it with the public Railway API URL.',
  );
}

if (apiUrl) {
  setBaseUrl(apiUrl);
}

createRoot(document.getElementById('root')!).render(<App />);
