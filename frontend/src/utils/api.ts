/**
 * Cliente API centralizado para Aegis-Peru Frontend
 * Maneja autenticacion, headers de seguridad y errores
 */

const API_BASE = '/api/v1';

interface ApiError {
  success: false;
  message: string;
  request_id?: string;
  timestamp?: string;
}

interface ApiResponse<T = unknown> {
  success: boolean;
  message: string;
  data?: T;
  request_id: string;
  timestamp: string;
}

/**
 * Genera un request ID unico para trazabilidad
 */
function generateRequestId(): string {
  return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Obtiene el token de autenticacion del localStorage
 */
function getAuthToken(): string | null {
  return localStorage.getItem('aegis_token');
}

/**
 * Realiza una peticion a la API con manejo de errores
 */
export async function apiRequest<T = unknown>(
  endpoint: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  const token = getAuthToken();
  const requestId = generateRequestId();

  const headers: Record<string, string> = {
    'X-Request-ID': requestId,
    ...((options.headers as Record<string, string>) || {}),
  };

  // Agregar token de autenticacion si existe
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Solo agregar Content-Type si no es FormData
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    // Manejar 401 - Token expirado o invalido
    if (response.status === 401) {
      localStorage.removeItem('aegis_token');
      window.dispatchEvent(new CustomEvent('aegis:auth:expired'));
      throw new Error('Sesion expirada. Por favor inicie sesion nuevamente.');
    }

    // Manejar 403 - Sin permisos
    if (response.status === 403) {
      throw new Error('No tiene permisos para realizar esta operacion.');
    }

    // Manejar 429 - Rate limit
    if (response.status === 429) {
      throw new Error('Demasiadas peticiones. Por favor espere un momento.');
    }

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.message || `Error del servidor: ${response.status}`
      );
    }

    return data as ApiResponse<T>;
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error('Error de conexion con el servidor. Verifique su conexion.');
    }
    throw error;
  }
}

/**
 * Realiza login
 */
export async function login(username: string, password: string): Promise<string> {
  const formData = new FormData();
  formData.append('username', username);
  formData.append('password', password);

  const response = await apiRequest<{ access_token: string; token_type: string }>(
    '/auth/login',
    {
      method: 'POST',
      body: formData,
    }
  );

  if (response.data?.access_token) {
    localStorage.setItem('aegis_token', response.data.access_token);
    return response.data.access_token;
  }

  throw new Error('Respuesta de login invalida');
}

/**
 * Cierra sesion
 */
export function logout(): void {
  localStorage.removeItem('aegis_token');
  window.dispatchEvent(new CustomEvent('aegis:auth:logout'));
}

/**
 * Verifica si el usuario esta autenticado
 */
export function isAuthenticated(): boolean {
  return !!getAuthToken();
}

/**
 * Obtiene investigaciones paginadas
 */
export async function getInvestigations(page = 1, pageSize = 20) {
  return apiRequest(`/investigations?page=${page}&page_size=${pageSize}`);
}

/**
 * Crea una nueva investigacion
 */
export async function createInvestigation(investigation: {
  case_id: string;
  title: string;
  description?: string;
  priority?: string;
}) {
  return apiRequest('/investigations', {
    method: 'POST',
    body: JSON.stringify(investigation),
  });
}

/**
 * Ingesta evidencia
 */
export async function ingestEvidence(formData: FormData) {
  return apiRequest('/ingest', {
    method: 'POST',
    body: formData,
  });
}

/**
 * Ejecuta query Cypher en el grafo
 */
export async function queryGraph(cypherQuery: string) {
  const formData = new FormData();
  formData.append('cypher_query', cypherQuery);

  return apiRequest('/query', {
    method: 'POST',
    body: formData,
  });
}

/**
 * Exporta investigacion
 */
export async function exportInvestigation(investigationId: string, format = 'json') {
  return apiRequest(`/export/${investigationId}?format=${format}`);
}
