# Evidencia 01 — Pruebas reales del backend serverless

- Fecha de ejecucion: 2026-11-16 05:18 UTC
- API: `https://1uyl298pkh.execute-api.us-east-2.amazonaws.com` (API Gateway HTTP + Lambda + DynamoDB, region us-east-2)
- Usuarios: dos cuentas de prueba creadas en Cognito (A y B) para verificar el aislamiento.
- **Resultado: 34/34 comprobaciones correctas**

| # | Comprobacion | Resultado |
|---|---|---|
| 1 | Sin token → 401 | ✅ |
| 2 | Token invalido → 401 | ✅ |
| 3 | Perfil creado en el primer acceso | ✅ |
| 4 | Viaje invalido → 400 con lista de campos | ✅ |
| 5 | Crear viaje → 201 | ✅ |
| 6 | Listar viajes | ✅ |
| 7 | Actualizar viaje (PATCH) | ✅ |
| 8 | Usuario B no ve el viaje de A → 404 | ✅ |
| 9 | Usuario B no puede modificarlo → 404 | ✅ |
| 10 | Usuario B no puede borrarlo → 404 | ✅ |
| 11 | Usuario B tiene su lista vacia | ✅ |
| 12 | Crear itinerario → 201 | ✅ |
| 13 | Crear de nuevo → 409 | ✅ |
| 14 | Fecha fuera del viaje → 400 | ✅ |
| 15 | Modificar itinerario (PUT) | ✅ |
| 16 | Usuario B no accede al itinerario → 404 | ✅ |
| 17 | Compra sin saldo → 409 INSUFFICIENT_FUNDS | ✅ |
| 18 | Recarga simulada → 201 | ✅ |
| 19 | Recarga fuera de rango → 400 | ✅ |
| 20 | Compra → 201 (descuenta y crea reserva SIMULADA) | ✅ |
| 21 | Compra repetida (misma clave) → 409 DUPLICATE, sin doble cobro | ✅ |
| 22 | Saldo tras la compra: 1.580.000 | ✅ |
| 23 | Reserva de hotel pendiente (sin cobro) | ✅ |
| 24 | Listar reservas del viaje | ✅ |
| 25 | Confirmar como usuario → 409 PROVIDER_ONLY | ✅ |
| 26 | Usuario B no ve la reserva → 404 | ✅ |
| 27 | Usuario B no puede crear reserva en viaje de A → 404 | ✅ |
| 28 | Cancelar reserva pagada → 200 y reembolso | ✅ |
| 29 | Saldo restituido: 2.000.000 (un solo reembolso) | ✅ |
| 30 | Cancelar de nuevo es idempotente (sin doble reembolso) | ✅ |
| 31 | Panel de usuario | ✅ |
| 32 | Resumen del viaje con presupuesto | ✅ |
| 33 | Preflight desde el origen de la aplicacion | ✅ |
| 34 | Preflight desde un origen no permitido (sin cabecera Allow-Origin) | ✅ |

---

## 1. Autenticacion y autorizacion (RNF-13, RNF-14, CA-1)

### ✅ Sin token → 401

`GET /trips` → **401** (esperado 401)

Respuesta:
```json
{
  "message": "Unauthorized"
}
```

### ✅ Token invalido → 401

`GET /trips` → **401** (esperado 401)

Respuesta:
```json
{
  "message": "Unauthorized"
}
```

### ✅ Perfil creado en el primer acceso

`GET /me` → **200** (esperado 200)

Respuesta:
```json
{
  "id": "31cb2570-a041-706b-7570-f945b7329926",
  "email": "31cb2570-a041-706b-7570-f945b7329926",
  "name": "",
  "createdAt": "2026-11-16T05:17:19.615Z"
}
```

## 2. Viajes (RF-40, RF-41) y validacion (RNF-12, CA-2)

### ✅ Viaje invalido → 400 con lista de campos

`POST /trips` → **400** (esperado 400)

