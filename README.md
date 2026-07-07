# ClinicFlow

Plataforma web de gestión clínica conversacional. Administra citas médicas, agendas, listas de espera y derivaciones de una clínica, e incluye un **asistente de IA por Telegram** con el que los pacientes agendan, cancelan, reagendan y consultan sus horas escribiendo en lenguaje natural.

🌐 **Aplicación:** <https://clinic-flow.up.railway.app/>
🤖 **Bot de Telegram:** [@ClinicFlowPacientes_bot](https://t.me/ClinicFlowPacientes_bot)

## Funcionalidades

- **Citas médicas**: creación, confirmación, cancelación, reagendamiento y registro de asistencia, con validación de disponibilidad y prevención de conflictos de agenda. Cada cita sigue un ciclo de vida con estados: pendiente, confirmada, cancelada, reagendada, completada y no asistió.
- **Agendas configurables**: horarios de atención por día de la semana, bloqueos de horarios puntuales y suspensiones de agenda completas, que cancelan las citas afectadas y notifican a los pacientes.
- **Lista de espera** por especialidad: inscripción con priorización y asignación de cupos que crea la cita automáticamente cuando se libera una hora.
- **Derivaciones**: un médico deriva a un paciente a otra especialidad; el paciente recibe el mensaje y puede tomar la hora sugerida directamente al reservar.
- **Asistente conversacional**: interpreta la solicitud del paciente con un modelo de lenguaje y la ejecuta a través de los servicios del backend. Disponible en la web (`/asistente`) y por Telegram, con historial de conversaciones.
- **Usuarios y roles**: administradores, recepcionistas, médicos y pacientes, cada uno con un portal con sus propias herramientas. Autenticación por RUT y contraseña, con JWT en cookie HttpOnly.
- **Dashboard**: citas del día, cancelaciones, pacientes en espera, métricas e historial de conversaciones.

El modelo de lenguaje solo traduce cada mensaje a una intención estructurada (acción + parámetros); las validaciones y reglas de negocio se ejecutan siempre en el backend, por lo que el sistema se mantiene consistente aunque el modelo se equivoque.

## Stack

| Componente | Tecnología |
|---|---|
| Backend | Python 3.11, FastAPI |
| Persistencia | PostgreSQL 16, SQLAlchemy 2 |
| Frontend | Plantillas Jinja2 renderizadas por el servidor |
| Bot | python-telegram-bot (polling) |
| LLM | Cualquier proveedor compatible con la API de OpenAI (por defecto Groq, `llama-3.3-70b-versatile`) |
| Testing | pytest |
| Despliegue | Docker / Docker Compose, Railway |

## Arquitectura

El backend está organizado en capas con responsabilidades separadas:

```
app/
├── backend/
│   ├── domain/         # Entidades y reglas de negocio puras (sin BD ni web)
│   ├── models/         # Modelos ORM (SQLAlchemy) — persistencia
│   ├── schemas/        # Esquemas Pydantic — contratos de entrada/salida
│   ├── repositories/   # Acceso a datos (patrón repositorio)
│   ├── services/       # Casos de uso: orquestan dominio + repositorios
│   ├── api/routes/     # Endpoints HTTP y páginas web (FastAPI)
│   ├── ai/             # Cliente LLM, intenciones estructuradas y despachador
│   ├── bot/            # Bot de Telegram (mismo despachador que la web)
│   └── core/           # Configuración, BD, seguridad, seed de datos demo
└── frontend/
    ├── templates/      # Vistas Jinja2
    └── static/         # Estilos
```

- El **dominio** contiene las reglas del negocio (estados de una cita, consistencia de horarios, priorización de la espera) sin dependencias de base de datos ni de la web.
- Los **servicios** implementan los casos de uso (crear cita, suspender agenda, asignar cupo…): validan contra el dominio y persisten a través de los repositorios. La web, el bot y el seed reutilizan los mismos servicios.
- El **asistente** funciona en dos pasos: `ai/cliente.py` pide al LLM una salida estructurada (`IntencionAsistente`) y `ai/despachador.py` la convierte en llamadas a los servicios. La página `/asistente` y el bot de Telegram comparten este flujo.

## Ejecución con Docker (recomendado)

Requisitos: Docker y Docker Compose.

1. Copiar la plantilla de variables de entorno y completar los valores:

   ```bash
   cp .env.example .env
   ```

   | Variable | Descripción |
   |---|---|
   | `SECRET_KEY` | Clave para firmar los tokens de sesión |
   | `TELEGRAM_BOT_TOKEN` | Token del bot (opcional; sin él la web funciona igual) |
   | `LLM_API_KEY` | Clave del proveedor LLM (gratis en [console.groq.com](https://console.groq.com)) |

2. Levantar todo (API + base de datos):

   ```bash
   docker compose up --build
   ```

3. Abrir la aplicación:

   - Interfaz web: <http://localhost:8000>
   - Documentación de la API: <http://localhost:8000/docs>

Al primer arranque se crean las tablas y se **siembran datos de demostración** (especialidades, médicos con agenda de lunes a viernes, pacientes, citas y listas de espera), por lo que el sistema queda usable de inmediato. El seed es idempotente y se puede desactivar con `SEED_DEMO=false`.

### Usuarios de demostración

Todos con contraseña `demo1234`; el inicio de sesión es con RUT.

| Rol | RUT | Nombre |
|---|---|---|
| Administrador | 10000000 | Administrador |
| Recepcionista | 12000001 | Lucía Ramírez |
| Médico (Cardiología) | 11000001 | Ana Rojas |
| Paciente | 44444444 | Pedro Soto |

## Uso del bot de Telegram

1. Abrir [@ClinicFlowPacientes_bot](https://t.me/ClinicFlowPacientes_bot) y enviar `/start`.
2. Vincular la cuenta de paciente al chat:

   ```
   /vincular 44444444 demo1234
   ```

3. Escribir en lenguaje natural, por ejemplo:

   - «Agenda una hora de cardiología para mañana a las 9»
   - «¿Qué horas de pediatría hay el viernes?»
   - «Reagenda mi cita al martes a las 15»
   - «Cancela mi hora de cardiología»
   - «Inscríbeme en la lista de espera de dermatología»
   - «¿Cuáles son mis próximas citas?»

Otros comandos: `/ayuda` muestra la ayuda y `/salir` desvincula la cuenta del chat.

## Ejecución local sin Docker

Requisitos: Python 3.11+ y una instancia de PostgreSQL accesible.

```bash
pip install -r requirements.txt
# En .env, apuntar DATABASE_URL a tu PostgreSQL local, por ejemplo:
# DATABASE_URL=postgresql+psycopg2://clinicflow:clinicflow@localhost:5432/clinicflow
uvicorn app.backend.main:app --reload
```

## Tests

```bash
pytest
```

La suite cubre las reglas de negocio del dominio (conflictos de agenda, cancelaciones inválidas, consistencia de horarios, priorización de la lista de espera), el despachador del asistente y los flujos web principales.

## Despliegue en la nube

La aplicación está desplegada en **Railway**: <https://clinic-flow.up.railway.app/> (con los mismos usuarios de demostración de la tabla anterior).

La imagen Docker respeta la variable `PORT` que inyectan plataformas como Railway o Render: basta apuntar el servicio al `Dockerfile`, aprovisionar un PostgreSQL administrado y definir las mismas variables del `.env` (con la `DATABASE_URL` del servicio y `SEED_DEMO=true` para poblar la demo).
