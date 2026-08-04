import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Drawer, List, ListItem, ListItemButton, ListItemIcon, ListItemText,
  Toolbar, Typography, Divider, Box, Avatar, Chip,
} from '@mui/material';
import {
  Dashboard, Search, CloudUpload, Settings, Logout, Shield,
} from '@mui/icons-material';

const DRAWER_WIDTH = 240;

const Layout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    { text: 'Panel Principal', icon: <Dashboard />, path: '/' },
    { text: 'Nueva Investigacion', icon: <Search />, path: '/investigation/new' },
    { text: 'Subir Evidencia', icon: <CloudUpload />, path: '/upload' },
    { text: 'Configuracion', icon: <Settings />, path: '/settings' },
  ];

  const handleLogout = () => {
    localStorage.removeItem('aegis_token');
    window.location.href = '/login';
  };

  return (
    <Drawer variant="permanent" sx={{
      width: DRAWER_WIDTH, flexShrink: 0,
      '& .MuiDrawer-paper': { width: DRAWER_WIDTH, boxSizing: 'border-box', bgcolor: 'background.paper', borderRight: '1px solid rgba(255,255,255,0.12)' },
    }}>
      <Toolbar sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2 }}>
        <Shield color="primary" />
        <Typography variant="h6" noWrap component="div" sx={{ fontWeight: 700 }}>AEGIS</Typography>
        <Chip label="PERU" size="small" color="primary" variant="outlined" sx={{ ml: 'auto' }} />
      </Toolbar>
      <Divider />
      <Box sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <Avatar sx={{ bgcolor: 'primary.main', width: 32, height: 32 }}>OP</Avatar>
        <Box>
          <Typography variant="body2" fontWeight={600}>Operador</Typography>
          <Typography variant="caption" color="text.secondary">Analista OSINT</Typography>
        </Box>
      </Box>
      <Divider />
      <List>
        {menuItems.map((item) => (
          <ListItem key={item.text} disablePadding>
            <ListItemButton selected={location.pathname === item.path} onClick={() => navigate(item.path)}
              sx={{ '&.Mui-selected': { bgcolor: 'primary.dark', '&:hover': { bgcolor: 'primary.dark' } } }}>
              <ListItemIcon sx={{ color: location.pathname === item.path ? 'primary.main' : 'inherit' }}>{item.icon}</ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
      <Box sx={{ mt: 'auto' }}>
        <Divider />
        <ListItem disablePadding>
          <ListItemButton onClick={handleLogout}>
            <ListItemIcon><Logout /></ListItemIcon>
            <ListItemText primary="Cerrar Sesion" />
          </ListItemButton>
        </ListItem>
      </Box>
    </Drawer>
  );
};

export default Layout;
