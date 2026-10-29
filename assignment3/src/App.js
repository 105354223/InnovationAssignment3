import logo from './logo.svg';
import './App.css';
import react, { useState } from 'react';

function App() {
  const [uploaded, setUploaded] = useState("false");
  return (
    <div className="App">
      <header className="App-header">
        {/*<img src={logo} className="App-logo" alt="logo" />/}
        {/* Barebones website creation of a main landing page */}
        <h1>ALDI</h1>
        <h2>Anomalous Log Detection Investigator</h2>
        <p>Files uploaded?: {uploaded}</p>
        <button onClick={() => setUploaded ("true")}>Upload files</button>
      </header>
    </div>
  );
}

export default App;
