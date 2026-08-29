import express from 'express';

const app = express();
const PORT = process.env.PORT || 8000;

app.use(express.json());

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', message: 'Backend is running' });
});

app.get('/api/entities', (req, res) => {
  res.json({ entities: [] });
});

app.get('/api/network', (req, res) => {
  res.json({ nodes: [], edges: [] });
});

app.listen(PORT, () => {
  console.log(`Backend API running on port ${PORT}`);
});