import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  Box, Typography, Card, CardContent, Button, LinearProgress, CircularProgress,
  Chip, Alert, Grid, TextField, List, ListItem, ListItemText,
} from '@mui/material';
import { CloudUpload, Image as ImageIcon, CheckCircle, Error as ErrorIcon } from '@mui/icons-material';
import { ingestEvidence } from '../utils/api';

interface UploadResult {
  filename: string;
  hash: string;
  status: 'success' | 'error';
  message: string;
  metadata?: any;
}

const EvidenceUpload: React.FC = () => {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState<UploadResult[]>([]);
  const [investigationId, setInvestigationId] = useState('');
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const validFiles = acceptedFiles.filter(f => {
      const validTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/tiff'];
      const validSize = f.size <= 50 * 1024 * 1024;
      return validTypes.includes(f.type) && validSize;
    });
    setFiles(prev => [...prev, ...validFiles]);
    setError(null);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': ['.jpeg', '.jpg', '.png', '.webp', '.tiff'] },
    maxSize: 50 * 1024 * 1024,
  });

  const handleUpload = async () => {
    if (files.length === 0) return;
    if (!investigationId.match(/^INV-\d{4}-\d{3}$/)) {
      setError('ID de investigacion invalido. Formato: INV-AAAA-NNN');
      return;
    }

    setUploading(true);
    setProgress(0);
    setError(null);
    const newResults: UploadResult[] = [];

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      try {
        const formData = new FormData();
        formData.append('investigation_id', investigationId);
        formData.append('image', file);

        const data = await ingestEvidence(formData);

        newResults.push({
          filename: file.name,
          hash: data.data?.analysis?.assets?.[0]?.hash || 'unknown',
          status: data.success ? 'success' : 'error',
          message: data.message || 'Procesado',
          metadata: data.data?.analysis?.assets?.[0]?.exif_data,
        });
      } catch (err: any) {
        newResults.push({
          filename: file.name,
          hash: 'error',
          status: 'error',
          message: err.message || 'Error de conexion',
        });
      }
      setProgress(((i + 1) / files.length) * 100);
    }

    setResults(newResults);
    setUploading(false);
    setFiles([]);
  };

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom fontWeight={700}>Subir Evidencia</Typography>
      <Typography variant="body2" color="text.secondary" gutterBottom>
        Sube imagenes para analisis forense automatico (EXIF, VLM, NER)
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card sx={{ bgcolor: 'background.paper' }}>
            <CardContent>
              <TextField
                fullWidth
                label="ID Investigacion"
                value={investigationId}
                onChange={(e) => setInvestigationId(e.target.value)}
                margin="normal"
                placeholder="INV-2026-001"
                helperText="Formato requerido: INV-AAAA-NNN"
              />

              <Box
                {...getRootProps()}
                sx={{
                  border: '2px dashed',
                  borderColor: isDragActive ? 'primary.main' : 'grey.500',
                  borderRadius: 2,
                  p: 4,
                  textAlign: 'center',
                  cursor: 'pointer',
                  bgcolor: isDragActive ? 'rgba(25, 118, 210, 0.08)' : 'transparent',
                  transition: 'all 0.2s',
                  mt: 2,
                }}
              >
                <input {...getInputProps()} />
                <CloudUpload sx={{ fontSize: 48, color: 'primary.main', mb: 1 }} />
                <Typography variant="h6">
                  {isDragActive ? 'Suelta los archivos aqui' : 'Arrastra imagenes aqui'}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  o haz clic para seleccionar (JPEG, PNG, WEBP, TIFF - max 50MB)
                </Typography>
              </Box>

              {files.length > 0 && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>Archivos seleccionados:</Typography>
                  <List dense>
                    {files.map((file, i) => (
                      <ListItem
                        key={i}
                        secondaryAction={
                          <Button size="small" color="error" onClick={() => removeFile(i)}>
                            Eliminar
                          </Button>
                        }
                      >
                        <ImageIcon sx={{ mr: 1, color: 'primary.main' }} />
                        <ListItemText
                          primary={file.name}
                          secondary={`${(file.size / 1024 / 1024).toFixed(2)} MB`}
                        />
                      </ListItem>
                    ))}
                  </List>
                  <Button
                    variant="contained"
                    fullWidth
                    size="large"
                    onClick={handleUpload}
                    disabled={uploading}
                    startIcon={uploading ? <CircularProgress size={20} /> : <CloudUpload />}
                    sx={{ mt: 2 }}
                  >
                    {uploading ? `Procesando... ${progress.toFixed(0)}%` : `Analizar ${files.length} archivo(s)`}
                  </Button>
                  {uploading && <LinearProgress variant="determinate" value={progress} sx={{ mt: 1 }} />}
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          {results.length > 0 && (
            <Card sx={{ bgcolor: 'background.paper' }}>
              <CardContent>
                <Typography variant="h6" gutterBottom fontWeight={600}>
                  Resultados del Procesamiento
                </Typography>
                {results.map((r, i) => (
                  <Alert
                    key={i}
                    severity={r.status === 'success' ? 'success' : 'error'}
                    icon={r.status === 'success' ? <CheckCircle /> : <ErrorIcon />}
                    sx={{ mb: 1 }}
                  >
                    <Typography variant="subtitle2">{r.filename}</Typography>
                    <Typography variant="body2">Hash: {r.hash}</Typography>
                    <Typography variant="body2">{r.message}</Typography>
                    {r.metadata && (
                      <Box sx={{ mt: 1 }}>
                        <Chip label={`Formato: ${r.metadata.format || 'N/A'}`} size="small" sx={{ mr: 0.5 }} />
                        <Chip label={`${r.metadata.width || '?'}x${r.metadata.height || '?'}`} size="small" />
                        {r.metadata.gps && <Chip label="GPS: Si" color="warning" size="small" sx={{ ml: 0.5 }} />}
                      </Box>
                    )}
                  </Alert>
                ))}
              </CardContent>
            </Card>
          )}
        </Grid>
      </Grid>
    </Box>
  );
};

export default EvidenceUpload;