Cuerpo enviado:
```json
{
  "origin": "B",
  "destination": "",
  "startDate": "2026-13-40",
  "endDate": "2026-12-01",
  "travelers": 0,
  "budgetCOP": -1
}
```

Respuesta:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Hay datos invalidos en la peticion.",
    "fields": {
      "origin": "Debe tener entre 2 y 80 caracteres.",
      "destination": "Debe tener entre 2 y 80 caracteres.",
      "startDate": "No es una fecha valida.",
      "travelers": "Debe estar entre 1 y 20.",
      "budgetCOP": "Debe estar entre 0 y 1000000000."
    }
  }
}
```

### ✅ Crear viaje → 201

`POST /trips` → **201** (esperado 201)

Cuerpo enviado:
```json
{
  "name": "Vacaciones Cartagena",
  "origin": "Bogota",
  "destination": "Cartagena",
  "startDate": "2026-12-10",
  "endDate": "2026-12-13",
  "travelers": 3,
  "budgetCOP": 5000000
}
```

Respuesta:
```json
{
  "name": "Vacaciones Cartagena",
  "origin": "Bogota",
  "destination": "Cartagena",
  "startDate": "2026-12-10",
  "endDate": "2026-12-13",
  "travelers": 3,
  "budgetCOP": 5000000,
  "notes": "",
  "status": "PLANEADO",
  "createdAt": "2026-11-16T05:17:20.723Z",
  "updatedAt": "2026-11-16T05:17:20.723Z",
  "id": "9a9f6091fa224f47"
}
```

### ✅ Listar viajes

`GET /trips` → **200** (esperado 200)

Respuesta:
```json
{
  "trips": [
    {
      "travelers": 3,
      "origin": "Bogota",
      "budgetCOP": 5000000,
      "endDate": "2026-12-13",
      "status": "PLANEADO",
      "createdAt": "2026-11-16T05:17:20.723Z",
      "name": "Vacaciones Cartagena",
      "updatedAt": "2026-11-16T05:17:20.723Z",
      "notes": "",
      "startDate": "2026-12-10",
      "destination": "Cartagena",
      "id": "9a9f6091fa224f47"
    }
  ]
}
```

### ✅ Actualizar viaje (PATCH)

`PATCH /trips/9a9f6091fa224f47` → **200** (esperado 200)

Cuerpo enviado:
```json
{
  "budgetCOP": 5500000
}
```

Respuesta:
```json
{
  "origin": "Bogota",
  "destination": "Cartagena",
  "notes": "",
  "startDate": "2026-12-10",
  "budgetCOP": 5500000,
  "createdAt": "2026-11-16T05:17:20.723Z",
  "name": "Vacaciones Cartagena",
  "status": "PLANEADO",
  "travelers": 3,
  "updatedAt": "2026-11-16T05:17:22.526Z",
  "endDate": "2026-12-13",
  "id": "9a9f6091fa224f47"
}
```

### ✅ Usuario B no ve el viaje de A → 404

`GET /trips/9a9f6091fa224f47` → **404** (esperado 404)

Respuesta:
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Viaje no encontrado."
  }
}
```

### ✅ Usuario B no puede modificarlo → 404

`PATCH /trips/9a9f6091fa224f47` → **404** (esperado 404)

Cuerpo enviado:
```json
{
  "name": "hackeado"
}
```

Respuesta:
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Viaje no encontrado."
  }
}
```

### ✅ Usuario B no puede borrarlo → 404

`DELETE /trips/9a9f6091fa224f47` → **404** (esperado 404)

Respuesta:
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Viaje no encontrado."
  }
}
```

### ✅ Usuario B tiene su lista vacia

`GET /trips` → **200** (esperado 200)

Respuesta:
```json
{
  "trips": []
}
```

## 3. Itinerario (RF-42)

### ✅ Crear itinerario → 201

`POST /trips/9a9f6091fa224f47/itinerary` → **201** (esperado 201)

