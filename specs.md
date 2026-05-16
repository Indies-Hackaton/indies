# Indies Product Agent Specs

Este documento describe los agentes del producto, sus poderes y ejemplos de uso del flujo conversacional persistente.

## Contrato principal

Todas las consultas conversacionales entran por:

```http
POST /api/v1/chat/messages
Content-Type: application/json
```

Request:

```json
{
  "conversation_id": null,
  "message": "Busca sistemas computacionales para la Municipalidad de Algarrobo entre enero y marzo 2024"
}
```

Response resumida:

```json
{
  "conversation": {
    "id": "uuid",
    "title": "Sistemas computacionales en Algarrobo"
  },
  "user_message": {
    "id": "uuid",
    "role": "user",
    "content": "Busca sistemas computacionales..."
  },
  "assistant_message": {
    "id": "uuid",
    "role": "assistant",
    "content": "Encontré 3 registros relevantes...",
    "linked_invocation_ids": ["planner-uuid", "chat-uuid"],
    "linked_tool_run_ids": ["toolrun-uuid"]
  },
  "planner": {
    "invocation_id": "planner-uuid",
    "plan": {
      "tasks": []
    }
  },
  "tool_runs": [],
  "total_records": 0
}
```

Si `conversation_id` es `null`, el backend crea una conversación nueva y genera un título desde el primer mensaje. Si viene un UUID existente, el backend usa el historial reciente como contexto.

## Arquitectura de agentes

| Agente | Poder | Guarda trazabilidad |
|---|---|---|
| Usuario/API client | Envía mensajes naturales por `curl` u otro cliente HTTP y conserva el UUID devuelto. | No, solo muestra lo recibido. |
| Chat Orchestrator (`ChatService`) | Crea conversaciones, mensajes, invocaciones LLM y tool runs. | Sí: `conversations`, `messages`, `llm_invocations`, `tool_runs`. |
| MiniMax Chat Model | Genera título y respuesta final en lenguaje natural. | Sí: `title_generation` y `chat_response`. |
| MiniMax Planner Model | Convierte el mensaje + contexto en tareas API estructuradas. | Sí: `planner`. |
| Executor | Ejecuta llamadas reales en paralelo. | Sí: una fila `tool_runs` por tarea. |
| Mercado Público Data Agent | Consulta compras, licitaciones y organismos. | Queda vinculado al `tool_run`. |
| Senado Data Agent | Consulta personal de apoyo y remuneraciones del Senado. | Queda vinculado al `tool_run`. |

## Poderes del Planner/API agent

| Tool | Qué hace | Parámetros |
|---|---|---|
| `senado_support_staff` | Personal de apoyo del Senado. | `year`, `month_es`, opcional `senator_name`, `staff_name`. |
| `mp_orders_by_org_and_date` | Órdenes por organismo y fecha. | `fecha` (`ddmmyyyy`) + `codigoorg` u `organism_name`. |
| `mp_orders_by_date` | Órdenes por fecha. | `fecha`. |
| `mp_tender_by_codigo` | Licitación por código. | `codigo`. |
| `mp_tenders_today` | Licitaciones del día actual. | Sin parámetros. |
| `mp_tenders_by_date` | Licitaciones por fecha. | `fecha`. |
| `mp_tenders_by_status` | Licitaciones por estado y fecha. | `fecha`, `estado`. |
| `mp_tenders_by_supplier` | Licitaciones por proveedor y fecha. | `fecha`, `CodigoProveedor`. |
| `mp_tenders_by_org` | Licitaciones por organismo y fecha. | `fecha` + `codigo_organismo` u `organism_name`. |
| `mp_search_buyers` | Lista compradores públicos. | Sin parámetros. |
| `mp_resolve_organism` | Resuelve nombre de organismo a código/candidatos. | `organism_name`. |
| `mp_semantic_range` | Busca por organismo, rango y keywords en licitaciones/órdenes. | `organism_name`, `start_date`, `end_date`, `keywords`, flags opcionales. |

Fechas: el Planner debe entregar `fecha`, `start_date` y `end_date` como `ddmmyyyy`. Ejemplo: `2024-02-05` → `05022024`.

