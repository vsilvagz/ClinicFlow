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