Cuerpo enviado:
```json
{
  "days": [
    {
      "date": "2026-12-10",
      "items": [
        {
          "time": "16:00",
          "title": "Check-in y paseo por la Ciudad Amurallada",
          "place": "Centro historico",
          "costCOP": 0
        },
        {
          "time": "19:30",
          "title": "Cena en Getsemani",
          "place": "Getsemani",
          "costCOP": 180000
        }
      ]
    },
    {
      "date": "2026-12-11",
      "items": [
        {
          "time": "09:00",
          "title": "Tour Islas del Rosario",
          "place": "Muelle de la Bodeguita",
          "costCOP": 420000
        }
      ]
    }
  ]
}
```

Respuesta:
```json
{
  "tripId": "9a9f6091fa224f47",
  "days": [
    {
      "date": "2026-12-10",
      "items": [
        {
          "time": "16:00",
          "title": "Check-in y paseo por la Ciudad Amurallada",
          "place": "Centro historico",
          "costCOP": 0,
          "notes": ""
        },
        {
          "time": "19:30",
          "title": "Cena en Getsemani",
          "place": "Getsemani",
          "costCOP": 180000,
          "notes": ""
        }
      ]
    },
    {
      "date": "2026-12-11",
      "items": [
        {
          "time": "09:00",
          "title": "Tour Islas del Rosario",
          "place": "Muelle de la Bodeguita",
          "costCOP": 420000,
          "notes": ""
        }
      ]
    }
  ],
  "updatedAt": "2026-11-16T05:17:25.287Z"
}
```

### ✅ Crear de nuevo → 409

`POST /trips/9a9f6091fa224f47/itinerary` → **409** (esperado 409)

Cuerpo enviado:
```json
{
  "days": [
    {
      "date": "2026-12-10",
      "items": [
        {
          "time": "16:00",
          "title": "Check-in y paseo por la Ciudad Amurallada",
          "place": "Centro historico",
          "costCOP": 0
        },
        {
          "time": "19:30",
          "title": "Cena en Getsemani",
          "place": "Getsemani",
          "costCOP": 180000
        }
      ]
    },
    {
      "date": "2026-12-11",
      "items": [
        {
          "time": "09:00",
          "title": "Tour Islas del Rosario",
          "place": "Muelle de la Bodeguita",
          "costCOP": 420000
        }
      ]
    }
  ]
}
```

Respuesta:
```json
{
  "error": {
    "code": "ITINERARY_EXISTS",
    "message": "El viaje ya tiene itinerario; usa la actualizacion."
  }
}
```

### ✅ Fecha fuera del viaje → 400

`PUT /trips/9a9f6091fa224f47/itinerary` → **400** (esperado 400)

Cuerpo enviado:
```json
{
  "days": [
    {
      "date": "2027-01-01",
      "items": []
    }
  ]
}
```

Respuesta:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Hay datos invalidos en la peticion.",
    "fields": {
      "days[0].date": "Debe estar dentro de las fechas del viaje."
    }
  }
}
```

### ✅ Modificar itinerario (PUT)

`PUT /trips/9a9f6091fa224f47/itinerary` → **200** (esperado 200)

Cuerpo enviado:
```json
{
  "days": [
    {
      "date": "2026-12-10",
      "items": [
        {
          "time": "16:00",
          "title": "Check-in y paseo por la Ciudad Amurallada",
          "place": "Centro historico",
          "costCOP": 0
        },
        {
          "time": "19:30",
          "title": "Cena en Getsemani",
          "place": "Getsemani",
          "costCOP": 180000
        }
      ]
    },
    {
      "date": "2026-12-11",
      "items": [
        {
          "time": "09:00",
          "title": "Tour Islas del Rosario",
          "place": "Muelle de la Bodeguita",
          "costCOP": 420000
        }
      ]
    }
  ]
}
```

Respuesta:
```json
{
  "tripId": "9a9f6091fa224f47",
  "days": [
    {
      "date": "2026-12-10",
      "items": [
        {
          "time": "16:00",
          "title": "Check-in y paseo por la Ciudad Amurallada",
          "place": "Centro historico",
          "costCOP": 0,
          "notes": ""
        },
        {
          "time": "19:30",
          "title": "Cena en Getsemani",
          "place": "Getsemani",
          "costCOP": 180000,
          "notes": ""
        }
      ]
    },
    {
      "date": "2026-12-11",
      "items": [
        {
          "time": "09:00",
          "title": "Tour Islas del Rosario",
          "place": "Muelle de la Bodeguita",
          "costCOP": 420000,
          "notes": ""
        }
      ]
    }
  ],
  "updatedAt": "2026-11-16T05:17:26.288Z"
}
```

### ✅ Usuario B no accede al itinerario → 404

`GET /trips/9a9f6091fa224f47/itinerary` → **404** (esperado 404)

Respuesta:
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Viaje no encontrado."
  }
}
```

