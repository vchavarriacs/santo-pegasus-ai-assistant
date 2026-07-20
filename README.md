# Santo Pegasus AI Assistant

Agente de inteligencia artificial con arquitectura RAG (Retrieval-Augmented Generation) para responder preguntas sobre la base de conocimiento interna de Santo Pegasus Soluciones.

Desarrollado como entrega del **Challenge AI for Tech — Alura**.

**🚀 Demo desplegada en OCI:** https://n8n-challenge.ren-lab-content.uk (chat público, requiere las credenciales compartidas en la entrega)

---

## Descripción

El agente permite a desarrolladores y nuevos integrantes de Santo Pegasus consultar en lenguaje natural la documentación interna de la empresa: manual de onboarding, guías de ingeniería, protocolo de incidentes y arquitectura de microservicios.

## Arquitectura

```
Usuario (chat) → n8n Chat Trigger
                     ↓
        Embedding de la consulta (Cohere)
                     ↓
          Qdrant Vector Store (top-4 chunks)
                     ↓
      AI Agent (Gemini + contexto recuperado)
                     ↓
              Respuesta fundamentada
```

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| Orquestación RAG | n8n (AI Agent + LangChain nodes) |
| Vector Store | Qdrant |
| Embeddings | Cohere `embed-multilingual-v3.0` (1024 dims) |
| LLM | Google Gemini `gemini-2.5-flash-lite` |
| Infra | OCI VM ARM Ampere (Always Free) |
| Tunneling | Cloudflare Tunnel |
| Contenedores | Docker Compose |

> **Nota:** los parámetros del pipeline RAG (chunk size 512, overlap 50, K=4) siguen los estándares internos definidos en la propia Guía de Ingeniería Back-end de Santo Pegasus.

## Base de conocimiento

Los documentos de Santo Pegasus indexados son:

- `Manual de Onboarding para Nuevos Desarrolladores.pdf`
- `Guia Oficial de Ingenieria Back-end.pdf`
- `Guia Oficial de Ingenieria Front-end.pdf`
- `Protocolo de respuestas a incidentes y post-mortems.pdf`
- `Arquitectura de Microservicios y Mapa de Dominios.pdf`

## Instrucciones para ejecutar

### Requisitos previos
- Docker y Docker Compose instalados
- Clave de API de Cohere (gratuita — para embeddings): https://dashboard.cohere.com/api-keys
- Clave de API de Google Gemini (gratuita — para el LLM): https://aistudio.google.com/app/apikey

### 1. Clonar el repositorio
```bash
git clone https://github.com/vchavarriacs/santo-pegasus-ai-assistant.git
cd santo-pegasus-ai-assistant
```

### 2. Configurar variables de entorno
```bash
cp .env.example .env
# Editar .env con tus credenciales
```

### 3. Levantar los servicios
```bash
docker compose up -d
```

### 4. Indexar los documentos
```bash
pip install pdfplumber requests
python scripts/ingest.py
```

### 5. Importar el workflow en n8n
- Acceder a `http://localhost:5678`
- Importar `n8n/workflow.json` (menú **⋯** → *Import from File*)
- Asignar credenciales en los nodos: **Google Gemini Chat Model** (API key de Gemini), **Cohere Embeddings** (API key de Cohere) y **Qdrant Vector Store** (URL: `http://qdrant:6333`, sin API key)
- Activar el workflow

### 6. Probar el agente
Acceder al chat en la URL generada por n8n y hacer preguntas sobre la documentación de Santo Pegasus.

## Ejemplos de preguntas

- *"¿Cuántas aprobaciones necesita un Pull Request para ser mergeado?"*
- *"¿Cuál es el chunk size estándar para pipelines RAG en Santo Pegasus?"*
- *"¿Qué hace el ai-assistant-service y qué base de datos vectorial usa?"*
- *"¿Cómo se calcula el Error Budget del servicio Agendio?"*
- *"¿Cuál es el plan 30/60/90 días para nuevos desarrolladores?"*
- *"¿Qué severidad tiene un incidente que afecta a todos los usuarios?"*

## Funcionalidades avanzadas (expansión post-entrega base)

Sobre la base funcional del challenge, se agregaron tres mejoras opcionales. Los workflows de esta expansión están en:

- [`n8n/workflow-expansion.json`](n8n/workflow-expansion.json) — agente principal, usa el sub-workflow de reranking como herramienta
- [`n8n/subworkflow-rerank.json`](n8n/subworkflow-rerank.json) — retrieval ampliado (top-20) + Cohere Rerank (top-4)
- [`n8n/workflow-feedback.json`](n8n/workflow-feedback.json) — endpoint que registra el feedback 👍/👎

