# Evidencia 03 — Infraestructura desplegada (inventario real)

- Fecha: 2026-11-16 21:47 UTC · Cuenta `406868032460` · Región `us-east-2`
- Stack SAM: `tripplanner-backend` · estado `UPDATE_COMPLETE`

## Salidas del stack

| Salida | Valor |
|---|---|
| ApiUrl | `https://1uyl298pkh.execute-api.us-east-2.amazonaws.com` |
| DistributionId | `E24UKW3FC4X0BO` |
| FrontendBucketName | `tripplanner-backend-frontendbucket-bo23mdyjrjqt` |
| FrontendUrl | `https://d33bzx67i3x8j6.cloudfront.net` |
| TableName | `tripplanner-main` |
| UserPoolClientId | `3nbs02ig7udvkpls95nkfkuirf` |
| UserPoolId | `us-east-2_cZUoWl8uB` |
| UserPoolIssuer | `https://cognito-idp.us-east-2.amazonaws.com/us-east-2_cZUoWl8uB` |

## DynamoDB (Entregable 3)

- Tabla `tripplanner-main` · estado **ACTIVE** · facturación `PAY_PER_REQUEST`
- Ítems actuales (conteo por `Scan` solo para esta evidencia): 4 `ITIN`, 3 `PROFILE`, 5 `RES`, 4 `TRIP`, 11 `TXN`, 5 `WALLET` — total 32
- Claves: `PK` (HASH), `SK` (RANGE)
- Cifrado en reposo: `ENABLED` · Recuperación a un punto en el tiempo: `ENABLED`

## Funciones Lambda y sus permisos IAM (Entregable 2)

| Función | Handler | Runtime | Memoria | Timeout | Acciones DynamoDB permitidas |
|---|---|---|---|---|---|
| `tripplanner-TravelTips` | `handler.lambda_handler` | python3.12 | 256 MB | 15 s | — |
| `tripplanner-conversations` | `conversations.handler` | python3.12 | 256 MB | 25 s | — |
| `tripplanner-itineraries` | `itineraries.handler` | python3.12 | 256 MB | 10 s | GetItem, PutItem |
| `tripplanner-me` | `me.handler` | python3.12 | 256 MB | 10 s | GetItem, PutItem, Query, UpdateItem |
| `tripplanner-presignup` | `presignup.handler` | python3.12 | 256 MB | 10 s | — |
| `tripplanner-reservations` | `reservations.handler` | python3.12 | 256 MB | 10 s | GetItem, PutItem, Query, UpdateItem |
| `tripplanner-trips` | `trips.handler` | python3.12 | 256 MB | 10 s | DeleteItem, GetItem, PutItem, Query, UpdateItem |
| `tripplanner-utils` | `utils.handler` | python3.12 | 256 MB | 20 s | — |
| `tripplanner-wallet` | `wallet.handler` | python3.12 | 256 MB | 10 s | GetItem, PutItem, Query, UpdateItem |

## API Gateway HTTP (Entregable 2)

- `tripplanner-backend` · `https://1uyl298pkh.execute-api.us-east-2.amazonaws.com`
- Autorizador `JWT`: issuer `https://cognito-idp.us-east-2.amazonaws.com/us-east-2_cZUoWl8uB`, audiencia `['3nbs02ig7udvkpls95nkfkuirf']`
- CORS: orígenes `['http://localhost:5173', 'https://d33bzx67i3x8j6.cloudfront.net']`, métodos `['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']`
- Throttling por defecto: `{'DetailedMetricsEnabled': False, 'ThrottlingBurstLimit': 40, 'ThrottlingRateLimit': 20.0}`

Rutas:

- `DELETE /conversations/{id}  (auth: JWT)`
- `DELETE /trips/{id}  (auth: JWT)`
- `GET /conversations  (auth: JWT)`
- `GET /conversations/{id}  (auth: JWT)`
- `GET /dashboard  (auth: JWT)`
- `GET /fx  (auth: JWT)`
- `GET /me  (auth: JWT)`
- `GET /me/preferences  (auth: JWT)`
- `GET /reservations  (auth: JWT)`
- `GET /reservations/{id}  (auth: JWT)`
- `GET /transport  (auth: JWT)`
- `GET /trips  (auth: JWT)`
- `GET /trips/{id}  (auth: JWT)`
- `GET /trips/{id}/itinerary  (auth: JWT)`
- `GET /wallet  (auth: JWT)`
- `PATCH /reservations/{id}  (auth: JWT)`
- `PATCH /trips/{id}  (auth: JWT)`
- `POST /purchases  (auth: JWT)`
- `POST /reservations  (auth: JWT)`
- `POST /trips  (auth: JWT)`
- `POST /trips/{id}/itinerary  (auth: JWT)`
- `POST /wallet/topup  (auth: JWT)`
- `PUT /me  (auth: JWT)`
- `PUT /me/preferences  (auth: JWT)`
- `PUT /trips/{id}/itinerary  (auth: JWT)`

## Cognito

- User Pool `tripplanner-users` (`us-east-2_cZUoWl8uB`) · usuarios estimados: 6
- Política de contraseñas: mínimo 8, mayúscula/minúscula/número
- Trigger PreSignUp: `tripplanner-presignup`

## Frontend: S3 + CloudFront (Entregable 1)

- Bucket `tripplanner-backend-frontendbucket-bo23mdyjrjqt` · objetos: 27 · bloqueo de acceso público: `True`
- CloudFront `E24UKW3FC4X0BO` · estado **Deployed** · URL `https://d33bzx67i3x8j6.cloudfront.net`

## Agentes en Amazon Bedrock AgentCore

| Runtime | Protocolo | Estado | Autorización |
|---|---|---|---|
| `tripplanner_FlightsAgent` | A2A | READY | AWS_IAM |
| `tripplanner_HotelsAgent` | A2A | READY | AWS_IAM |
| `tripplanner_OrchestratorAgent` | HTTP | READY | CUSTOM_JWT (Cognito) |
| `tripplanner_WeatherAgent` | A2A | READY | AWS_IAM |

Memorias de AgentCore: `tripplanner_TripPlannerMemory-ZQN59q9P6T` (ACTIVE)
