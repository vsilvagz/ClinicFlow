# Registro de prompts de IA

## \app\backend\domain\usuarios.py -- Protección de atributos

**Prompt:** Protege los atributos de las clases de usuarios considerando su sensibilidad y necesidad de control de acceso.

---

## \app\backend\domain\agenda.py -- Implementación de la agenda médica

**Prompt:** Implementa `agenda.py` para el sistema ClinicFlow. Antes de escribir, lee los archivos `citas.py`, `enums.py`, `errores.py`, `lista_espera.py` y `usuarios.py` del módulo `domain` para entender las clases y errores existentes. Solo modifica `agenda.py`.

El archivo debe contener:

- Una clase `BloqueHorario` que represente una franja horaria semanal recurrente (día de la semana, hora inicio, hora fin), con un método que verifique si un intervalo cae dentro del bloque.
- Una clase `Bloqueo` para bloqueos puntuales de un intervalo específico, sin afectar citas ya agendadas.
- Una clase `Suspension` para suspensiones completas de un período, con método que detecte solapamiento.
- Una clase `Agenda` que gestione la disponibilidad de un médico. Debe:
  - Permitir agregar horarios recurrentes, bloqueos y suspensiones.
  - Al suspender, cancelar automáticamente las citas activas afectadas y retornarlas.
  - Validar al agregar una cita: que caiga en horario definido, que no haya suspensión ni bloqueo activo, que no haya conflicto con otras citas, y que no se supere la capacidad máxima diaria (si está configurada).
  - Exponer un método `esta_disponible(inicio, duracion)` y un método `slots_disponibles(fecha)` que genere automáticamente los slots libres del día.
  - Usar las excepciones `HorarioNoDisponible`, `AgendaSuspendida` y `ConflictoDeAgenda` de `errores.py`.
  - Delegar la validación de solapamiento entre citas al método `validar_no_solapa` de la clase `Cita`.

---

## `app/backend/domain/usuarios.py` — Composición de Agenda en Medico

**Prompt:** Modifica la clase `Medico` en `usuarios.py` para que componga una `Agenda` propia usando el principio de composición. La agenda debe crearse automáticamente al instanciar un `Medico` y ser accesible mediante una propiedad `agenda`. Agrega el import de `Agenda` desde `agenda.py` a nivel de módulo (no dentro del método). Verifica antes de editar que no existe importación circular entre `usuarios.py` y `agenda.py`.

---

## `app/backend/domain/agenda.py` — Eliminación de medico_id

**Prompt:** Refactoriza la clase `Agenda` en `agenda.py` para eliminar el parámetro `medico_id` de su constructor y la propiedad asociada. La agenda ya no necesita conocer el RUN del médico porque pasa a ser un atributo compuesto por `Medico`: el médico es su dueño y provee el contexto. Elimina también el import de `UUID` si queda sin uso tras el cambio.

---

## `app/backend/domain/derivacion.py` — Implementación de derivaciones médicas

**Prompt:** Implementa `derivacion.py` para el sistema ClinicFlow. Antes de escribir, lee los archivos `citas.py`, `enums.py`, `errores.py` y `usuarios.py` del módulo `domain` para entender los patrones existentes y no romper la coherencia del código. Solo modifica `derivacion.py`, `enums.py` y `errores.py` si es necesario.

El archivo debe contener una clase `Derivacion` que modele el proceso de derivación de un paciente hacia otra especialidad o profesional. Debe seguir el mismo patrón que `Cita`: `@dataclass` con factory `crear()` y máquina de estados con un diccionario `_TRANSICIONES`. Los estados posibles son: pendiente, aceptada, rechazada, completada y expirada.

La clase debe:

