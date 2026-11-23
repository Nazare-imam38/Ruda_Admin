
import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import LandInformation from './pages/LandInformation/LandInformation';
import './styles.css';

const isLandPage = window.location.pathname === '/land-information';

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {isLandPage ? <LandInformation /> : <App />}
  </React.StrictMode>
);
