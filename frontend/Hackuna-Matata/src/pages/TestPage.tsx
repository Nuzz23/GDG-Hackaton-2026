import React from 'react';
import Test from '@/components/Test';

const TestPage: React.FC = () => {
  return (
    <div>
      <h1>Test Page</h1>
      <p>Se vedi questo messaggio, l'import funziona!</p>
        <Test />
    </div>
  );
};

export default TestPage;