- Registrar quién emite la derivación (`medico_origen_id`), a qué especialidad se deriva y, opcionalmente, a qué médico destino.
- Tener una fecha de expiración configurable (por defecto 30 días desde la creación).
- Exponer métodos de transición: `aceptar()`, `rechazar()`, `completar(cita_id)` y `expirar()`. El método `aceptar()` debe verificar que la derivación no haya vencido antes de transicionar.
- Exponer reglas de negocio: `esta_vigente()`, `puede_agendar()` (solo si está aceptada y vigente) y `verificar_y_expirar_si_corresponde()` para ser invocado por un servicio de background.
- Al completarse, vincular la derivación a la `Cita` resultante mediante `cita_resultante_id`.
- Agregar a `enums.py` el enum `EstadoDerivacion` y a `errores.py` las excepciones `DerivacionNoEncontrada`, `DerivacionExpirada` y `DerivacionYaUsada`, heredando de `ClinicFlowError`.
- Usar el parámetro `ahora` en los métodos que dependan del tiempo, para facilitar el testing.

---

## `app/backend/domain/usuarios.py` — Atributos y métodos de Medico

**Prompt:** Agrega a la clase `Medico` en `usuarios.py` el atributo `_derivaciones_emitidas: list[Derivacion]` (inicializado como lista vacía en `__init__`) y los métodos `bloquear_horario(inicio, fin, motivo)`, `suspender_agenda(inicio, fin, motivo)`, `registrar_derivacion(derivacion)`, `derivaciones_vigentes()` e `historial_derivaciones()`. Los métodos `bloquear_horario` y `suspender_agenda` deben delegar directamente en `self._agenda.bloquear()` y `self._agenda.suspender()` respectivamente, devolviendo sus resultados. Importa `Bloqueo` y `Suspension` desde `agenda.py`, `Derivacion` desde `derivacion.py` y `datetime` desde la librería estándar. Verifica que no haya imports circulares antes de modificar.

---

## `app/backend/domain/usuarios.py` — Atributos y métodos de Paciente

**Prompt:** Agrega a la clase `Paciente` en `usuarios.py` el atributo `_citas: list[Cita]` (inicializado como lista vacía en `__init__`) y los métodos `registrar_cita(cita)`, `citas_activas()`, `tiene_cita_en_especialidad(especialidad)` e `historial_citas()`. Importa `Cita` desde `citas.py` a nivel de módulo verificando que no haya imports circulares. El método `citas_activas()` debe devolver solo las citas en estado PENDIENTE o CONFIRMADA usando la propiedad `esta_activa` de `Cita`. El método `tiene_cita_en_especialidad()` permite validar si el paciente ya tiene una cita activa en una especialidad, lo cual es necesario para la lógica de lista de espera.

---

## `app/backend/domain/usuarios.py` — Métodos de Recepcionista

**Prompt:** Implementa los métodos de la clase `Recepcionista` en `usuarios.py`: gestionar citas, reagendar pacientes, administrar listas de espera y visualizar agendas clínicas.

Los métodos deben ser:

- `confirmar_cita(cita)`, `cancelar_cita(cita)` y `marcar_no_asistio(cita)`: delegan directamente en los métodos de `Cita`.
- `reagendar_cita(cita, medico, nueva_inicio, duracion_minutos, ahora)`: llama a `cita.reagendar()` para obtener la nueva cita y la registra en `medico.agenda` mediante `agregar_cita()`. Retorna la nueva cita.
- `ver_agenda_medico(medico, fecha)`: devuelve las citas del día desde `medico.agenda.citas_del_dia(fecha)`.
- `slots_disponibles_medico(medico, fecha)`: devuelve los slots libres desde `medico.agenda.slots_disponibles(fecha)`.
- `agregar_a_lista_espera(lista, paciente)` y `extraer_de_lista_espera(lista)`: delegan en los métodos de `Lista_de_Espera`.

---

## `app/backend/domain/especialidades.py` — Catálogo de especialidades médicas

**Prompt:** Crea el archivo `especialidades.py` en el módulo `domain` y mueve la clase `Especialidad` desde `usuarios.py` hacia él. La clase debe implementarse como un `Enum` con un catálogo predefinido de especialidades médicas, donde cada entrada tenga `nombre` y `descripcion` como atributos. Usa una tupla como valor de cada miembro del enum y desempáquetala en `__init__`. Incluye al menos las siguientes especialidades: Medicina General, Cardiología, Neurología, Traumatología, Pediatría, Ginecología, Oftalmología, Dermatología, Psiquiatría, Urología, Gastroenterología y Otorrinolaringología. Actualiza el import en `usuarios.py` para obtener `Especialidad` desde `especialidades.py` y elimínala de `usuarios.py`.

