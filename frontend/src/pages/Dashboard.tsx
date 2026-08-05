import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Grid, Card, CardContent, Typography, Box, LinearProgress,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Paper, Chip, IconButton, Button,
} from '@mui/material';
import { TrendingUp, Security, Warning, CheckCircle, ArrowForward } from '@mui/icons-material';

const statsCards = [
  { title: 'Investigaciones Activas', value: 12, icon: <Security />, color: '#1976d2' },
  { title: 'Alertas Criticas', value: 3, icon: <Warning />, color: '#dc004e' },
  { title: 'Evidencias Procesadas', value: 847, icon: <CheckCircle />, color: '#2e7d32' },
  { title: 'Fuentes OSINT', value: 24, icon: <TrendingUp />, color: '#ed6c02' },
];

const recentCases = [
  { id: 'INV-2026-001', title: 'Caso Secuestro - Lima Norte', status: 'CRITICAL', priority: 'ALTA', updated: '2026-08-03 14:30' },
  { id: 'INV-2026-002', title: 'Trata de Personas - Callao', status: 'ACTIVE', priority: 'ALTA', updated: '2026-08-03 12:15' },
  { id: 'INV-2026-003', title: 'Extorsion Telefonica', status: 'ACTIVE', priority: 'MEDIA', updated: '2026-08-02 09:45' },
  { id: 'INV-2026-004', title: 'Fraude Bancario', status: 'PENDING', priority: 'MEDIA', updated: '2026-08-01 16:20' },
];

const getStatusColor = (status: string) => {
  switch (status) {
    case 'CRITICAL': return 'error';
    case 'ACTIVE': return 'success';
    case 'PENDING': return 'warning';
    default: return 'default';
  }
};

const Dashboard: React.FC = () => {
  const navigate = useNavigate();

  return (
    <Box>
      <Typography variant="h4" gutterBottom fontWeight={700}>Panel de Control</Typography>
      <Typography variant="body2" color="text.secondary" gutterBottom>
        Sistema de Inteligencia OSINT - Ultima actualizacion: {new Date().toLocaleString('es-PE')}
      </Typography>

      <Grid container spacing={3} sx={{ mt: 1 }}>
        {statsCards.map((card) => (
          <Grid item xs={12} sm={6} md={3} key={card.title}>
            <Card sx={{ bgcolor: 'background.paper', borderLeft: `4px solid ${card.color}` }}>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Box>
                    <Typography color="text.secondary" variant="body2" gutterBottom>{card.title}</Typography>
                    <Typography variant="h4" fontWeight={700}>{card.value}</Typography>
                  </Box>
                  <Box sx={{ color: card.color }}>{card.icon}</Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Card sx={{ mt: 3, bgcolor: 'background.paper' }}>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6" fontWeight={600}>Investigaciones Recientes</Typography>
            <Button variant="contained" size="small" onClick={() => navigate('/investigation/new')}>
              Nueva Investigacion
            </Button>
          </Box>
          <TableContainer component={Paper} variant="outlined" sx={{ bgcolor: 'transparent' }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>ID Caso</TableCell>
                  <TableCell>Titulo</TableCell>
                  <TableCell>Estado</TableCell>
                  <TableCell>Prioridad</TableCell>
                  <TableCell>Actualizado</TableCell>
                  <TableCell align="right">Accion</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {recentCases.map((row) => (
                  <TableRow key={row.id} hover>
                    <TableCell sx={{ fontFamily: 'monospace', fontWeight: 600 }}>{row.id}</TableCell>
                    <TableCell>{row.title}</TableCell>
                    <TableCell><Chip label={row.status} color={getStatusColor(row.status) as any} size="small" /></TableCell>
                    <TableCell>{row.priority}</TableCell>
                    <TableCell sx={{ color: 'text.secondary' }}>{row.updated}</TableCell>
                    <TableCell align="right">
                      <IconButton size="small" onClick={() => navigate(`/investigation/${row.id}`)}>
                        <ArrowForward fontSize="small" />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>

      <Grid container spacing={3} sx={{ mt: 1 }}>
        <Grid item xs={12} md={6}>
          <Card sx={{ bgcolor: 'background.paper' }}>
            <CardContent>
              <Typography variant="h6" gutterBottom fontWeight={600}>Rendimiento del Sistema</Typography>
              <Box sx={{ mt: 2 }}>
                {['CPU', 'Memoria', 'Disco'].map((label, i) => (
                  <Box key={label} sx={{ mb: 1 }}>
                    <Typography variant="body2" color="text.secondary">{label}</Typography>
                    <LinearProgress variant="determinate" value={[45, 62, 28][i]} />
                  </Box>
                ))}
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={6}>
          <Card sx={{ bgcolor: 'background.paper' }}>
            <CardContent>
              <Typography variant="h6" gutterBottom fontWeight={600}>Fuentes OSINT Activas</Typography>
              <Box sx={{ mt: 2 }}>
                {['SUNAT', 'RENIEC', 'SUNEDU', 'SUNARP', 'HIBP', 'IntelX', 'Shodan', 'Censys'].map((source) => (
                  <Chip key={source} label={source} size="small" color="success" variant="outlined" sx={{ m: 0.5 }} />
                ))}
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Dashboard;
