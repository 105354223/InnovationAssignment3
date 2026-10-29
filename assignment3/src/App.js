import logo from './logo.svg';
import './App.css';
import react, { useState } from 'react';

function App() {
  const [count, setCount] = useState(0);
  return (
    <div className="App">
      <header className="App-header">
        <img src={logo} className="App-logo" alt="logo" />
        {/* Barebones website creation of a main landing page */}
        <h1>ALDI</h1>
        <h2>Anomalous Log Detection Investigator</h2>
        <p>Current count: {count}</p>
        <button onClick={() => setCount (count + 1)}>Increase Count</button>
        <button onClick={() => setCount (count - 1)}>Decrease Count</button>
      </header>
    </div>
  );
}

export default App;
