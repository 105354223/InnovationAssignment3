import React, { useState } from 'react';
import * as d3 from 'd3';
import axios from 'axios';
import {
  Container, Typography, Button, Paper, Box, CircularProgress,
  Table, TableHead, TableRow, TableCell, TableBody, Chip,
  Collapse, Alert
} from '@mui/material';
import { ThemeProvider, createTheme } from '@mui/material/styles';

const theme = createTheme({
  palette: { primary: { main: '#1976d2' }, secondary: { main: '#dc004e' } },
});

function SummaryChart({ summary }) {
  const ref = React.useRef(null);

  React.useEffect(() => {
    if (!ref.current || !summary) return;
    const svg = d3.select(ref.current);
    svg.selectAll('*').remove();

    const data = [
      { label: 'Normal',  value: summary.normal,  color: '#2ca02c' },
      { label: 'Anomaly', value: summary.anomaly, color: '#d62728' },
    ];

    const width = 400, height = 260;
    const margin = { top: 20, right: 20, bottom: 40, left: 60 };

    svg.attr('width', width).attr('height', height);

    const x = d3.scaleBand()
      .domain(data.map(d => d.label))
      .range([margin.left, width - margin.right])
      .padding(0.3);

    const y = d3.scaleLinear()
      .domain([0, d3.max(data, d => d.value)])
      .nice()
      .range([height - margin.bottom, margin.top]);

    svg.selectAll('rect').data(data).join('rect')
      .attr('x', d => x(d.label))
      .attr('y', d => y(d.value))
      .attr('width', x.bandwidth())
      .attr('height', d => y(0) - y(d.value))
      .attr('fill', d => d.color);

    svg.selectAll('text.value').data(data).join('text')
      .attr('x', d => x(d.label) + x.bandwidth() / 2)
      .attr('y', d => y(d.value) - 6)
      .attr('text-anchor', 'middle')
      .attr('font-size', 12)
      .text(d => d.value.toLocaleString());

    svg.selectAll('text.label').data(data).join('text')
      .attr('x', d => x(d.label) + x.bandwidth() / 2)
      .attr('y', height - margin.bottom + 20)
      .attr('text-anchor', 'middle')
      .attr('font-size', 14)
      .text(d => d.label);

    svg.append('g')
      .attr('transform', `translate(${margin.left},0)`)
      .call(d3.axisLeft(y).ticks(5));
  }, [summary]);

  return <svg ref={ref} />;
}

function SessionsTable({ sessions }) {
  const [expandedId, setExpandedId] = useState(null);
  const [detail, setDetail] = useState({});
  
  // calls GET/session/{block_id} on backend
  // if user expands too many rows, error 429 shows
  // the catch shows "failed to load detail" and swollows 429 error
  const toggleRow = async (blockId) => {
    if (expandedId === blockId) { setExpandedId(null); return; }
    setExpandedId(blockId);
    if (!detail[blockId]) {
      try {
        const res = await axios.get(`http://localhost:8000/session/${encodeURIComponent(blockId)}`);
        setDetail(prev => ({ ...prev, [blockId]: res.data.messages }));
      } catch {
        setDetail(prev => ({ ...prev, [blockId]: ['Failed to load detail'] }));
      }
    }
  };

  return (
    <Table size="small">
      <TableHead>
        <TableRow>
          <TableCell>Block ID</TableCell>
          <TableCell align="right">Events</TableCell>
          <TableCell align="right">Anomaly Score</TableCell>
          <TableCell align="center">Label</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {sessions.map(s => (
          <React.Fragment key={s.block_id}>
            <TableRow hover sx={{ cursor: 'pointer' }} onClick={() => toggleRow(s.block_id)}>
              <TableCell sx={{ fontFamily: 'monospace', fontSize: 12 }}>{s.block_id}</TableCell>
              <TableCell align="right">{s.event_count}</TableCell>
              <TableCell align="right">{s.anomaly_score.toFixed(4)}</TableCell>
              <TableCell align="center">
                <Chip size="small" label={s.label}
                      color={s.label === 'Anomaly' ? 'error' : 'success'} />
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell colSpan={4} sx={{ py: 0 }}>
                <Collapse in={expandedId === s.block_id} timeout="auto" unmountOnExit>
                  <Box sx={{ p: 2, bgcolor: '#f5f5f5' }}>
                    {(detail[s.block_id] || []).map((line, i) => (
                      <Typography key={i} variant="body2"
                        sx={{ fontFamily: 'monospace', fontSize: 12 }}>
                        {line}
                      </Typography>
                    ))}
                  </Box>
                </Collapse>
              </TableCell>
            </TableRow>
          </React.Fragment>
        ))}
      </TableBody>
    </Table>
  );
}

