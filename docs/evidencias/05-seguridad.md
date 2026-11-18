# Evidencia 05 — Pruebas de seguridad

Fecha: 2026-11-16 06:11 UTC

## 1. El endpoint del Orchestrator exige JWT (RNF-17)

```
# sin token:
HTTP 401
# token inválido:
HTTP 403
```

## 2. Sin credenciales ni secretos en el código del navegador (RNF-11, CA-5)

```
# Patrones buscados en dist/ (JS, CSS, HTML): claves de acceso AWS, secretos, claves de Gemini/RapidAPI
AKIA[0-9A-Z]{16} -> 0 archivos
ASIA[0-9A-Z]{16} -> 0 archivos
aws_secret_access_key -> 0 archivos
AIza[0-9A-Za-z_-]{20,} -> 0 archivos
AQ\.[A-Za-z0-9_-]{20,} -> 0 archivos
x-rapidapi-key -> 0 archivos
GEMINI_API_KEY -> 0 archivos
client_secret -> 0 archivos
# URLs/IDs públicos presentes en el bundle:
bedrock-agentcore.us-east-2.amazonaws.com
execute-api.us-east-2.amazonaws.com
us-east-2_cZUoWl8uB
```

## 3. Cabeceras de seguridad de CloudFront

```
HTTP/1.1 200 OK
X-Frame-Options: DENY
Referrer-Policy: same-origin
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https://*.execute-api.us-east-2.amazonaws.com https://bedrock-agentcore.us-east-2.amazonaws.com https://cognito-idp.us-east-2.amazonaws.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'
X-Content-Type-Options: nosniff
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

## 4. El bucket de S3 no es accesible directamente (solo vía CloudFront con OAC)

```
GET https://tripplanner-backend-frontendbucket-bo23mdyjrjqt.s3.us-east-2.amazonaws.com/index.html -> HTTP 403
```

## 5. Seguridad de datos (cubierto en la evidencia 01)

- API: sin token → 401; token inválido → 401 · usuario B no ve/modifica/borra recursos de A → 404 · el cuerpo no puede cambiar el dueño.
- Validación: 400 con lista de campos · CORS: origen no permitido sin cabecera `Access-Control-Allow-Origin`.
- Roles IAM de mínimo privilegio por Lambda (evidencia 03); el Orchestrator no tiene permisos sobre DynamoDB.
