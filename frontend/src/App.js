import logo from './logo.svg';
import './App.css';
import react, { useState } from 'react';
import D3Chart from './D3Chart';

function App() {
  const [chartType, setChartType] = useState('interactive-pie');
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

        <select 
          value={chartType} 
          onChange={(e) => setChartType(e.target.value)}
          className="chart-selector"
        >
          <option value="multiline">Multi-dimensional Line Chart</option>
          <option value="interactive-pie">Interactive Pie Chart</option>
          <option value="sunburst">Zoomable Sunburst</option>
          <option value="bar">Bar Chart (Fetch Data from the file) </option>
        </select>
        
        <div className="chart-container">
          <D3Chart type={chartType} />
        </div>
      </header>
    </div>
  );
}

export default App;
