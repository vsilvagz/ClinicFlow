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
