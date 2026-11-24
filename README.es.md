# Terna

[![CI](https://github.com/Arenx3/terna/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Arenx3/terna/actions/workflows/ci.yml)

**De 300 CVs a tu terna, con evidencia.**

Terna es un ATS (sistema de seguimiento de candidatos) multi-empresa construido sobre una idea: cada decisión de contratación debe apoyarse en evidencia visible. Evalúa los CVs requisito por requisito. Los candidatos responden las preguntas de preselección en texto, audio o video, como prefieran. Y ayuda al equipo a armar la *terna*: los tres finalistas que se presentan al hiring manager.

Toda la IA corre en tu propia máquina. Sin API keys, sin cuentas externas, sin costo.

[Read in English](README.md)

> **Estado:** en desarrollo, Fase 1 (cimientos). Las funciones de abajo son el roadmap. Cada una se marca al quedar lista.

## Por qué

- Un reclutador revisa cientos de CVs por vacante, coordina entrevistas por correo y decide con notas sueltas.
- Los ATS con IA dan un "87% de match" sin decir por qué.
- Los candidatos esperan semanas sin respuesta.
- Las entrevistas grabadas en video alejan a mucha gente que no quiere salir en cámara.

## Qué lo hace distinto

| | |
|---|---|
| **Screening explicable** | Cada requisito de la vacante aparece junto al fragmento del CV que lo demuestra, o marcado como "sin evidencia". Ningún score llega sin una razón. La IA sugiere y el reclutador decide. |
| **Preselección asíncrona, como el candidato prefiera** | El reclutador define las preguntas de cada vacante. El candidato responde en el momento, con tiempo de preparación y reintentos, en **texto, audio o video**. El audio y el video se transcriben solos. |
| **Revisión por transcripción** | El evaluador lee las respuestas antes de ver cualquier video. Con el modo ciego activo, se puede evaluar a un candidato sin ver su cara ni oír su voz. |
| **Revisión ciega** | Oculta nombre, foto, edad, género y escuela durante la revisión de CVs para reducir el sesgo. |
| **Búsqueda en las respuestas** | "¿Quién mencionó Kubernetes?" busca en todas las transcripciones y salta al segundo exacto. Los clips se pueden compartir con el hiring manager. |
| **Scorecards calibrados** | Cada entrevistador califica por su cuenta y respalda cada calificación con evidencia escrita. Terna señala a quien califica siempre más duro o más blando que el resto del panel. |
| **La vista Terna** | Los tres finalistas lado a lado, con su evidencia, scorecards y clips, listos para el hiring manager. |
| **Portal del candidato** | Estado de la postulación en tiempo real, autoagenda de entrevistas y un cierre respetuoso para quien no queda. Sin ghosting. |
| **Privacidad desde el diseño** | Registro de consentimiento, retención automática de datos y solicitudes de los titulares: derechos ARCO de la LFPDPPP, más el GDPR. |
| **Bilingüe** | Interfaz completa en español e inglés. El matching también funciona entre idiomas, por ejemplo con una vacante en español y un CV escrito en inglés. |

Terna nunca analiza caras, tono de voz ni expresiones faciales. Solo toma en cuenta lo que dijo el candidato.

## Arquitectura

```
 navegador (React) ──► nginx ──► backend Django (ASGI: REST + WebSockets)
                                   │                  │
                   PostgreSQL + pgvector        Redis (broker, channels, cache)
                   (row-level security)               │
                           ┌──────────────────────────┼──────────────────────┐
                     worker-default              worker-media             worker-ml
                     correo, alertas,            FFmpeg: HLS,             parsing de CV,
                     outbox, retención           thumbnails               embeddings, Whisper
                           └──────────── RustFS (almacenamiento S3) ─────────┘
```

Detalles en [docs/architecture.md](docs/architecture.md) (en inglés).

## Stack

- **Backend:** Django 5.2 LTS, Django REST Framework, Django Channels, Celery
- **Datos:** PostgreSQL 16 con `pgvector` y row-level security, Redis
- **IA local:** `faster-whisper` para transcripción, `sentence-transformers` multilingüe para el matching CV ↔ vacante
- **Multimedia:** FFmpeg (HLS adaptativo), RustFS (almacenamiento compatible con S3)
- **Frontend:** React, TypeScript, Vite, Tailwind CSS, shadcn/ui, i18n (es/en)
- **Calidad:** CI en GitHub Actions, tests de aislamiento entre empresas, evaluación de calidad del matching, tests E2E con Playwright

## Roadmap

- [ ] **Fase 1, Cimientos:** stack Docker sin configuración, CI, multi-empresa con row-level security, autenticación, roles e invitaciones, dirección de diseño
- [ ] **Fase 2, ATS núcleo:** vacantes con requisitos y etapas, página pública de empleo, postulaciones, pipeline kanban en tiempo real, perfil del candidato, correos, auditoría
- [ ] **Fase 3, Screening explicable:** parsing de CV, ocultación de datos personales, matching por requisito con evidencia, correcciones del reclutador, revisión ciega
- [ ] **Fase 4, Preselección asíncrona:** preguntas por vacante respondidas en texto, audio o video, grabador en el navegador, subida resumible, transcripción, búsqueda y clips
- [ ] **Fase 5, Decisión y producto:** agenda de entrevistas, scorecards calibrados, vista Terna, analytics, portal del candidato, solicitudes de privacidad, datos demo

El avance se sigue en los [milestones](https://github.com/Arenx3/terna/milestones).

## Ejecutar

```bash
git clone https://github.com/Arenx3/terna.git
cd terna
docker compose up -d --build --wait
```

No necesita cuentas, API keys ni `.env`. Los secretos se generan en el primer arranque y se guardan en el volumen `terna_secrets`. Para cambiar un valor por defecto (puertos, proveedor de correo o de almacenamiento), copia `.env.example` a `.env`.

**Requisitos:** Docker con Compose v2.24 o posterior. Asigna a Docker al menos 8 GB de memoria: los modelos de IA local de fases posteriores los necesitan.

| URL | Qué es |
|---|---|
| http://localhost:8080 | Terna |
| http://localhost:8080/api/docs/ | Referencia de la API (OpenAPI) |
| http://localhost:8080/api/health/ | Salud de la base de datos, Redis y almacenamiento |
| http://localhost:8025 | Mailpit, la bandeja que atrapa todos los correos |
| http://localhost:9001/rustfs/console/ | Consola de almacenamiento (RustFS) |

Todos los puertos se publican solo en `127.0.0.1`. Credenciales de la consola de almacenamiento:

```bash
docker compose exec backend sh -c 'cat /run/secrets/storage_access_key; echo; cat /run/secrets/storage_secret_key; echo'
```

Detén todo con `docker compose down`. Agrega `-v` para borrar también los datos y los secretos generados.

El stack ya corre; las funciones del producto llegan fase por fase.

## Desarrollo

Los tests y el lint corren en contenedores, así que solo necesitas Docker:

```bash
docker compose --profile test run --rm tests                  # tests del backend
docker compose --profile test run --rm --no-deps tests \
  sh -c 'ruff check . && ruff format --check .'               # lint y formato
python scripts/smoke_test.py                                  # revisión de punta a punta del stack corriendo
```

La CI corre las mismas revisiones en cada pull request (lint, tests del backend, frontend y un smoke test del stack completo), y todas deben pasar antes de fusionar a `main`.

El frontend corre en tu máquina con recarga en caliente, contra el stack levantado (Node 24):

```bash
cd frontend
npm ci
npm run dev          # http://localhost:5173, redirige /api al stack en :8080
npm run lint && npm run typecheck && npm run build
npm run api:types    # regenera el cliente tipado de la API tras cambios en el backend
```

Toda cadena visible vive en `frontend/src/i18n/locales/` (inglés y español). El lint falla si un componente tiene texto fijo y la verificación de tipos falla si falta una clave en cualquiera de los dos idiomas.

Instala los hooks de Git una vez con `pre-commit install` (vía `pipx`, `uv tool` o `pip`). Corren Ruff, mantienen `uv.lock` sincronizado y detectan errores comunes antes de cada commit.

## Documentación

- [Visión del producto](docs/vision.md): el problema, los principios, los usuarios y el recorrido completo de contratación
- [Arquitectura](docs/architecture.md): servicios, flujos de datos, multi-empresa, IA local y modelo de datos
- [Registros de decisiones de arquitectura](docs/adr/)

La documentación técnica está en inglés.

## El nombre

En el reclutamiento en México, la *terna* son los tres finalistas que se presentan al hiring manager. Armarla es para lo que sirve esta herramienta.
