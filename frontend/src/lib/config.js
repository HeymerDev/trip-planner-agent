// Unica configuracion del navegador: URLs y IDs PUBLICOS. Ningun secreto ni credencial AWS (RNF-11).
export const config = {
  apiUrl: (import.meta.env.VITE_API_URL || '').replace(/\/$/, ''),
  agentUrl: import.meta.env.VITE_AGENT_URL || '',
  userPoolId: import.meta.env.VITE_USER_POOL_ID || '',
  clientId: import.meta.env.VITE_CLIENT_ID || '',
}