---

## `app/backend/core/config.py` — Configuración centralizada de la aplicación

**Prompt:** Implementa `config.py` en el módulo `core` para centralizar toda la configuración de la aplicación a partir de variables de entorno, usando `pydantic-settings`. Define una clase `Settings(BaseSettings)` con `model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")` para leer el `.env` sin fallar ante variables no usadas. Incluye los atributos, agrupados por sección y con valores por defecto razonables: aplicación (`app_name`, `environment`, `debug`), base de datos (`database_url` apuntando a PostgreSQL vía `postgresql+psycopg2`), seguridad (`secret_key`, `access_token_expire_minutes`), Telegram (`telegram_bot_token`) y LLM (`openai_api_key`, `llm_model`). Los nombres deben coincidir con las variables de `.env.example`. Agrega una propiedad `is_production` que compare `environment` con `"production"`. Expón una función `get_settings()` decorada con `@lru_cache` para construir la configuración una sola vez, y una instancia `settings` lista para importar. Mantén el estilo de comentarios didácticos del resto del proyecto.

---

## `app/backend/core/database.py` — Motor, sesiones y base declarativa

**Prompt:** Implementa `database.py` en el módulo `core` como base técnica de la persistencia, usando SQLAlchemy 2.0 y la configuración de `config.py`. Crea un `engine` con `create_engine(settings.database_url, pool_pre_ping=True, echo=settings.debug)`. Define `SessionLocal` con `sessionmaker(bind=engine, autoflush=False, autocommit=False)`. Define una clase `Base(DeclarativeBase)` de la que heredarán todos los modelos ORM. Implementa una dependencia `get_db()` como generador que entrega una sesión mediante `yield` y la cierra en un bloque `finally`, con tipo de retorno `Iterator[Session]`. Mantén el estilo de comentarios didácticos del resto del proyecto.

---

## `app/backend/models/especialidades.py` y `app/backend/models/usuarios.py` — Modelos ORM de usuarios y especialidades

**Prompt:** Crea los modelos ORM de persistencia (SQLAlchemy 2.0, estilo `Mapped` / `mapped_column`) que son el espejo de las clases de dominio de `domain/usuarios.py` y `domain/especialidades.py`, heredando de la `Base` de `core/database.py`. Usa el sufijo `ORM` en los nombres para distinguirlos del dominio. En `models/especialidades.py` define `EspecialidadORM` (tabla `especialidades`) con `id` autoincremental como PK, `nombre` único no nulo, `descripcion` con default vacío, y una relación uno-a-muchos `medicos` con `back_populates`. En `models/usuarios.py` modela la jerarquía de usuarios con HERENCIA DE TABLA ÚNICA: una clase base `UsuarioORM` (tabla `usuarios`) con `run_usuario` como PK no autoincremental, `nombre`, `correo`, `telefono` (BigInteger) y una columna discriminadora `rol` de tipo `Enum(RolUsuario)`, configurando `__mapper_args__` con `polymorphic_on` y `polymorphic_identity`. Define las subclases `PacienteORM`, `MedicoORM`, `RecepcionistaORM` y `AdministradorORM`, cada una con su `polymorphic_identity` igual al valor de `RolUsuario`. `MedicoORM` debe tener `especialidad_id` como FK nullable a `especialidades.id` y la relación `especialidad` con `back_populates="medicos"`. Evita imports circulares usando `TYPE_CHECKING`. Finalmente, en `models/__init__.py` importa y reexporta todos los modelos para que queden registrados en `Base.metadata`. Mantén el estilo de comentarios didácticos del resto del proyecto.

---

## `app/backend/models/` — Modelos ORM de clínica, agenda, citas, derivación y lista de espera