## 4. Monedero, compra atomica y reservas (RF-50..65, CA-3, CA-4)

### ✅ Compra sin saldo → 409 INSUFFICIENT_FUNDS

`POST /purchases` → **409** (esperado 409)

Cuerpo enviado:
```json
{
  "tripId": "9a9f6091fa224f47",
  "kind": "FLIGHT",
  "title": "BOG → CTG · LATAM",
  "priceCOP": 420000,
  "details": {
    "airline": "LATAM",
    "departure": "2026-12-10T07:40"
  },
  "link": "https://www.google.com/travel/flights",
  "idempotencyKey": "evidencia-compra-0001"
}
```

Respuesta:
```json
{
  "error": {
    "code": "INSUFFICIENT_FUNDS",
    "message": "Saldo insuficiente: la compra cuesta 420.000 COP y tu saldo es 0 COP. Recarga el monedero e intenta de nuevo."
  }
}
```

### ✅ Recarga simulada → 201

`POST /wallet/topup` → **201** (esperado 201)

Cuerpo enviado:
```json
{
  "amountCOP": 2000000
}
```

Respuesta:
```json
{
  "balanceCOP": 2000000,
  "transactions": [
    {
      "amountCOP": 2000000,
      "title": "Recarga simulada",
      "createdAt": "2026-11-16T05:17:28.484Z",
      "type": "TOPUP",
      "id": "b495aff6c81843dc"
    }
  ]
}
```

### ✅ Recarga fuera de rango → 400

`POST /wallet/topup` → **400** (esperado 400)

Cuerpo enviado:
```json
{
  "amountCOP": 5
}
```

