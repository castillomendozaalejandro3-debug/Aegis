import React, { useState, useEffect } from 'react';
import {
  Box, Card, CardContent, TextField, Button, Typography,
  Alert, CircularProgress, Avatar, Container,
} from '@mui/material';
import { Lock, Shield } from '@mui/icons-material';
import { login } from '../utils/api';

interface LoginProps {
  onLogin: () => void;
}

const Login: React.FC<LoginProps> = ({ onLogin }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempts, setAttempts] = useState(0);

  // Bloquear despues de 5 intentos fallidos
  const isLocked = attempts >= 5;

  useEffect(() => {
    // Limpiar cualquier token previo al cargar login
    localStorage.removeItem('aegis_token');
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (isLocked) {
      setError('Demasiados intentos fallidos. Espere 5 minutos.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await login(username, password);
      setAttempts(0);
      onLogin();
    } catch (err: any) {
      setAttempts(prev => prev + 1);
      setError(err.message || 'Error de conexion con el servidor');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="sm" sx={{ display: 'flex', alignItems: 'center', minHeight: '100vh' }}>
      <Card sx={{ width: '100%', bgcolor: 'background.paper', boxShadow: 24 }}>
        <CardContent sx={{ p: 4 }}>
          <Box sx={{ textAlign: 'center', mb: 3 }}>
            <Avatar sx={{ bgcolor: 'primary.main', width: 64, height: 64, mx: 'auto', mb: 2 }}>
              <Shield sx={{ fontSize: 36 }} />
            </Avatar>
            <Typography variant="h4" fontWeight={700}>AEGIS</Typography>
            <Typography variant="subtitle1" color="text.secondary">
              Sistema de Inteligencia OSINT
            </Typography>
            <Typography variant="caption" color="text.secondary" display="block">
              Acceso restringido - Personal autorizado
            </Typography>
          </Box>

          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          {isLocked && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              Cuenta temporalmente bloqueada por seguridad.
            </Alert>
          )}

          <Box component="form" onSubmit={handleSubmit}>
            <TextField
              fullWidth
              label="Usuario"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              margin="normal"
              required
              autoFocus
              autoComplete="username"
              disabled={isLocked}
            />
            <TextField
              fullWidth
              label="Contrasena"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              margin="normal"
              required
              autoComplete="current-password"
              disabled={isLocked}
            />
            <Button
              type="submit"
              variant="contained"
              fullWidth
              size="large"
              disabled={loading || isLocked}
              startIcon={loading ? <CircularProgress size={20} /> : <Lock />}
              sx={{ mt: 2 }}
            >
              {loading ? 'Autenticando...' : 'Iniciar Sesion'}
            </Button>
          </Box>

          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ mt: 2, display: 'block', textAlign: 'center' }}
          >
            Este sistema esta protegido por monitoreo de seguridad.
            Cualquier acceso no autorizado sera registrado y reportado.
          </Typography>
        </CardContent>
      </Card>
    </Container>
  );
};

export default Login;