**Prompt:** Completa la capa de modelos ORM (SQLAlchemy 2.0, estilo `Mapped` / `mapped_column`, sufijo `ORM`) creando el espejo de persistencia de las entidades de dominio restantes, heredando de la `Base` de `core/database.py` y reutilizando los enums del dominio como tipo de las columnas de estado/prioridad. Evita imports circulares con `TYPE_CHECKING` y resuelve las relaciones por nombre de clase/tabla. Crea: (1) `models/clinica.py` con `ClinicaORM` (tabla `clinicas`, PK `rut_empresa` de tipo texto) y dos tablas de asociación muchos-a-muchos `clinica_medicos` y `clinica_especialidades`; relaciones `medicos`, `especialidades` (vía `secondary`) y `recepcionistas` (uno-a-muchos). (2) `models/agenda.py` con `AgendaORM` (uno-a-uno con el médico mediante FK `medico_run` única) y sus tablas hijas `BloqueHorarioORM` (con `Time`), `BloqueoORM` y `SuspensionORM`, todas con FK a `agendas.id` y `cascade="all, delete-orphan"` salvo las citas. (3) `models/citas.py` con `CitaORM` (PK `Uuid`, dos FK a `usuarios` para paciente y médico resueltas con `foreign_keys`, autorreferencias `reagendada_desde_id`/`reagendada_hacia_id`, FK opcional a `agendas.id`, estado `Enum(EstadoCita)`). (4) `models/derivacion.py` con `DerivacionORM` (PK `Uuid`, FKs a `usuarios` y FK opcional a `citas.id`, estado `Enum(EstadoDerivacion)`). (5) `models/lista_espera.py` con `ListaEsperaORM` (FK a especialidad y clínica) y su tabla hija `InscripcionEsperaORM` (paciente, `fecha_inscripcion`, `prioridad` `Enum(PrioridadEspera)`). Agrega en `models/usuarios.py` la relación `agenda` (uno-a-uno) y `clinicas` (muchos-a-muchos) en `MedicoORM`, y la FK `clinica_rut` con su relación `clinica` en `RecepcionistaORM`; añade la relación `clinicas` en `EspecialidadORM`. Finalmente, registra todos los modelos nuevos en `models/__init__.py`. 

---

## `app/backend/schemas/` — Esquemas Pydantic (DTOs) de la API

**Prompt:** Implementa los esquemas Pydantic (Pydantic v2) que definen el contrato de entrada/salida de la API, en el módulo `schemas`, manteniéndolos como una capa separada de los modelos ORM y de las clases de dominio. Antes de escribir, lee los enums de `domain/enums.py` y los modelos ORM correspondientes para que los campos coincidan. Crea: (1) `schemas/especialidades.py` con `EspecialidadCrear` (entrada: `nombre`, `descripcion`) y `EspecialidadLeer` (salida: `id`, `nombre`, `descripcion`) usando `ConfigDict(from_attributes=True)` para construirse desde objetos ORM. (2) `schemas/usuarios.py` con una base privada `_UsuarioBase` (`run_usuario`, `nombre`, `correo` validado como `EmailStr`, `telefono`) y los esquemas de entrada por rol `PacienteCrear`, `MedicoCrear` (añade `especialidad_id`), `RecepcionistaCrear` (añade `clinica_rut`) y `AdministradorCrear`; más los de salida `UsuarioLeer` (incluye `rol` de tipo `RolUsuario`) y `MedicoLeer` (añade `especialidad_id`). (3) `schemas/citas.py` con `CitaCrear` (`paciente_id`, `medico_id`, `inicio`, `duracion_minutos`, `motivo`), `CitaReagendar` (`nueva_inicio`, `duracion_minutos`) y `CitaLeer` (vista completa con `estado` de tipo `EstadoCita`). Usa `Field` con validaciones razonables (longitudes, valores positivos, duración acotada) y reutiliza los enums del dominio como tipos. Mantén el estilo de comentarios didácticos del resto del proyecto.

---

## `app/backend/repositories/` — Repositorios de acceso a datos