Respuesta:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Hay datos invalidos en la peticion.",
    "fields": {
      "amountCOP": "Debe estar entre 1000 y 10000000."
    }
  }
}
```

### ✅ Compra → 201 (descuenta y crea reserva SIMULADA)

`POST /purchases` → **201** (esperado 201)

Cuerpo enviado:
```json
{
  "tripId": "9a9f6091fa224f47",
  "kind": "FLIGHT",
  "title": "BOG → CTG · LATAM",
  "priceCOP": 420000,
  "details": {
    "airline": "LATAM",
    "departure": "2026-12-10T07:40"
  },
  "link": "https://www.google.com/travel/flights",
  "idempotencyKey": "evidencia-compra-0001"
}
```

Respuesta:
```json
{
  "reservation": {
    "tripId": "9a9f6091fa224f47",
    "kind": "FLIGHT",
    "title": "BOG → CTG · LATAM",
    "priceCOP": 420000,
    "details": {
      "airline": "LATAM",
      "departure": "2026-12-10T07:40"
    },
    "status": "SIMULADA",
    "paid": true,
    "createdAt": "2026-11-16T05:17:29.189Z",
    "updatedAt": "2026-11-16T05:17:29.189Z",
    "link": "https://www.google.com/travel/flights",
    "id": "5c1798f2dbbbf327"
  },
  "balanceCOP": 1580000
}
```

### ✅ Compra repetida (misma clave) → 409 DUPLICATE, sin doble cobro

`POST /purchases` → **409** (esperado 409)

Cuerpo enviado:
```json
{
  "tripId": "9a9f6091fa224f47",
  "kind": "FLIGHT",
  "title": "BOG → CTG · LATAM",
  "priceCOP": 420000,
  "details": {
    "airline": "LATAM",
    "departure": "2026-12-10T07:40"
  },
  "link": "https://www.google.com/travel/flights",
  "idempotencyKey": "evidencia-compra-0001"
}
```

Respuesta:
```json
{
  "error": {
    "code": "DUPLICATE",
    "message": "Esta compra ya fue registrada; no se cobro de nuevo."
  }
}
```

### ✅ Saldo tras la compra: 1.580.000

`GET /wallet` → **200** (esperado 200)

Respuesta:
```json
{
  "balanceCOP": 1580000,
  "transactions": [
    {
      "amountCOP": -420000,
      "type": "PURCHASE",
      "title": "BOG → CTG · LATAM",
      "reservationId": "5c1798f2dbbbf327",
      "createdAt": "2026-11-16T05:17:29.189Z",
      "id": "8e244f6fef2a46fa"
    },
    {
      "title": "Recarga simulada",
      "createdAt": "2026-11-16T05:17:28.484Z",
      "type": "TOPUP",
      "amountCOP": 2000000,
      "id": "b495aff6c81843dc"
    }
  ]
}
```

### ✅ Reserva de hotel pendiente (sin cobro)

`POST /reservations` → **201** (esperado 201)

Cuerpo enviado:
```json
{
  "tripId": "9a9f6091fa224f47",
  "kind": "HOTEL",
  "title": "Hotel Casa San Agustin",
  "priceCOP": 2076000,
  "status": "PENDIENTE"
}
```

Respuesta:
```json
{
  "tripId": "9a9f6091fa224f47",
  "kind": "HOTEL",
  "title": "Hotel Casa San Agustin",
  "priceCOP": 2076000,
  "details": {},
  "status": "PENDIENTE",
  "paid": false,
  "createdAt": "2026-11-16T05:17:32.008Z",
  "updatedAt": "2026-11-16T05:17:32.008Z",
  "id": "fe8efcc367b34c90"
}
```

### ✅ Listar reservas del viaje

`GET /reservations?tripId=9a9f6091fa224f47` → **200** (esperado 200)

Respuesta:
```json
{
  "reservations": [
    {
      "priceCOP": 2076000,
      "tripId": "9a9f6091fa224f47",
      "kind": "HOTEL",
      "updatedAt": "2026-11-16T05:17:32.008Z",
      "status": "PENDIENTE",
      "createdAt": "2026-11-16T05:17:32.008Z",
      "details": {},
      "title": "Hotel Casa San Agustin",
      "paid": false,
      "id": "fe8efcc367b34c90"
    },
    {
      "kind": "FLIGHT",
      "updatedAt": "2026-11-16T05:17:29.189Z",
      "paid": true,
      "title": "BOG → CTG · LATAM",
      "link": "https://www.google.com/travel/flights",
      "status": "SIMULADA",
      "priceCOP": 420000,
      "details": {
        "airline": "LATAM",
        "departure": "2026-12-10T07:40"
      },
      "createdAt": "2026-11-16T05:17:29.189Z",
      "tripId": "9a9f6091fa224f47",
      "id": "5c1798f2dbbbf327"
    }
  ]
}
```

### ✅ Confirmar como usuario → 409 PROVIDER_ONLY

`PATCH /reservations/5c1798f2dbbbf327` → **409** (esperado 409)

Cuerpo enviado:
```json
{
  "status": "CONFIRMADA"
}
```

Respuesta:
```json
{
  "error": {
    "code": "PROVIDER_ONLY",
    "message": "Solo un proveedor real puede confirmar una reserva."
  }
}
```

### ✅ Usuario B no ve la reserva → 404

`GET /reservations/5c1798f2dbbbf327` → **404** (esperado 404)

Respuesta:
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Reserva no encontrado."
  }
}
```

