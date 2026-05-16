# Indies Product Agent Specs

Este documento describe los agentes del producto, los poderes que expone el
asistente de auditoría y ejemplos completos de uso. Los ejemplos son
representativos: muestran la forma esperada del flujo sin depender de resultados
reales completos de Mercado Público.

## Contrato principal

Todas las consultas del usuario entran por el mismo endpoint:

```http
POST /api/v1/audit/query
Content-Type: application/json
```

Request:

```json
{
  "message": "Muéstrame órdenes de compra de la Municipalidad de Algarrobo el 05/02/2024"
}
```

Response:

```json
{
  "intent": {
    "tool": "orders_by_org_and_date",
    "parameters": {
      "codigoorg": null,
      "fecha": "05022024",
      "codigo": null,
      "estado": null,
      "codigo_proveedor": null,
      "codigo_organismo": null,
      "organism_name": "Municipalidad de Algarrobo",
      "keywords": [],
      "start_date": null,
      "end_date": null,
      "include_orders": null,
      "include_tenders": null
    },
    "reasoning": "El usuario pidió órdenes de compra para un organismo y una fecha."
  },
  "data": {},
  "detail": null
}
```

Errores principales:

| Status | Cuándo ocurre |
|---|---|
| `422` | Faltan parámetros obligatorios, una fecha no usa `ddmmyyyy`, el rango está invertido o el estado de licitación no es válido. |
| `502` | MiniMax o Mercado Público no responden correctamente. |
| `500` | Falla interna, por ejemplo falta `pandas` para la búsqueda semántica. |

## Arquitectura de agentes

| Agente | Poder | Entrada | Salida |
|---|---|---|---|
| Frontend/usuario | Captura una pregunta en lenguaje natural y la envía al backend. | Texto libre. | `POST /api/v1/audit/query` con `{ "message": "..." }`. |
| FastAPI Audit Orchestrator | Coordina clasificación, validación de parámetros y consulta de datos. | Request del frontend. | `{ intent, data, detail }`. |
| MiniMax Intent Router | Clasifica la intención y extrae parámetros estructurados. | Mensaje del usuario. | `Intent` con `tool`, `parameters` y `reasoning`. |
| Mercado Público Data Agent | Consulta órdenes de compra, licitaciones y compradores públicos. | Parámetros validados por el backend. | JSON de Mercado Público o payload enriquecido. |

## Poderes soportados por `tool`

| Tool | Qué hace | Parámetros requeridos | Backend action |
|---|---|---|---|
| `orders_by_org_and_date` | Busca órdenes de compra de un organismo en una fecha. | `fecha` y `codigoorg`, `codigo_organismo` u `organism_name`. | Resuelve organismo si viene por nombre y llama `get_orders_by_org_and_date`. |
| `orders_by_date` | Busca todas las órdenes de compra de una fecha. | `fecha`. | Llama `get_orders_by_date`. |
| `public_organism_lookup` | Lista o resuelve compradores/organismos públicos. | Opcional: `organism_name`. | Llama `lookup_public_organisms` o `resolve_public_organism`. |
| `tender_by_code` | Busca una licitación por código. | `codigo`. | Llama `get_tender_by_code`. |
| `tenders_current_day` | Busca licitaciones del día actual según Mercado Público. | Ninguno. | Llama `get_tenders_current_day`. |
| `tenders_by_date` | Busca todas las licitaciones de una fecha. | `fecha`. | Llama `get_tenders_by_date`. |
| `tenders_by_status_and_date` | Busca licitaciones por estado y fecha. | `fecha`, `estado`. | Normaliza `estado` y llama `get_tenders_by_status_and_date`. |
| `tenders_by_supplier_and_date` | Busca licitaciones por proveedor y fecha. | `fecha`, `codigo_proveedor`. | Llama `get_tenders_by_supplier_and_date`. |
| `tenders_by_org_and_date` | Busca licitaciones por organismo y fecha. | `fecha` y `codigoorg`, `codigo_organismo` u `organism_name`. | Resuelve organismo si viene por nombre y llama `get_tenders_by_org_and_date`. |
| `semantic_org_date_range_search` | Busca por organismo, rango de fechas y keywords en órdenes y/o licitaciones. | `organism_name` o código, `start_date`, `end_date`, `keywords`. | Expande fechas, consulta fuentes en paralelo y filtra con `pandas`. |
| `unknown` | Marca consultas fuera de los poderes soportados. | Ninguno. | No consulta Mercado Público; retorna `detail`. |

