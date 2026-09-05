const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';
const ML_SERVICE_URL = import.meta.env.VITE_ML_SERVICE_URL || 'http://localhost:8001';

export async function fetchHealth() {
  const backendRes = await fetch(`${API_BASE_URL}/health/`);
  const mlRes = await fetch(`${ML_SERVICE_URL}/health`);
  
  return {
    backend: await backendRes.json(),
    mlService: await mlRes.json(),
  };
}