### ✅ Usuario B no puede crear reserva en viaje de A → 404

`POST /reservations` → **404** (esperado 404)

Cuerpo enviado:
```json
{
  "tripId": "9a9f6091fa224f47",
  "kind": "FLIGHT",
  "title": "BOG → CTG · LATAM",
  "priceCOP": 420000,
  "details": {
    "airline": "LATAM",
    "departure": "2026-12-10T07:40"
  },
  "link": "https://www.google.com/travel/flights",
  "idempotencyKey": null
}
```

Respuesta:
```json
{
  "error": {
    "code": "TRIP_NOT_FOUND",
    "message": "El viaje indicado no existe."
  }
}
```

### ✅ Cancelar reserva pagada → 200 y reembolso

`PATCH /reservations/5c1798f2dbbbf327` → **200** (esperado 200)

Cuerpo enviado:
```json
{
  "status": "CANCELADA"
}
```

Respuesta:
```json
{
  "paid": true,
  "updatedAt": "2026-11-16T05:17:47.503Z",
  "title": "BOG → CTG · LATAM",
  "link": "https://www.google.com/travel/flights",
  "refunded": true,
  "priceCOP": 420000,
  "details": {
    "airline": "LATAM",
    "departure": "2026-12-10T07:40"
  },
  "createdAt": "2026-11-16T05:17:29.189Z",
  "status": "CANCELADA",
  "kind": "FLIGHT",
  "tripId": "9a9f6091fa224f47",
  "id": "5c1798f2dbbbf327"
}
```

### ✅ Saldo restituido: 2.000.000 (un solo reembolso)

`GET /wallet` → **200** (esperado 200)

Respuesta:
```json
{
  "balanceCOP": 2000000,
  "transactions": [
    {
      "type": "REFUND",
      "reservationId": "5c1798f2dbbbf327",
      "amountCOP": 420000,
      "createdAt": "2026-11-16T05:17:47.503Z",
      "title": "BOG → CTG · LATAM",
      "id": "27a5ab79d9c2473a"
    },
    {
      "createdAt": "2026-11-16T05:17:29.189Z",
      "type": "PURCHASE",
      "reservationId": "5c1798f2dbbbf327",
      "amountCOP": -420000,
      "title": "BOG → CTG · LATAM",
      "id": "8e244f6fef2a46fa"
    },
    {
      "amountCOP": 2000000,
      "title": "Recarga simulada",
      "createdAt": "2026-11-16T05:17:28.484Z",
      "type": "TOPUP",
      "id": "b495aff6c81843dc"
    }
  ]
}
```

### ✅ Cancelar de nuevo es idempotente (sin doble reembolso)

`PATCH /reservations/5c1798f2dbbbf327` → **200** (esperado 200)

Cuerpo enviado:
```json
{
  "status": "CANCELADA"
}
```

Respuesta:
```json
{
  "createdAt": "2026-11-16T05:17:29.189Z",
  "status": "CANCELADA",
  "priceCOP": 420000,
  "tripId": "9a9f6091fa224f47",
  "details": {
    "airline": "LATAM",
    "departure": "2026-12-10T07:40"
  },
  "kind": "FLIGHT",
  "link": "https://www.google.com/travel/flights",
  "refunded": true,
  "updatedAt": "2026-11-16T05:17:47.503Z",
  "paid": true,
  "title": "BOG → CTG · LATAM",
  "id": "5c1798f2dbbbf327"
}
```

### ✅ Panel de usuario

`GET /dashboard` → **200** (esperado 200)