Fechas: MiniMax debe entregar `fecha`, `start_date` y `end_date` en formato
`ddmmyyyy`. Ejemplo: `2024-02-05` se representa como `05022024`.

## Ejemplos de flujo completo

### 1. Órdenes de compra por organismo y fecha

Pregunta:

```text
Muéstrame órdenes de compra de la Municipalidad de Algarrobo el 05/02/2024
```

Intent esperado:

```json
{
  "tool": "orders_by_org_and_date",
  "parameters": {
    "codigoorg": null,
    "codigo_organismo": null,
    "organism_name": "Municipalidad de Algarrobo",
    "fecha": "05022024",
    "codigo": null,
    "estado": null,
    "codigo_proveedor": null,
    "keywords": [],
    "start_date": null,
    "end_date": null,
    "include_orders": null,
    "include_tenders": null
  },
  "reasoning": "La pregunta pide órdenes de compra para un organismo y una fecha."
}
```

Acción backend:

```text
Resolver "Municipalidad de Algarrobo" con BuscarComprador.
Si hay un organismo único, consultar ordenesdecompra.json con CodigoOrganismo y fecha=05022024.
```

Respuesta resumida:

```json
{
  "intent": {
    "tool": "orders_by_org_and_date",
    "parameters": {
      "organism_name": "Municipalidad de Algarrobo",
      "fecha": "05022024"
    },
    "reasoning": "La pregunta pide órdenes de compra para un organismo y una fecha."
  },
  "data": {
    "organism_resolution": {
      "selected": {
        "code": "3081",
        "name": "I MUNICIPALIDAD DE ALGARROBO"
      },
      "ambiguous": false,
      "verification_required": false
    },
    "payload": {
      "Cantidad": 1,
      "Ordenes": [
        {
          "Codigo": "3081-123-SE24",
          "Nombre": "Compra de insumos municipales"
        }
      ]
    }
  },
  "detail": "Resolved to a unique public organism."
}
```

Nota: si Mercado Público devuelve varios compradores posibles, el backend no
elige a ciegas. Retorna `blocked_by_organism_ambiguity: true` y la lista de
`candidates`.

### 2. Órdenes de compra por fecha

Pregunta:

```text
Muestra todas las órdenes de compra del 05/02/2024
```

Intent esperado:

```json
{
  "tool": "orders_by_date",
  "parameters": {
    "fecha": "05022024"
  },
  "reasoning": "La pregunta pide órdenes de compra para una fecha sin organismo específico."
}
```

Acción backend:

```text
Consultar ordenesdecompra.json con fecha=05022024.
```

Respuesta resumida:

```json
{
  "intent": {
    "tool": "orders_by_date",
    "parameters": {
      "fecha": "05022024"
    },
    "reasoning": "La pregunta pide órdenes de compra para una fecha sin organismo específico."
  },
  "data": {
    "Cantidad": 2,
    "Ordenes": [
      {
        "Codigo": "123-45-SE24",
        "Nombre": "Servicio de mantención"
      }
    ]
  },
  "detail": null
}
```

### 3. Buscar organismo público

Pregunta:

```text
Verifica qué organismo público corresponde a Municipalidad de Algarrobo
```

Intent esperado:

```json
{
  "tool": "public_organism_lookup",
  "parameters": {
    "organism_name": "Municipalidad de Algarrobo"
  },
  "reasoning": "La pregunta pide resolver un comprador público por nombre."
}
```

Acción backend:

```text
Consultar Empresas/BuscarComprador y resolver coincidencias por nombre.
```

Respuesta resumida:

```json
{
  "intent": {
    "tool": "public_organism_lookup",
    "parameters": {
      "organism_name": "Municipalidad de Algarrobo"
    },
    "reasoning": "La pregunta pide resolver un comprador público por nombre."
  },
  "data": {
    "query": "Municipalidad de Algarrobo",
    "selected": {
      "code": "3081",
      "name": "I MUNICIPALIDAD DE ALGARROBO"
    },
    "ambiguous": false,
    "candidates": [
      {
        "code": "3081",
        "name": "I MUNICIPALIDAD DE ALGARROBO",
        "match_type": "exact"
      }
    ],
    "candidate_count": 1,
    "verification_required": false
  },
  "detail": "Resolved to a unique public organism."
}
```

### 4. Licitación por código

Pregunta:

```text
Busca la licitación 1509-5-L114
```

Intent esperado:

```json
{
  "tool": "tender_by_code",
  "parameters": {
    "codigo": "1509-5-L114"
  },
  "reasoning": "La pregunta entrega un Código de Licitación."
}
```

Acción backend:

```text
Consultar licitaciones.json con codigo=1509-5-L114.
```

Respuesta resumida:

```json
{
  "intent": {
    "tool": "tender_by_code",
    "parameters": {
      "codigo": "1509-5-L114"
    },
    "reasoning": "La pregunta entrega un Código de Licitación."
  },
  "data": {
    "Cantidad": 1,
    "Listado": [
      {
        "CodigoExterno": "1509-5-L114",
        "Nombre": "Adquisición de equipamiento"
      }
    ]
  },
  "detail": null
}
```

### 5. Licitaciones del día actual

Pregunta:

```text
Qué licitaciones hay hoy?
```

Intent esperado:

```json
{
  "tool": "tenders_current_day",
  "parameters": {},
  "reasoning": "La pregunta pide licitaciones del día actual sin fecha explícita."
}
```

Acción backend:

```text
Consultar licitaciones.json sin filtros adicionales.
```

Respuesta resumida:

```json
{
  "intent": {
    "tool": "tenders_current_day",
    "parameters": {},
    "reasoning": "La pregunta pide licitaciones del día actual sin fecha explícita."
  },
  "data": {
    "Cantidad": 2,
    "Listado": [
      {
        "CodigoExterno": "1001-9-LP26",
        "Nombre": "Servicio publicado hoy"
      }
    ]
  },
  "detail": null
}
```

### 6. Licitaciones por fecha

Pregunta:

```text
Dame todas las licitaciones del 05/02/2024
```

Intent esperado:

```json
{
  "tool": "tenders_by_date",
  "parameters": {
    "fecha": "05022024"
  },
  "reasoning": "La pregunta pide licitaciones para una fecha específica."
}
```

Acción backend:

```text
Consultar licitaciones.json con fecha=05022024.
```

Respuesta resumida:

```json
{
  "intent": {
    "tool": "tenders_by_date",
    "parameters": {
      "fecha": "05022024"
    },
    "reasoning": "La pregunta pide licitaciones para una fecha específica."
  },
  "data": {
    "Cantidad": 1,
    "Listado": [
      {
        "CodigoExterno": "2000-10-LE24",
        "Nombre": "Convenio de suministro"
      }
    ]
  },
  "detail": null
}
```

### 7. Licitaciones por estado y fecha

Pregunta:

```text
Dame licitaciones adjudicadas del 05/02/2024
```

Intent esperado:

```json
{
  "tool": "tenders_by_status_and_date",
  "parameters": {
    "fecha": "05022024",
    "estado": "Adjudicada"
  },
  "reasoning": "La pregunta pide licitaciones filtradas por estado y fecha."
}
```

Acción backend:

```text
Normalizar estado Adjudicada a código Mercado Público y consultar licitaciones.json con fecha y estado.
```

Respuesta resumida:

```json
{
  "intent": {
    "tool": "tenders_by_status_and_date",
    "parameters": {
      "fecha": "05022024",
      "estado": "Adjudicada"
    },
    "reasoning": "La pregunta pide licitaciones filtradas por estado y fecha."
  },
  "data": {
    "Cantidad": 1,
    "Listado": [
      {
        "CodigoExterno": "3000-20-LQ24",
        "Estado": "Adjudicada",
        "Nombre": "Servicio adjudicado"
      }
    ]
  },
  "detail": null
}
```

Estados aceptados: `Publicada`, `Cerrada`, `Desierta`, `Adjudicada`,
`Revocada`, `Suspendida`, `Todos` o sus códigos internos.

### 8. Licitaciones por proveedor y fecha

Pregunta:

```text
Busca licitaciones del proveedor 76543210 el 05/02/2024
```

Intent esperado:

```json
{
  "tool": "tenders_by_supplier_and_date",
  "parameters": {
    "fecha": "05022024",
    "codigo_proveedor": "76543210"
  },
  "reasoning": "La pregunta pide licitaciones filtradas por proveedor y fecha."
}
```

Acción backend:

```text
Consultar licitaciones.json con fecha=05022024 y CodigoProveedor=76543210.
```

Respuesta resumida:

```json
{
  "intent": {
    "tool": "tenders_by_supplier_and_date",
    "parameters": {
      "fecha": "05022024",
      "codigo_proveedor": "76543210"
    },
    "reasoning": "La pregunta pide licitaciones filtradas por proveedor y fecha."
  },
  "data": {
    "Cantidad": 1,
    "Listado": [
      {
        "CodigoExterno": "4000-30-LE24",
        "CodigoProveedor": "76543210",
        "Nombre": "Oferta asociada al proveedor"
      }
    ]
  },
  "detail": null
}
```

### 9. Licitaciones por organismo y fecha

Pregunta:

```text
Muestra licitaciones de la Municipalidad de Algarrobo el 05/02/2024
```

Intent esperado:

```json
{
  "tool": "tenders_by_org_and_date",
  "parameters": {
    "organism_name": "Municipalidad de Algarrobo",
    "fecha": "05022024"
  },
  "reasoning": "La pregunta pide licitaciones para un organismo y fecha."
}
```

Acción backend:

```text
Resolver el organismo con BuscarComprador y consultar licitaciones.json con CodigoOrganismo y fecha.
```

Respuesta resumida:

```json
{
  "intent": {
    "tool": "tenders_by_org_and_date",
    "parameters": {
      "organism_name": "Municipalidad de Algarrobo",
      "fecha": "05022024"
    },
    "reasoning": "La pregunta pide licitaciones para un organismo y fecha."
  },
  "data": {
    "organism_resolution": {
      "selected": {
        "code": "3081",
        "name": "I MUNICIPALIDAD DE ALGARROBO"
      },
      "ambiguous": false
    },
    "payload": {
      "Cantidad": 1,
      "Listado": [
        {
          "CodigoExterno": "5000-40-LP24",
          "Nombre": "Licitación municipal"
        }
      ]
    }
  },
  "detail": "Resolved to a unique public organism."
}
```

### 10. Búsqueda semántica por organismo y rango

Pregunta:

```text
Busca sistemas computacionales para Municipalidad de Algarrobo entre enero y marzo 2024
```

Intent esperado:

```json
{
  "tool": "semantic_org_date_range_search",
  "parameters": {
    "organism_name": "Municipalidad de Algarrobo",
    "keywords": ["sistemas computacionales"],
    "start_date": "01012024",
    "end_date": "31032024",
    "include_orders": null,
    "include_tenders": true
  },
  "reasoning": "La pregunta combina organismo, rango de fechas y términos de producto."
}
```

Acción backend:

```text
Expandir el rango de fechas, resolver organismo, consultar licitaciones por día y filtrar registros con keywords semánticas.
```

Respuesta resumida:

```json
{
  "intent": {
    "tool": "semantic_org_date_range_search",
    "parameters": {
      "organism_name": "Municipalidad de Algarrobo",
      "keywords": ["sistemas computacionales"],
      "start_date": "01012024",
      "end_date": "31032024",
      "include_tenders": true
    },
    "reasoning": "La pregunta combina organismo, rango de fechas y términos de producto."
  },
  "data": {
    "detail": "Semantic date-range search completed.",
    "codigo_organismo": "3081",
    "dates": ["01012024", "02012024"],
    "queried_sources": {
      "tenders": true,
      "purchase_orders": false
    },
    "keywords": ["sistemas computacionales"],
    "search_terms": ["sistemas computacionales", "sistemas", "computacionales", "software", "hardware"],
    "raw_record_count": 42,
    "count": 3,
    "columns": ["CodigoExterno", "Nombre", "Descripcion"],
    "records": [
      {
        "CodigoExterno": "6000-50-LE24",
        "Nombre": "Adquisición de software",
        "_source": "tenders",
        "_query_fecha": "15022024"
      }
    ]
  },
  "detail": "Semantic date-range search completed."
}
```

Notas:

- El rango máximo permitido es de 366 días.
- Si `include_orders` y `include_tenders` son `null`, el backend consulta
  licitaciones por defecto.
- Si la pregunta dice "órdenes de compra o licitaciones", ambos flags deben
  quedar en `true`.

### 11. Intent desconocido

Pregunta:

```text
Cuéntame un chiste sobre auditorías
```

Intent esperado:

```json
{
  "tool": "unknown",
  "parameters": {},
  "reasoning": "La solicitud no corresponde a una consulta soportada de Mercado Público."
}
```

Acción backend:

```text
No consultar Mercado Público.
```

Respuesta resumida:

```json
{
  "intent": {
    "tool": "unknown",
    "parameters": {},
    "reasoning": "La solicitud no corresponde a una consulta soportada de Mercado Público."
  },
  "data": null,
  "detail": "Could not map the request to a known audit tool."
}
```