export default function App() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showOnlyAnomalies, setShowOnlyAnomalies] = useState(false);

  const MAX_MB = 25;

  // POST contains file field matching fastapi parameter
  // backend rate limit is 5/minute, error analysing files after 6 or more attempts within a minute
  // Cleint max_mb check is UX only
  // error message extraction for errors
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setResult(null);

    if (!file) { setError('Please choose a file first.'); return; }
    if (file.size > MAX_MB * 1024 * 1024) {
      setError(`File too large (${(file.size / 1_048_576).toFixed(1)} MB). Max ${MAX_MB} MB.`);
      return;
    }

    setLoading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await axios.post('http://localhost:8000/analyze', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 300_000,
      });
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Error analysing the file.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <ThemeProvider theme={theme}>
      <Container maxWidth="md">
        <Box sx={{ my: 4 }}>
          <Typography variant="h3" component="h1" gutterBottom>
            HDFS Log Anomaly Detector
          </Typography>

          <Paper elevation={3} sx={{ p: 3, mb: 3 }}>
            <form onSubmit={handleSubmit}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Button variant="contained" component="label">
                  Choose File
                  <input type="file" hidden accept=".log,.txt"
                    onChange={(e) => setFile(e.target.files[0] || null)} />
                </Button>
                <Typography variant="body2" color="text.secondary">
                  {file ? `${file.name} (${(file.size / 1_048_576).toFixed(1)} MB)` : 'No file chosen'}
                </Typography>
              </Box>
              <Box sx={{ mt: 2 }}>
                <Button type="submit" variant="contained" disabled={loading || !file} fullWidth>
                  {loading ? <CircularProgress size={24} /> : 'Analyze'}
                </Button>
              </Box>
            </form>
          </Paper>

          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          {loading && (
            <Alert severity="info" sx={{ mb: 2 }}>
              Analyzing — this can take 1–2 minutes for large files.
            </Alert>
          )}

          {result && (
            <>
              <Paper elevation={3} sx={{ p: 3, mb: 3 }}>
                <Typography variant="h5" gutterBottom>
                  Summary — {result.summary.total_sessions.toLocaleString()} sessions
                </Typography>
                <SummaryChart summary={result.summary} />
              </Paper>

              <Paper elevation={3} sx={{ p: 3 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between',
                           alignItems: 'center', mb: 2 }}>
                  <Typography variant="h5">
                    Sessions (top {result.sessions.length}
                    {result.session_total ? ` of ${result.session_total.toLocaleString()}` : ''})
                  </Typography>
                  <Button
                    variant={showOnlyAnomalies ? 'contained' : 'outlined'}
                    onClick={() => setShowOnlyAnomalies(v => !v)}
                  >
                    {showOnlyAnomalies ? 'Show All' : 'Anomalies Only'}
                  </Button>
                </Box>
                <SessionsTable
                  sessions={showOnlyAnomalies
                    ? result.sessions.filter(s => s.label === 'Anomaly')
                    : result.sessions}
                />
              </Paper>
            </>
          )}
        </Box>
      </Container>
    </ThemeProvider>
  );
}