El filtro semántico normaliza acentos y expande variantes comunes en español.
Por ejemplo, `sistemas informáticos` también busca `sistema informatico`, lo
que permite encontrar nombres como `SISTEMA INFORMÁTICO GESTIÓN DE RECURSOS`.

Las tools de fecha única por organismo (`mp_orders_by_org_and_date` y
`mp_tenders_by_org`) aceptan `organism_name`; el Executor resuelve el código
antes de consultar Mercado Público. No deben degradar a búsquedas globales por
fecha cuando el usuario nombra una institución.

## Ejemplos de uso

### Búsqueda semántica Mercado Público

Usuario:

```text
Busca sistemas computacionales para la Municipalidad de Algarrobo entre enero y marzo 2024
```

Plan esperado:

```json
{
  "tasks": [
    {
      "id": "t1",
      "tool": "mp_semantic_range",
      "description": "Buscar licitaciones de sistemas computacionales para Municipalidad de Algarrobo",
      "parameters": {
        "organism_name": "Municipalidad de Algarrobo",
        "start_date": "01012024",
        "end_date": "31032024",
        "keywords": ["sistemas computacionales"],
        "include_tenders": true,
        "include_orders": false
      }
    }
  ],
  "reasoning": "La pregunta combina institución, rango de fechas y términos de producto."
}
```

Respuesta natural esperada:

```text
Encontré 3 registros relacionados con sistemas computacionales para la Municipalidad de Algarrobo en el rango solicitado. La búsqueda consultó licitaciones por fecha y filtró por términos como sistemas, computacionales, software y hardware. Los resultados quedan vinculados a esta respuesta para revisar el detalle de cada llamada.
```

Vinculación guardada:

```json
{
  "assistant_message": {
    "linked_invocation_ids": ["planner-uuid", "chat-uuid"],
    "linked_tool_run_ids": ["toolrun-uuid"]
  }
}
```

### Personal de apoyo del Senado

Usuario:

```text
Analiza el personal de apoyo del senador Araya en marzo 2026
```

Plan esperado:

```json
{
  "tasks": [
    {
      "id": "t1",
      "tool": "senado_support_staff",
      "description": "Consultar personal de apoyo del senador Araya en marzo 2026",
      "parameters": {
        "year": 2026,
        "month_es": "MARZO",
        "senator_name": "Araya"
      }
    }
  ],
  "reasoning": "La pregunta pide datos de personal de apoyo del Senado."
}
```

Respuesta natural esperada:

```text
Encontré registros de personal de apoyo asociados al senador Araya para marzo de 2026. La respuesta resume los nombres, roles y montos disponibles, y la llamada al portal de transparencia del Senado queda enlazada al mensaje.
```

### Resolver organismo público

Usuario:

```text
Verifica qué organismo público corresponde a Municipalidad de Algarrobo
```

Plan esperado:

```json
{
  "tasks": [
    {
      "id": "t1",
      "tool": "mp_resolve_organism",
      "description": "Resolver el comprador público por nombre",
      "parameters": {
        "organism_name": "Municipalidad de Algarrobo"
      }
    }
  ],
  "reasoning": "La pregunta pide verificar un organismo por nombre."
}
```

Respuesta natural esperada:

```text
Encontré el organismo público más probable y mantuve candidatos similares para verificación. Si Mercado Público devuelve varias municipalidades o corporaciones relacionadas, la respuesta indica la ambigüedad en vez de escoger a ciegas.
```

## Persistencia

Cada turno guarda:

| Registro | Contenido |
|---|---|
| `messages` user | Texto original del usuario. |
| `llm_invocations` planner | Prompt, modelo, JSON del plan o error. |
| `tool_runs` | Tool, parámetros, resultado `TaskResult`, status y conteo. |
| `llm_invocations` chat_response | Prompt, modelo y respuesta natural final. |
| `messages` assistant | Texto final mostrado al usuario y links a invocaciones/tool runs. |

El título se genera una sola vez al crear la conversación. Si falla, se usa un título corto derivado del primer mensaje.

La base SQLite local recomendada es `sqlite+aiosqlite:///./data/indies.db`.
El backend crea el directorio `data/` al arrancar.
