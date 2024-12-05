import React from 'react';
import ReactDOM from 'react-dom/client';
import TextProcessorApp from './components/TextProcessorApp';  // Changed from { TextProcessorApp }

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <TextProcessorApp />
  </React.StrictMode>
);