Respuesta:
```json
{
  "upcomingTrips": [
    {
      "budgetCOP": 5500000,
      "createdAt": "2026-11-16T05:17:20.723Z",
      "destination": "Cartagena",
      "endDate": "2026-12-13",
      "name": "Vacaciones Cartagena",
      "notes": "",
      "origin": "Bogota",
      "startDate": "2026-12-10",
      "status": "PLANEADO",
      "travelers": 3,
      "updatedAt": "2026-11-16T05:17:22.526Z",
      "id": "9a9f6091fa224f47"
    }
  ],
  "recentReservations": [
    {
      "priceCOP": 2076000,
      "tripId": "9a9f6091fa224f47",
      "kind": "HOTEL",
      "updatedAt": "2026-11-16T05:17:32.008Z",
      "status": "PENDIENTE",
      "createdAt": "2026-11-16T05:17:32.008Z",
      "details": {},
      "title": "Hotel Casa San Agustin",
      "paid": false,
      "id": "fe8efcc367b34c90"
    },
    {
      "createdAt": "2026-11-16T05:17:29.189Z",
      "status": "CANCELADA",
      "updatedAt": "2026-11-16T05:17:47.503Z",
      "priceCOP": 420000,
      "link": "https://www.google.com/travel/flights",
      "paid": true,
      "kind": "FLIGHT",
      "title": "BOG → CTG · LATAM",
      "tripId": "9a9f6091fa224f47",
      "refunded": true,
      "details": {
        "airline": "LATAM",
        "departure": "2026-12-10T07:40"
      },
      "id": "5c1798f2dbbbf327"
    }
  ],
  "walletBalanceCOP": 2000000,
  "counts": {
    "trips": 1,
    "reservations": 1
  },
  "totalReservedCOP": 2076000
}
```

### ✅ Resumen del viaje con presupuesto

`GET /trips/9a9f6091fa224f47` → **200** (esperado 200)

Respuesta:
```json
{
  "trip": {
    "budgetCOP": 5500000,
    "createdAt": "2026-11-16T05:17:20.723Z",
    "destination": "Cartagena",
    "endDate": "2026-12-13",
    "name": "Vacaciones Cartagena",
    "notes": "",
    "origin": "Bogota",
    "startDate": "2026-12-10",
    "status": "PLANEADO",
    "travelers": 3,
    "updatedAt": "2026-11-16T05:17:22.526Z",
    "id": "9a9f6091fa224f47"
  },
  "itinerary": {
    "tripId": "9a9f6091fa224f47",
    "days": [
      {
        "date": "2026-12-10",
        "items": [
          {
            "costCOP": 0,
            "notes": "",
            "place": "Centro historico",
            "time": "16:00",
            "title": "Check-in y paseo por la Ciudad Amurallada"
          },
          {
            "costCOP": 180000,
            "notes": "",
            "place": "Getsemani",
            "time": "19:30",
            "title": "Cena en Getsemani"
          }
        ]
      },
      {
        "date": "2026-12-11",
        "items": [
          {
            "costCOP": 420000,
            "notes": "",
            "place": "Muelle de la Bodeguita",
            "time": "09:00",
            "title": "Tour Islas del Rosario"
          }
        ]
      }
    ],
    "updatedAt": "2026-11-16T05:17:26.288Z"
  },
  "reservations": [
    {
      "paid": true,
      "updatedAt": "2026-11-16T05:17:47.503Z",
      "title": "BOG → CTG · LATAM",
      "link": "https://
... (recortado)
```

## 5. CORS (RNF-14)

### ✅ Preflight desde el origen de la aplicacion

`OPTIONS /trips` → **204** (esperado 204)

Cabecera `access-control-allow-origin`: `https://d33bzx67i3x8j6.cloudfront.net`

Cabecera `access-control-allow-headers`: `authorization,content-type`

Respuesta:
```json
(sin cuerpo)
```

### ✅ Preflight desde un origen no permitido (sin cabecera Allow-Origin)

`OPTIONS /trips` → **204** (esperado 204)

Cabecera `access-control-allow-origin`: `None`

Respuesta:
```json
(sin cuerpo)
```