(El [`n8n/workflow.json`](n8n/workflow.json) original, con retrieval directo K=4, se mantiene como la versión base del challenge.)

### 1. Reranking

En lugar de devolver directamente los top-4 chunks de la búsqueda vectorial, el agente usa un sub-workflow (`RAG Retrieval con Reranking`, invocado como *Call n8n Sub-Workflow Tool*) que:

1. Genera el embedding de la pregunta (Cohere `embed-multilingual-v3.0`)
2. Recupera los **20** candidatos más cercanos en Qdrant (búsqueda amplia)
3. Reordena esos 20 con **Cohere Rerank** (`rerank-v3.5`), comparando la pregunta completa contra cada candidato
4. Devuelve al agente solo los **4** fragmentos más relevantes tras el reranking

Esto mejora la precisión de la recuperación frente al top-4 directo: en las pruebas, permitió que el agente combinara contexto de varias fuentes relevantes (p. ej. Back-end + Front-end + Onboarding) en una sola respuesta, en vez de quedarse solo con el primer documento que aparecía en la búsqueda vectorial simple.

### 2. Feedback del usuario

La interfaz de chat (`web/index.html`) muestra botones **👍 Útil / 👎 No útil** bajo cada respuesta. Al hacer clic, se envía `{sessionId, question, answer, rating}` a un workflow dedicado (`Santo Pegasus Feedback Endpoint`) que lo guarda como punto en una colección de Qdrant (`santo_pegasus_feedback`), permitiendo auditar qué respuestas fueron útiles.

Consultar el feedback almacenado:
```bash
curl -s -X POST http://localhost:6333/collections/santo_pegasus_feedback/points/scroll \
  -H 'Content-Type: application/json' -d '{"limit": 50, "with_payload": true}'
```

### 3. Interfaz de chat propia

`web/index.html` es una página estática (sin frameworks ni build step) que consume directamente los webhooks públicos de n8n:
- Indica explícitamente que se trata de un agente de IA, no una persona
- Mantiene historial de conversación durante la sesión
- Muestra los botones de feedback descritos arriba

Para usarla localmente:
```bash
cd web
python -m http.server 8765
# abrir http://localhost:8765
```
Antes de desplegarla, edita las constantes `CHAT_WEBHOOK_URL` y `FEEDBACK_WEBHOOK_URL` al inicio del `<script>` con las URLs de tu propia instancia de n8n.

## Deploy en OCI

Desplegado en una VM **Always Free** de Oracle Cloud Infrastructure (Oracle Linux 9, ARM Ampere, región Mexico Central - Queretaro), con n8n y Qdrant en Docker Compose y acceso público vía Cloudflare Tunnel (como servicio systemd, persistente entre reinicios).

Ver [`oci/setup.sh`](oci/setup.sh) para el script de provisioning completo.

### Notas sobre disponibilidad de modelos gratuitos

Los modelos gratuitos de LLM/embeddings cambian de disponibilidad según la cuenta y la fecha. Antes de fijar un modelo en el workflow, verifica cuáles responden con tu propia API key:

```bash
# Modelos de Gemini disponibles para tu key
curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=TU_KEY" | grep '"name"'

# Prueba directa de un modelo específico
curl -s "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key=TU_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"contents":[{"parts":[{"text":"di hola"}]}]}'
```

En este proyecto, `gemini-2.5-flash` y toda la familia `gemini-2.0-*` devolvieron error 404/429 ("no longer available to new users" / cuota 0) con la API key usada en producción, mientras que `gemini-2.5-flash-lite` funcionó sin problema. Del lado de Cohere, el nodo de embeddings puede caer por defecto en `embed-english-v2.0` (retirado) si el campo Model no se fija explícitamente — siempre confirma que sea `embed-multilingual-v3.0`, el mismo usado en `scripts/ingest.py`.

**Importante:** el free tier de Gemini limita `gemini-2.5-flash-lite` a solo **20 solicitudes por día** por proyecto (no por minuto — el mensaje de error de Google es engañoso al respecto). Cada modelo tiene su propia cuota independiente, así que si la agotas probando, cambiar a otro modelo (`gemini-flash-latest`, `gemini-3.5-flash`, etc.) da acceso a una cuota fresca sin esperar. Para uso más intensivo, considera Cohere (`command-a-03-2025`) como chat model alternativo — en las pruebas resultó más tolerante a ráfagas de solicitudes.

---

*Challenge AI for Tech — Alura | Junio 2026*