**Prompt:** Implementa la capa de repositorios en el módulo `repositories`, que encapsula el acceso a la base de datos detrás de métodos con nombre de negocio para que los servicios no usen SQL ni sesiones directamente. Antes de escribir, lee los modelos ORM correspondientes y `core/database.py`. Crea: (1) `repositories/base.py` con una clase genérica `RepositorioBase` parametrizada por un `TypeVar` acotado a `Base` (`ModeloORM`), que reciba en el constructor la `Session` y la clase del modelo, y exponga las operaciones CRUD comunes `obtener(id)` (vía `db.get`), `listar()` (vía `select`), `agregar(obj)` (con `db.add` + `db.flush`) y `eliminar(obj)`. (2) `repositories/especialidades.py` con `RepositorioEspecialidades` que herede de la base para `EspecialidadORM` y agregue `obtener_por_nombre(nombre)`. (3) `repositories/usuarios.py` con `RepositorioUsuarios` para `UsuarioORM` que aproveche la herencia de tabla única y agregue `obtener_paciente(run)`, `obtener_medico(run)` (pidiendo las subclases concretas para filtrar por rol) y `listar_medicos()`. (4) `repositories/citas.py` con `RepositorioCitas` para `CitaORM` que agregue `listar_de_paciente(paciente_id)` y `listar_activas_de_medico(medico_id)`, esta última filtrando por los `ESTADOS_ACTIVOS` del dominio para soportar la validación de conflictos de agenda. Mantén el estilo de comentarios didácticos del resto del proyecto.

---

## `app/backend/services/` — Servicios (casos de uso)

**Prompt:** Implementa la capa de servicios en el módulo `services`, que orquesta repositorios y reglas de negocio y es lo único con lo que hablará la API (nunca con la base de datos directamente). Cada caso de uso recibe la `Session` y el schema de entrada, valida, persiste con `commit`/`refresh` y devuelve el objeto ORM. Crea: (1) `services/especialidades_service.py` con `crear_especialidad(db, datos)` que rechace nombres duplicados (excepción `EspecialidadYaExiste`) y `listar_especialidades(db)`. (2) `services/usuarios_service.py` con `crear_paciente`, `crear_medico` (validando que la especialidad exista, excepción `EspecialidadNoEncontrada`), `crear_recepcionista` y `crear_administrador`, todos verificando que el RUN esté libre (excepción `UsuarioYaExiste`), más `listar_usuarios`, `listar_medicos` y `obtener_medico` (que lance `MedicoNoEncontrado` del dominio). (3) `services/citas_service.py` como núcleo de las reglas de negocio: en vez de reimplementar la lógica, debe REUTILIZAR la entidad de dominio `Cita` mediante helpers `_a_dominio(orm)` y `_a_orm(cita)` que traduzcan entre ORM y dominio. `crear_cita` valida que existan paciente y médico (excepciones `PacienteNoEncontrado`/`MedicoNoEncontrado`), usa `Cita.crear` para la validación de fecha pasada y el cálculo del fin, y valida solapamientos con `validar_no_solapa` contra las citas activas del médico. Las transiciones `confirmar_cita`, `cancelar_cita`, `completar_cita` y `marcar_no_asistio` deben compartir un helper `_aplicar_transicion(db, cita_id, accion)` que cargue la cita, aplique el método de dominio (dejando que `TransicionEstadoInvalida` aborte sin guardar) y persista el nuevo estado. `reagendar_cita` marca la original como REAGENDADA y crea la cita nueva enlazada validando solapamiento. Incluye `listar_citas_de_paciente`. Mantén el estilo de comentarios didácticos del resto del proyecto.

---

## `app/backend/main.py` y `app/backend/api/routes/health.py` — Punto de entrada y chequeos de salud

**Prompt:** Implementa `api/routes/health.py` con un `APIRouter(prefix="/health")` y dos endpoints: `GET /health` devuelve un dict con `status`, `app` y `environment` leídos de `settings`, sin tocar la base de datos; `GET /health/db` recibe la sesión con `Depends(get_db)`, ejecuta `db.execute(text("SELECT 1"))` y devuelve `{"status": "ok", "database": "reachable"}`.

Implementa `main.py` que ensamble la app: crea `app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)`; el `lifespan` (con `@asynccontextmanager`) llama a `Base.metadata.create_all(bind=engine)` al iniciar e importa el paquete `app.backend.models` para registrar las tablas en `Base.metadata`; monta `StaticFiles` en `/static` y configura `Jinja2Templates`, resolviendo la carpeta `frontend/` con `pathlib.Path(__file__)`; incluye `health.router`; y define `GET /` que renderice `index.html` pasándole `app_name`. Mantén el estilo de comentarios didácticos del resto del proyecto.
