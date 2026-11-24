# TalentForge

ATS (Applicant Tracking System) multi-empresa con **screening explicable** y **entrevistas en video asíncronas**. Toda la inteligencia corre en tu máquina: sin API keys, sin cuentas externas, sin costo.

> **Estado:** en construcción. Fase 1: infraestructura base.

## El problema

Un reclutador revisa cientos de CVs por vacante, coordina entrevistas por correo y decide con notas sueltas. Los ATS con IA dan un "score de 87%" sin decir por qué, y el candidato se queda semanas sin respuesta.

## Qué hace distinto

| | |
|---|---|
| **Screening explicable** | Cada requisito de la vacante aparece junto al fragmento del CV que lo demuestra, o marcado como "sin evidencia". Ningún score sin justificación. La IA sugiere y el reclutador decide. |
| **Entrevistas en video asíncronas** | El candidato graba sus respuestas desde el navegador, con tiempo de preparación y reintentos limitados. Streaming adaptativo (HLS) y transcripción automática sincronizada: clic en una frase y el video salta a ese momento. |
| **Búsqueda en entrevistas** | "¿Quién mencionó Kubernetes?" busca en todas las transcripciones y abre el clip exacto. |
| **Revisión ciega** | Oculta nombre, foto, edad, género y escuela en la primera etapa para reducir sesgo. Se activa por vacante y queda en la bitácora de auditoría. |
| **Scorecards con calibración** | Cada entrevistador evalúa sin ver la opinión de los demás. El sistema detecta quién califica sistemáticamente más duro o más blando. |
| **Analytics del funnel** | Time-to-hire, conversión por etapa, efectividad por fuente y alertas de candidatos sin respuesta. |
| **Portal del candidato** | El candidato ve el estado de su postulación en tiempo real y agenda su entrevista en los horarios disponibles. |
| **Colaboración en vivo** | Kanban con drag-and-drop sincronizado por WebSockets, presencia, @menciones y paleta de comandos (⌘K). |
| **Privacidad desde el diseño** | Consentimiento, retención con purga automática y derechos ARCO (acceso, rectificación, cancelación, oposición) según la LFPDPPP. |

## Arquitectura

```
                       ┌──────────────┐
   navegador ────────► │    nginx     │
   (React + TS)        └──────┬───────┘
              REST / WebSocket │
                       ┌──────▼───────┐        ┌──────────────────────┐
                       │   backend    │◄──────►│ PostgreSQL + pgvector│
                       │ Django + DRF │        │ Row-Level Security   │
                       │  + Channels  │        └──────────────────────┘
                       └──┬────────┬──┘
                   encola │        │ boto3
                       ┌──▼───┐  ┌─▼──────────┐
                       │Redis │  │ RustFS (S3)│
                       └──┬───┘  └─▲──────────┘
             ┌────────────┼────────┼───────────┐
        ┌────▼────┐  ┌────▼───────┴┐  ┌────────▼────────┐
        │ default │  │    media    │  │       ml        │
        │ correo, │  │ FFmpeg: HLS │  │ faster-whisper, │
        │ alertas │  │ thumbnails  │  │ embeddings      │
        └─────────┘  └─────────────┘  └─────────────────┘
```

## Stack

- **Backend:** Django 5.2 LTS, Django REST Framework, Django Channels, Celery
- **Datos:** PostgreSQL 16 con `pgvector`, Redis
- **IA local:** `faster-whisper` (transcripción), `sentence-transformers` multilingüe (matching CV ↔ vacante)
- **Multimedia:** FFmpeg (HLS adaptativo), RustFS (almacenamiento compatible con S3)
- **Frontend:** React, TypeScript, Vite, Tailwind CSS, shadcn/ui
- **Calidad:** CI en GitHub Actions, tests de aislamiento entre empresas, E2E con Playwright

## Roadmap

- [ ] **Fase 1. Infraestructura:** stack Docker completo, CI, multi-tenant con RLS y roles
- [ ] **Fase 2. ATS núcleo:** vacantes, página pública de empleo, postulaciones, pipeline kanban, scorecards
- [ ] **Fase 3. Inteligencia:** parsing de CV, screening explicable, entrevistas en video, transcripción y búsqueda
- [ ] **Fase 4. Producto:** analytics, portal del candidato, revisión ciega, privacidad y datos demo

## Ejecutar

Con Docker instalado, un solo comando y nada que configurar:

```bash
docker compose up -d --build
```

*(Disponible al cerrar la Fase 1.)*
