import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Box, Typography, Card, CardContent, Grid, TextField, Button,
  Stepper, Step, StepLabel, Chip, Alert, CircularProgress, Divider,
  Accordion, AccordionSummary, AccordionDetails, List, ListItem, ListItemText,
} from '@mui/material';
import {
  Search, Person, ContactPhone, LocationOn, ExpandMore,
  CheckCircle, Error as ErrorIcon, Security,
} from '@mui/icons-material';

const steps = ['Datos de Entrada', 'Recoleccion OSINT', 'Analisis NER/VLM', 'Persistencia', 'Reporte'];

const Investigation: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [activeStep, setActiveStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);

  const [formData, setFormData] = useState({
    investigationId: id === 'new' ? `INV-${new Date().getFullYear()}-${String(Math.floor(Math.random() * 900) + 100)}` : id || '',
    textQuery: '',
    dniHint: '',
    rucHint: '',
    aliasHint: '',
    phoneHint: '',
    emailHint: '',
  });

  const handleChange = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [field]: e.target.value });
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    setActiveStep(1);

    try {
      const token = localStorage.getItem('aegis_token');
      const form = new FormData();
      form.append('investigation_id', formData.investigationId);
      if (formData.textQuery) form.append('text_query', formData.textQuery);
      if (formData.dniHint) form.append('dni_hint', formData.dniHint);
      if (formData.rucHint) form.append('ruc_hint', formData.rucHint);
      if (formData.aliasHint) form.append('alias_hint', formData.aliasHint);
      if (formData.phoneHint) form.append('phone_hint', formData.phoneHint);
      if (formData.emailHint) form.append('email_hint', formData.emailHint);

      const response = await fetch('/api/v1/ingest', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: form,
      });

      const data = await response.json();
      if (data.success) {
        setResult(data.data);
        setActiveStep(4);
      } else {
        setError(data.message || 'Error en el analisis');
        setActiveStep(0);
      }
    } catch (err: any) {
      setError(err.message || 'Error de conexion');
      setActiveStep(0);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom fontWeight={700}>
        {id === 'new' ? 'Nueva Investigacion' : `Investigacion ${id}`}
      </Typography>

      <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
        {steps.map((label) => <Step key={label}><StepLabel>{label}</StepLabel></Step>)}
      </Stepper>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} icon={<ErrorIcon />}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card sx={{ bgcolor: 'background.paper' }}>
            <CardContent>
              <Typography variant="h6" gutterBottom fontWeight={600}>
                <Security sx={{ mr: 1, verticalAlign: 'middle' }} />
                Datos de Entrada
              </Typography>
              <Divider sx={{ my: 2 }} />

              <TextField
                fullWidth label="ID Investigacion" value={formData.investigationId}
                onChange={handleChange('investigationId')} margin="normal" disabled={id !== 'new'}
                helperText="Formato: INV-AAAA-NNN"
              />
              <TextField
                fullWidth label="Consulta de Texto" value={formData.textQuery}
                onChange={handleChange('textQuery')} margin="normal"
                placeholder="Nombre, alias o descripcion del sujeto"
              />
              <TextField
                fullWidth label="DNI (8 digitos)" value={formData.dniHint}
                onChange={handleChange('dniHint')} margin="normal"
                inputProps={{ maxLength: 8, pattern: '\\d{8}' }}
              />
              <TextField
                fullWidth label="RUC (11 digitos)" value={formData.rucHint}
                onChange={handleChange('rucHint')} margin="normal"
                inputProps={{ maxLength: 11, pattern: '\\d{11}' }}
              />
              <TextField
                fullWidth label="Alias / Seudonimo" value={formData.aliasHint}
                onChange={handleChange('aliasHint')} margin="normal"
              />
              <TextField
                fullWidth label="Telefono" value={formData.phoneHint}
                onChange={handleChange('phoneHint')} margin="normal"
                placeholder="+519XXXXXXXX"
              />
              <TextField
                fullWidth label="Email" value={formData.emailHint}
                onChange={handleChange('emailHint')} margin="normal"
                type="email"
              />

              <Button
                variant="contained" fullWidth size="large"
                onClick={handleSubmit} disabled={loading}
                startIcon={loading ? <CircularProgress size={20} /> : <Search />}
                sx={{ mt: 2 }}
              >
                {loading ? 'Analizando...' : 'Iniciar Analisis OSINT'}
              </Button>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          {result && (
            <Card sx={{ bgcolor: 'background.paper' }}>
              <CardContent>
                <Typography variant="h6" gutterBottom fontWeight={600}>
                  <CheckCircle color="success" sx={{ mr: 1, verticalAlign: 'middle' }} />
                  Resultados del Analisis
                </Typography>
                <Divider sx={{ my: 2 }} />

                <Box sx={{ mb: 2 }}>
                  <Chip label={`Confianza: ${(result.analysis?.confidence_aggregate * 100 || 0).toFixed(1)}%`}
                    color={result.analysis?.confidence_aggregate > 0.7 ? 'success' : 'warning'} />
                  <Chip label={`Tiempo: ${result.processing_time || 0}s`} sx={{ ml: 1 }} />
                </Box>

                {result.analysis?.persons?.length > 0 && (
                  <Accordion defaultExpanded>
                    <AccordionSummary expandIcon={<ExpandMore />}>
                      <Person sx={{ mr: 1 }} /> Personas ({result.analysis.persons.length})
                    </AccordionSummary>
                    <AccordionDetails>
                      <List dense>
                        {result.analysis.persons.map((p: any, i: number) => (
                          <ListItem key={i}>
                            <ListItemText
                              primary={p.full_name || 'Sin nombre'}
                              secondary={`DNI: ${p.dni || 'N/A'} | Fuente: ${p.source} | Confianza: ${(p.confidence * 100).toFixed(0)}%`}
                            />
                          </ListItem>
                        ))}
                      </List>
                    </AccordionDetails>
                  </Accordion>
                )}

                {result.analysis?.contacts?.length > 0 && (
                  <Accordion>
                    <AccordionSummary expandIcon={<ExpandMore />}>
                      <ContactPhone sx={{ mr: 1 }} /> Contactos ({result.analysis.contacts.length})
                    </AccordionSummary>
                    <AccordionDetails>
                      <List dense>
                        {result.analysis.contacts.map((c: any, i: number) => (
                          <ListItem key={i}>
                            <ListItemText
                              primary={`${c.contact_type}: ${c.value}`}
                              secondary={`Dominio: ${c.domain || 'N/A'} | Fuente: ${c.source}`}
                            />
                          </ListItem>
                        ))}
                      </List>
                    </AccordionDetails>
                  </Accordion>
                )}

                {result.analysis?.locations?.length > 0 && (
                  <Accordion>
                    <AccordionSummary expandIcon={<ExpandMore />}>
                      <LocationOn sx={{ mr: 1 }} /> Ubicaciones ({result.analysis.locations.length})
                    </AccordionSummary>
                    <AccordionDetails>
                      <List dense>
                        {result.analysis.locations.map((l: any, i: number) => (
                          <ListItem key={i}>
                            <ListItemText
                              primary={`${l.latitude?.toFixed(6)}, ${l.longitude?.toFixed(6)}`}
                              secondary={`${l.address || ''} ${l.city || ''} | Precision: ${l.accuracy_meters}m`}
                            />
                          </ListItem>
                        ))}
                      </List>
                    </AccordionDetails>
                  </Accordion>
                )}

                {result.analysis?.sunat_results?.length > 0 && (
                  <Accordion>
                    <AccordionSummary expandIcon={<ExpandMore />}>
                      <Security sx={{ mr: 1 }} /> Registros SUNAT ({result.analysis.sunat_results.length})
                    </AccordionSummary>
                    <AccordionDetails>
                      <List dense>
                        {result.analysis.sunat_results.map((s: any, i: number) => (
                          <ListItem key={i}>
                            <ListItemText
                              primary={`RUC: ${s.ruc} - ${s.razon_social}`}
                              secondary={`Estado: ${s.estado} | Condicion: ${s.condicion_domicilio} | Direccion: ${s.direccion || 'N/A'}`}
                            />
                          </ListItem>
                        ))}
                      </List>
                    </AccordionDetails>
                  </Accordion>
                )}

                {result.analysis?.breach_results?.length > 0 && (
                  <Accordion>
                    <AccordionSummary expandIcon={<ExpandMore />}>
                      <ErrorIcon sx={{ mr: 1 }} color="error" /> Breach Data ({result.analysis.breach_results.length})
                    </AccordionSummary>
                    <AccordionDetails>
                      {result.analysis.breach_results.map((b: any, i: number) => (
                        <Alert key={i} severity={b.is_compromised ? 'error' : 'info'} sx={{ mb: 1 }}>
                          {b.email || b.phone}: {b.compromise_count} brechas detectadas
                        </Alert>
                      ))}
                    </AccordionDetails>
                  </Accordion>
                )}
              </CardContent>
            </Card>
          )}
        </Grid>
      </Grid>
    </Box>
  );
};

export default Investigation;
