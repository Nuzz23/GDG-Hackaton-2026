import React from 'react';

const Test: React.FC = () => {
  const printHelloWorld = () => {
    console.log('Hello world');
  };

  return (
    <div>
      <button onClick={printHelloWorld}>Stampa Hello World</button>
    </div>
  );
};

export default Test;
