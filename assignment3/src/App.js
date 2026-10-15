import logo from './logo.svg';
import './App.css';
import react, { useState } from 'react';

function App() {
  const [count, setCount] = useState(0);
  return (
    <div className="App">
      <header className="App-header">
        <img src={logo} className="App-logo" alt="logo" />
        <p>
          Edit <code>src/App.js</code> and save to reload.
        </p>
        <a
          className="App-link"
          href="https://reactjs.org"
          target="_blank"
          rel="noopener noreferrer"
        >
          Learn React
        </a>
        <h1>React Counter</h1>
        <p>CUrrent count: {count}</p>
        <button onClick={() => setCount (count + 1)}>Increase Count</button>
        <button onClick={() => setCount (count - 1)}>Decrease Count</button>
      </header>
    </div>
  );
}

export default App;
