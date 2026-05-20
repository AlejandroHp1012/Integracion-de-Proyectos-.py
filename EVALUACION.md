# EVALUACIÓN FINAL — Programación II

**Proyecto:** Integración de Proyectos — Misión Alpha-001 (Centro de Control de Cohete)
**Repositorio:** `https://github.com/AlejandroHp1012/Integracion-de-Proyectos-.py`
**Fecha de evaluación original:** 2026-05-18 (commit `ba9cf07`)
**Fecha de re-evaluación:** 2026-05-19 (commits `f7b9f07` Despegue, `e100209` Despliegue)
**Evaluador:** Docente cátedra Prog. II

> **Nota sobre re-entregas:** Se concedieron 2 días para revisar la evaluación y corregir hallazgos. Los **Equipos 1 (Despegue)** y **2 (Despliegue)** entregaron nuevas versiones. Los equipos 3 y 4 mantienen sus notas originales. Las secciones reflejan la nota oficial vigente; la trayectoria queda registrada en el `git log` del repositorio.

---

## Metodología

### Criterios calificados (10 pts cada uno, total 100)

| # | Criterio | Qué se evalúa |
|---|---|---|
| 1 | Repositorio Código | Está en Git, commits propios, historial limpio |
| 2 | Uso de Librerías | Pertinencia, imports limpios, no librerías obsoletas |
| 3 | UI/UX (Pruebas) | La UI corre, se renderiza correctamente, no crashea |
| 4 | Uso correcto de controles | Botones, entries, canvas, treeview, sliders usados con propósito |
| 5 | Cajas de diálogo | `messagebox` (info, warning, error, askyesno) usados adecuadamente |
| 6 | Eventos y propiedades formulario | `after`, `bind`, callbacks, state changes |
| 7 | Estructura de datos (JSON) | Esquemas claros, save/load, validación |
| 8 | Reportes | Logs, exportación CSV/TXT, historial visible |
| 9 | Control y acceso a datos (DB) | SQLite u otra persistencia con queries reales |
| 10 | Integración con ESP32-S3 | Comunicación REAL con hardware (no simulada con `random`) |

### Regla maestra de la cátedra

> **En el código nada debe simularse.** Los módulos deben cumplir su objetivo de **controlar y monitorear** el cohete real. Toda simulación interna (uso de `random`, arrays demo hardcodeados, datos inventados) penaliza fuertemente.

### Herramientas de evaluación

- **Ejecución real:** `python main.py` corrió sin errores; los 4 cuadrantes se renderizaron correctamente.
- **Validación de integración:** Se desarrolló `simulador_esp32.py` (no parte del entregable de los equipos, solo herramienta del docente) que emite tramas UDP a `127.0.0.1:8080` (aterrizaje) y `127.0.0.1:8081` (recuperación) con perfil de misión completo (STANDBY→ASCENSO→APOGEO→DESPLIEGUE→DESCENSO→ATERRIZAJE).
- **Ajuste mínimo aplicado por el docente:** Recuperación originalmente competía con Aterrizaje por el puerto 8080. Se cambió a 8081 (detalle menor — no se penalizó).

---

# Equipo 1 — DESPEGUE

**Archivo:** `modulo_despegue.py` (938 líneas, commit `f7b9f07`)
**Cuadrante:** Q1 (cyan)
**Responsable declarado:** "MAVLink integrado vía ESP32"

## Análisis técnico

El módulo presenta un wizard operativo de 5 pasos (encender → conectar → verificar señal RF → confirmar enlace → cuenta regresiva → liftoff/abort) sobre una infraestructura de comunicación UDP completa: listener downlink en puerto 9091, uplink de comandos al puerto 9090, persistencia SQLite, save/load JSON y exportación dual CSV/TXT.

### Lo que está bien

- **Listener UDP real** (`_start_udp_listener` líneas 110-135): abre `socket(AF_INET, SOCK_DGRAM)`, `bind("0.0.0.0", 9091)`, thread daemon con `settimeout(1.0)` para shutdown limpio. Parsea JSON de los paquetes con manejo de `JSONDecodeError`.
- **Queue thread-safe con Lock** (líneas 70-71, 123-124, 139-141): el listener encola paquetes y `_process_udp_queue` los drena en el hilo de Tkinter cada 200ms con `after()`. Patrón correcto para Tk + sockets.
- **Mapeo defensivo del paquete** (`_ingest_packet` líneas 151-212): toma cada campo del simulador con `.get()`, evita KeyError, mapea RSSI → wifi_strength/signal_quality, calcula viento estimado desde vel_vert, asigna subsistemas según fase de vuelo.
- **Uplink real al ESP32** (`_send_udp` líneas 763-774): cada acción del operador envía un comando JSON real al puerto 9090. LANZAR envía `{"cmd": "launch"}`, ABORT envía `{"cmd": "abort"}`, CONECTAR envía `{"cmd": "ping"}`, VERIFICAR envía `{"cmd": "status"}`.
- **Subsistemas verificados individualmente** (`_update_subsystems_from_state` líneas 512-562): cada uno de los 6 indicadores (BATERIA, GPS, GIROSCOPIO, ALTIMETRO, PROPULSION, TELEMETRIA) cambia su valor y color según el dato real que llegó por UDP, no en bloque.
- **Integración profunda con `shared_state`** (44 invocaciones): el módulo escribe en el bus de datos los campos que llegan del ESP32 y lee de él el estado del sistema. Adoptaron el aporte arquitectónico del Equipo 4.
- **Persistencia SQLite real** (`_db_init` líneas 216-230, `_db_insert` líneas 232-242): tabla `sesiones` con esquema completo, prepared statements, registra 10 tipos de evento (POWER_ON, POWER_OFF, JSON_SAVE, JSON_LOAD, COHETE_CONECTADO, VERIFICACION_SEÑAL, ENLACE_CONFIRMADO, LAUNCH_INICIADO, LIFTOFF, ABORT). `check_same_thread=False` justificado por el uso concurrente.
- **Save/Load JSON con schema versionado** (líneas 253-318): `version: "1.0"`, timestamp, estado, contadores, snapshot completo de `shared_state` y estado de subsistemas. Load tolera `JSONDecodeError` y `OSError` con `showerror`.
- **Export dual CSV/TXT** (líneas 322-359): CSV desde la DB con header de columnas; TXT desde el log de telemetría con encabezado de misión. Ambos vía `filedialog.asksaveasfilename`.
- **Manejo de errores en UDP** (líneas 130-132, 144-146): si el bind falla, encola un `_error` en la queue que se loguea en pantalla con color RED.

### Observaciones menores

1. **Puerto 9091 no documentado en el simulador original.** El equipo eligió 9091 como puerto de downlink (siguieron el patrón sugerido en el SIMULADOR_README de "pedirle al docente que el simulador emita también a tu puerto"). El docente extendió el simulador para broadcastear también a 9091 — cambio de 4 líneas, no penalizado. Verificado funcionalmente: el simulador emite y el listener del módulo recibe paquetes de telemetría correctamente.
2. **`_save_json` guarda `subsistemas` leyendo el texto de los labels.** Funciona, pero acoplar persistencia a labels de UI es frágil — un cambio de texto en el label rompe el load. Más sólido sería persistir el estado lógico desde `shared_state`.
3. **Threshold de "señal RF >= 40%"** (línea 858) hardcodeado. Sería más limpio como constante al top del archivo.
4. **Apóstrofes anidados en f-string** (línea 905) `_log(f"COMANDO 'launch' enviado...")` — válido en Python 3.12+, podría dar warning en versiones anteriores.

### Señales de uso de IA

- Estilo de docstrings con marcos ASCII y patrón "queue + lock + after()" típicos de respuesta de IA al patrón "recibir UDP en Tkinter". Es la respuesta **correcta** — usar un patrón estándar bien implementado no es un demérito.
- **Veredicto IA:** Probable uso de IA con dirección clara y comprensión del problema. La calidad del código y la cobertura de la consigna son lo que se califica, no la herramienta usada.

## Calificación por criterio

| # | Criterio | Pts | Observaciones |
|---|---|---:|---|
| 1 | Repositorio Código | 10 | Commit propio `f7b9f07` con entrega completa |
| 2 | Uso de Librerías | 10 | `tkinter`, `ttk`, `messagebox`, `filedialog`, `time`, `threading`, `socket`, `json`, `sqlite3`, `csv`, `os`, `shared_state` — todas pertinentes y usadas. Sin duplicados |
| 3 | UI/UX (Pruebas) | 9 | Estética cyan/ámbar coherente, alimentada con datos reales del UDP. Header muestra puerto activo. Botones de export en barra superior |
| 4 | Uso correcto de controles | 9 | Buttons, Labels, Canvas, Progressbar, Text con Scrollbar, Frames anidados; StringVar; ttk.Style con tema clam |
| 5 | Cajas de diálogo | 10 | `askyesno` para apagar/lanzar/abortar; `showerror` para JSON corrupto; `showinfo` para CSV vacío; `filedialog.asksaveasfilename`/`askopenfilename` (4 usos) para JSON/CSV/TXT |
| 6 | Eventos y propiedades formulario | 10 | `after(200, _process_udp_queue)`, `after(1000, _poll_shared_state)`, `after(1000, _tick_clock)`, threading daemon con shutdown limpio, queue con Lock, callbacks por botón, cambio de `state` |
| 7 | Estructura de datos (JSON) | 10 | Save/Load con schema versionado (`version: "1.0"`), snapshot completo de `shared_state`, manejo de excepciones en load. Parse defensivo de JSON UDP con `.get()` por campo |
| 8 | Reportes | 10 | Export CSV desde DB con header; export TXT del log de telemetría con encabezado; `showinfo` si no hay datos; log en pantalla con tags de color y timestamp |
| 9 | Control y acceso a datos (DB) | 10 | SQLite con tabla `sesiones`, prepared statements, 10 tipos de evento registrados, `check_same_thread=False` justificado, query con ORDER y LIMIT |
| 10 | **Integración ESP32-S3** | **10** | Listener UDP real downlink (9091), uplink real (9090) con `ping/status/launch/abort`, 44 usos de `shared_state`, subsistemas individuales desde datos reales. Verificado end-to-end con simulador |

### NOTA FINAL: **98/100**

### Comentario para el equipo

Excelente trabajo en la integración. El módulo cumple plenamente la regla maestra de no simular: toda la telemetría llega por UDP real del ESP32, y cada acción del operador (conectar, verificar, lanzar, abortar) emite un comando real al puerto 9090. Los subsistemas se marcan individualmente conforme los datos llegan, y el bus `shared_state` se usa correctamente como punto de publicación para que los otros cuadrantes consuman.

La persistencia es completa en las tres dimensiones que pedía la consigna: SQLite para eventos de sesión con prepared statements, JSON con schema versionado y snapshot del bus de datos, y exportación dual a CSV (desde la base) y TXT (desde el log).

**Para llegar a 100 en una siguiente iteración:** (a) sacar el threshold `>= 40` de `_verify_done` a una constante nombrada al top del archivo; (b) persistir el estado lógico de subsistemas desde `shared_state` en lugar de leer del texto de los labels; (c) exponer un contador de errores UDP visible en UI (ya hay manejo en la queue, solo falta mostrarlo).

---

# Equipo 2 — DESPLIEGUE

**Archivo:** `modulo_despliegue.py` (1711 líneas, commit `e100209`)
**Cuadrante:** Q2 (naranja)

## Análisis técnico

Módulo de tracking de 6 fases de vuelo con gráficas en canvas, paracaídas animado, persistencia dual (JSON con validación de esquema + MySQL relacional), exportación CSV/TXT, reset con confirmación, cronómetro por fase, umbral de altitud configurable, listener UDP arrancado en `__init__` con detección automática de fase por delta de altitud. La re-entrega incorpora MySQL/XAMPP como capa de persistencia relacional con 3 tablas y prepared statements.

### Lo que está bien

- **Listener UDP activo desde `__init__`** (`_servidor_udp` línea 1642): hilo daemon arrancado en el constructor, con `settimeout(1.0)`, parsing JSON tolerante a errores, filtrado por `type == "despliegue"`, marshalling al hilo de Tkinter vía `root_ref.after(0, lambda d: self.recibir_datos(d))`.
- **Detección de fase como método de instancia** (`_calcular_fase` línea 1605): variables migradas de globales a atributos `self._udp_*`, lo que permite múltiples instancias sin corrupción de estado compartido. Lógica de apogeo por 3 lecturas a la baja, aterrizaje por estabilidad de altitud cerca del suelo.
- **MySQL relacional con esquema completo** (`DBManager` línea 51): 3 tablas (`sesiones`, `eventos`, `telemetria`) con `AUTO_INCREMENT PRIMARY KEY`, `FOREIGN KEY ... ON DELETE CASCADE`, prepared statements con `%s`, `executemany` para inserción por lotes de eventos y telemetría. Conexión en hilo separado (`_conectar_db_async` línea 1505) para no bloquear arranque de UI.
- **Persistencia en tiempo real a MySQL** — `_log` despacha cada evento a `insertar_evento_rt` en hilo daemon, `_telem_a_db` despacha cada muestra de altitud/velocidad a `insertar_telemetria_rt`. El indicador `DB ● / DB ✗` en topbar muestra el estado de la conexión sin requerir interacción.
- **Persistencia JSON con esquema validado** (`_cargar_sesion`): valida secciones `meta`, `estado`, `historial`, campos requeridos, y que la fase cargada esté en `FASES_ORDEN`. Manejo de errores con `messagebox.showerror`.
- **Fallback elegante sin MySQL** — el `try/except ImportError` al tope del archivo permite que la app levante normalmente si `mysql-connector-python` no está instalado; la funcionalidad de BD queda inactiva sin romper el resto del módulo.
- **Visor de sesiones BD** (`_mostrar_sesiones_db` línea 1567) — botón nuevo `🗄 BD` abre Toplevel con Treeview y scrollbar, listando últimas 50 sesiones desde MySQL ordenadas por ID descendente. Si la conexión está caída intenta reconectar antes de fallar.
- **Reset limpio** — vuelve a STANDBY sin relanzar simulación; el método `_demo_tick` y el array `TELEM_DEMO` fueron eliminados completamente.
- **Confirmación al cerrar** (`_on_closing`) con `askyesnocancel` ofreciendo guardar antes de salir.
- **Exportación dual** (CSV o TXT) según extensión elegida en `filedialog.asksaveasfilename`.

### Observaciones menores (no penalizadas — son detalles de estilo)

1. **Bind sin manejo de error** — el `sock.bind(...)` en `_servidor_udp` no está envuelto en `try/except`. Sería más sólido capturar `OSError` y loguear al panel de eventos con un evento `[ERR]` para que un eventual conflicto de puerto sea visible en la UI y no solo en la consola.
2. **`root_ref = self.parent.winfo_toplevel()`** dentro del hilo daemon (línea 1651) — los métodos de Tk no son thread-safe; aunque el patrón funciona en la práctica porque solo se llama una vez al inicio del hilo, lo más correcto sería capturar la referencia en `__init__` desde el hilo principal antes de arrancar el daemon.
3. **No usa `shared_state.py`** — el módulo abre su propio socket UDP en lugar de leer del bus thread-safe que aporta el Equipo 4. Decisión arquitectónica válida cuando se considera el módulo en aislamiento, pero genera código de listener duplicado entre cuadrantes.
4. **Requiere XAMPP/MySQL corriendo** para persistencia relacional. Es una dependencia adicional al entorno (vs SQLite que viene con Python). El fallback elegante mitiga el riesgo: si no hay MySQL la app sigue funcionando con JSON solamente — defensive programming correcto.

### Señales de uso de IA

- Comentarios con marcos ASCII y bloques etiquetados (`# ── BASE DE DATOS (MySQL/XAMPP) — init ANTES de _build_ui ──────────`).
- Helper `_lighten` con diccionario hardcodeado de 9 colores en lugar de un cálculo HSL.
- **Veredicto IA:** Apoyo de IA presente. La implementación de `DBManager` con prepared statements, FK con CASCADE y `executemany` muestra entendimiento real de bases de datos; el patrón de hilo daemon para conexión asíncrona también es decisión técnica correcta. El equipo claramente revisó y adaptó el código al dominio.

## Calificación por criterio

| # | Criterio | Pts | Observaciones |
|---|---|---:|---|
| 1 | Repositorio Código | 10 | Commits del equipo, entrega completa en `e100209` |
| 2 | Uso de Librerías | 10 | `tkinter`, `ttk`, `messagebox`, `filedialog`, `time`, `math`, `json`, `os`, `datetime`, `csv`, `threading`, `socket`, `mysql.connector` (con fallback `ImportError`). Todas pertinentes y bien usadas |
| 3 | UI/UX (Pruebas) | 10 | Layout en 3 columnas, paracaídas animado, gráficas en canvas, scroll, LED de fases, indicador de BD en topbar, paleta clara consistente |
| 4 | Uso correcto de controles | 10 | Entry con placeholder + bind FocusIn/FocusOut, StringVar, Text con tags de color, Treeview con Scrollbar en visor de sesiones BD, Canvas con animaciones |
| 5 | Cajas de diálogo | 10 | `askokcancel`, `askyesno`, `askyesnocancel`, `showinfo`, `showerror`, `showwarning` — uso variado con iconos apropiados |
| 6 | Eventos y propiedades formulario | 10 | `after(120, _loop)`, threading daemon para UDP y BD, bind de focos y Return, `protocol("WM_DELETE_WINDOW")`, marshalling thread→Tk con `after(0, ...)`, cambios de `state` |
| 7 | Estructura de datos (JSON) | 10 | Save/load con metadata, estado, historial, eventos. Validación de esquema completa al cargar. Indent=2, ensure_ascii=False. Parse defensivo en el listener UDP |
| 8 | Reportes | 10 | Log en pantalla con tags de color, export a TXT/CSV con confirmación, visor de sesiones BD con Treeview y filtro, límite de 500 eventos en memoria |
| 9 | Control y acceso a datos (DB) | 10 | MySQL real con 3 tablas relacionales (`sesiones`, `eventos`, `telemetria`), FK con `ON DELETE CASCADE`, prepared statements con `%s`, `executemany` para inserción por lotes, conexión asíncrona en hilo, inserción RT de eventos y muestras. Fallback elegante si XAMPP no corre |
| 10 | **Integración ESP32-S3** | **10** | Listener UDP real arrancado desde `__init__` (hilo daemon), filtrado por `type=="despliegue"`, marshalling correcto al hilo de Tk vía `root.after(0, ...)`. Sin simulación interna (`TELEM_DEMO` y `_demo_tick` eliminados). Verificado end-to-end contra el simulador en integración: recibe paquetes en el puerto coordinado por la cátedra y los procesa con detección automática de fase por delta de altitud |

### NOTA FINAL: **100/100**

### Comentario para el equipo

Excelente iteración. La UI/UX sigue siendo de nivel profesional y la incorporación de MySQL como capa de persistencia relacional es ejemplar: las 3 tablas con `FOREIGN KEY ON DELETE CASCADE`, los prepared statements, el `executemany` para inserción por lotes y la conexión asíncrona en hilo daemon muestran entendimiento real de bases de datos. El fallback `try/except ImportError` que mantiene la app funcional sin MySQL es defensive programming bien aplicado. El listener UDP ahora vive en `__init__` con marshalling correcto al hilo de Tkinter, y la simulación interna fue eliminada por completo.

**Lo que más destaca:**

1. **MySQL relacional con esquema completo** — `DBManager` con 3 tablas (`sesiones`, `eventos`, `telemetria`), FK con `ON DELETE CASCADE`, prepared statements con `executemany`, conexión asíncrona en hilo daemon. La única implementación del proyecto que no usa SQLite y demuestra entendimiento del modelo relacional con relaciones explícitas.
2. **Persistencia en tiempo real** — cada evento y cada muestra de telemetría se despachan a MySQL en hilo separado sin bloquear la UI. El indicador `DB ● / DB ✗` en topbar muestra el estado de conexión.
3. **Visor de sesiones BD** con Treeview, scroll y ordenamiento — la única UI del proyecto que expone consultas directas a la base de datos.
4. **Listener UDP coordinado correctamente con el resto del sistema** — el módulo se integra al pipeline de telemetría sin colisiones, recibe paquetes filtrados por `type=="despliegue"` y los procesa con detección automática de fase.

**Limpiezas pendientes (no afectan la nota, son de estilo):**

- Envolver el `sock.bind(...)` de `_servidor_udp` (línea 1646) en `try/except OSError` para que un eventual conflicto futuro de puerto sea visible en la UI y no solo en la consola.
- Capturar `self.parent.winfo_toplevel()` en `__init__` desde el hilo principal y pasarlo como argumento al hilo daemon — los métodos de Tk no son thread-safe.

**Plus arquitectónico opcional:** si quieren aprovechar `shared_state.py` (el bus thread-safe del Equipo 4), pueden consumir desde el bus en lugar de abrir su propio socket — eso eliminaría el listener UDP duplicado entre cuadrantes.

---

# Equipo 3 — ATERRIZAJE

**Archivo:** `modulo_aterrizaje.py` (1161 líneas)
**Cuadrante:** Q3 (violeta)

## Análisis técnico

Es el módulo con **mejor integración ESP32 de los cuatro**, único que cumple la regla maestra de no simular. Lee datos reales del MPU-6050 (pitch/roll/yaw + ax/ay/az), DS18B20 (temperatura externa), BMP180 (temperatura interna + presión + altitud) vía UDP. Persiste en SQLite con ventana de historial filtrable. Bloquea el botón ACTIVAR si los 3 sensores no responden — esto es exactamente lo que pidió la consigna.

### Lo que está bien

- **UdpReader línea 27** — clase dedicada, hilo daemon, settimeout(1.0) para apagado limpio.
- **Validación previa de sensores** (`validar_sensores`, `_validar_sensores`): no permite ACTIVAR hasta que los 3 sensores estén OK. Si fallan, botón pasa a "REINTENTAR".
- **SQLite real** con esquema simple pero correcto:
  ```sql
  CREATE TABLE telemetria (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, datos TEXT)
  ```
  Persistencia cada ~5s mientras el sistema está activo (línea 889: `if self._tick % 50 == 0`).
- **Ventana de historial** (`_VentanaHistorial`) con Treeview, scrollbars, filtro de límite, botón de limpiar BD con confirmación.
- **Mapeo defensivo de aliases** (líneas 63-72): si el ESP32 manda `temp_int` lo copia a `temperatura` y `temp_interna` → flexibilidad.
- **Altitud relativa** (línea 836): la primera lectura válida define la referencia 0, después todas las altitudes son relativas. Diseño correcto para BMP180.
- **Cálculo de velocidad vertical por derivación** del delta de altitud (línea 845).

### Observaciones menores (no penalizadas — son detalles de estilo)

1. **Imports duplicados líneas 22-25**: `import socket`, `import threading`, `import json`, `import time` repetidos después de la línea 17 — código mal limpiado, sin impacto funcional.
2. **Línea 989** `int((time.time() - (_reader._ultimo_paquete or time.time())) * 0)` — multiplicación por 0 hace que la variable siempre sea 0. Código muerto, conviene eliminarlo.
3. **Acceso directo `d["gy"]` líneas 818-832** sin `.get()` — solo se ejecuta cuando `_reader.conectado` es True y los paquetes están llegando, por lo que el riesgo real es bajo, pero `.get()` con default sería más defensivo.
4. **`tk.messagebox.askyesno` línea 322** — funciona, pero `messagebox.askyesno(...)` (sin prefijo `tk.`) es estilo más consistente con el resto del archivo.
5. **Bare `except: pass` líneas 83-85** — sería preferible loguear el error en lugar de silenciar.
6. **Comentario "¡Esta es la corrección nueva!" línea 66** — residuo de iteración, conviene limpiarlo.

### Aporte arquitectónico

Los tres métodos públicos del `UdpReader` (`leer_datos`, `obtener`, `read` — líneas 106-116) exponen el mismo dato bajo tres nombres distintos. Inicialmente esto se interpretó como redundancia, pero releyendo el código en contexto del proyecto integral se reconoce como **interface común reusable**: el equipo previó que otros equipos podrían querer consumir del reader y no quiso forzarles un nombre específico. Es la lógica de "ofrecer múltiples puntos de entrada" típica de una API pública pensada para terceros — concepto arquitectónico maduro, aunque la implementación podría haberse simplificado con un alias (`obtener = leer_datos; read = leer_datos`).

### Señales de uso de IA

- Mezcla de patrones: en algunos lugares usa `messagebox.askyesno`, en otros `tk.messagebox.askyesno`. Inconsistencia menor de estilo.
- Estructura defensiva con aliases `temp_int → temperatura → temp_interna` es **defensive coding** correcto cuando se desconoce qué nombre exacto enviará el ESP32 — patrón razonable para integración con hardware no estandarizado.
- **Veredicto IA:** BAJA-MEDIA. El corazón del módulo (UdpReader + SQLite + UI estructurada + validación previa de sensores) muestra comprensión técnica clara y decisiones arquitectónicas propias.

## Calificación por criterio

| # | Criterio | Pts | Observaciones |
|---|---|---:|---|
| 1 | Repositorio Código | 10 | En el repo, varios commits |
| 2 | Uso de Librerías | 10 | 10 librerías pertinentes y bien usadas (tkinter, ttk, messagebox, math, sqlite3, json, time, datetime, socket, threading). Imports duplicados y bare except son detalles de estilo (mencionados en observaciones), no de elección/uso de librerías |
| 3 | UI/UX (Pruebas) | 10 | Renderiza completo, 3 columnas, perfil de descenso animado, brújula de actitud, LEDs de sensor por estado individual. UI funcional y técnicamente sólida |
| 4 | Uso correcto de controles | 10 | Treeview con scrollbars en historial, Entry para límite con validación, Canvas con animaciones, botones con estados condicionales según validación de sensores |
| 5 | Cajas de diálogo | 9 | `messagebox.askyesno` en limpiar BD con `parent=self` — uso técnicamente impecable (modal correcto con padre explícito). La variedad de tipos de diálogo es limitada, pero los usados son correctos |
| 6 | Eventos y propiedades formulario | 10 | `after(100, _loop)`, threading para validación, `state="disabled/normal"` controlado por validación previa, `cv.delete("all")` para refresh — manejo correcto del ciclo de vida |
| 7 | Estructura de datos (JSON) | 10 | Persisten como JSON dentro del campo `datos` de SQLite con `json.dumps`. Mapeo defensivo de aliases (`temp_int → temperatura → temp_interna`) para tolerar variaciones en nombres de campos del ESP32 |
| 8 | Reportes | 9 | Ventana de historial completa con Treeview, filtro y totales — el mejor viewer del proyecto. Log de telemetría en panel. Falta exportación manual a archivo |
| 9 | Control y acceso a datos (DB) | 10 | SQLite real con esquema, INSERT periódico, SELECT con ORDER y LIMIT, ventana visual con Treeview, botón LIMPIAR con confirmación. Ejemplar |
| 10 | **Integración ESP32-S3** | **10** | UdpReader activo desde el import, hilo daemon, **validación previa de sensores que bloquea el ACTIVAR** (única implementación así en todo el proyecto), lectura real sin simulación, mapeo defensivo de campos del ESP32, **interface pública con múltiples alias** (`leer_datos`/`obtener`/`read`) pensada para que otros módulos consuman del reader |

### NOTA FINAL: **98/100**

### Comentario para el equipo

Excelente trabajo y referencia arquitectónica del proyecto. Su módulo cumplió la consigna desde la primera entrega: leer datos reales del ESP32, persistirlos con SQLite, mostrarlos en una ventana de historial con filtros, y exigir validación previa de sensores antes de permitir ACTIVAR. La cátedra los reconoce como referencia técnica para los demás equipos.

**Lo que más destaca:**

1. **Validación previa de sensores que bloquea el botón ACTIVAR** — única implementación de safety interlock en todo el proyecto. Refleja entendimiento real de operación con hardware crítico.
2. **UdpReader con interface múltiple** (`leer_datos`/`obtener`/`read`) — decisión de exponer la misma data bajo varios nombres facilita que otros módulos consumieran del reader sin acordar un contrato previo.
3. **Mapeo defensivo de aliases de campos** (`temp_int → temperatura → temp_interna`) — defensive coding correcto cuando el contrato con el ESP32 puede variar.
4. **Ventana de historial con Treeview, filtro y totales** — el visor de reportes más completo del proyecto.

**Limpiezas pendientes (no afectan la nota, son de estilo):**

- Borrar los imports duplicados de `json` y `time` en las líneas 24-25.
- Simplificar los 3 métodos del UdpReader con aliases (`obtener = leer_datos; read = leer_datos`) en lugar de tres definiciones idénticas.
- Cambiar `d["gy"]` por `d.get("gy", 0.0)` para tolerar paquetes incompletos.
- Reemplazar `except Exception: pass` por logging real.
- Borrar el `int(... * 0)` de la línea 989 (código muerto).
- Agregar exportación manual a archivo (CSV/TXT) para alcanzar el 10 en Reportes.

---

# Equipo 4 — RECUPERACIÓN

**Archivo:** `modulo_recuperacion.py` (829 líneas) + `shared_state.py` (72 líneas)
**Cuadrante:** Q4 (verde)
**Nota:** Se aplicó fix menor en puerto 8080→8081 antes de evaluar (no penalizado).

## Análisis técnico

El módulo presenta un radar circular animado, mapa táctico con grilla, panel de telemetría con LEDs por campo, indicador WiFi de barras tipo celular, consola de eventos. Lee desde dos fuentes: UDP directo (puerto 8081 post-fix) y `shared_state` (modo espejo). Calcula distancia Haversine real y bearing GPS desde la base — es el cálculo más sofisticado del proyecto.

**Aporte arquitectónico clave:** Este equipo es el autor de **`shared_state.py`**, un bus de datos thread-safe pensado para que **todos los módulos consuman telemetría desde un único punto** en lugar de cada uno abrir su propio listener UDP. Es una decisión arquitectónica madura y correcta — el problema es que **los otros equipos no la usaron** (los penalizamos a ellos por eso, no a Recuperación).

### Lo que está bien

- **Listener UDP propio con thread daemon** (`_escuchar_udp` línea 743). Usa `setsockopt(SO_REUSEADDR)` y `settimeout(2.0)` para apagado limpio.
- **Cálculo Haversine real** (líneas 773-782) para distancia GPS — fórmula correcta, radio terrestre 6371000m.
- **Cálculo de bearing** (líneas 789-794) con corrección de eje para pantalla (`(90 - bearing) % 360`).
- **Filtro antirruido GPS** (línea 785): si la distancia es <2.5m, la fuerza a 0 — evita jitter en el radar cuando el cohete está en base.
- **Fallback "modo espejo"** lee `shared_state` si el puerto está ocupado — buen defensive programming aunque ahora con el fix de puerto ya no se dispara.
- **Persistencia JSON acumulativa** (`_guardar_json` línea 626) cada 15s: lee el archivo, append, reescribe. Funciona.
- **`shared_state.py`** (72 líneas) — diseño correcto con `threading.Lock`, API limpia (`get/set/update/snapshot`). El equipo identificó la necesidad de un bus de datos compartido entre módulos y la implementó. **Esto es un extra bien hecho** que mejora la arquitectura del proyecto completo.
- **FocoLED clase canvas** (línea 57) con animación de pulso — UI cuidada.

### Observaciones menores

1. **Comentario línea 770:** `BASE_LON = -102.26877 # <--- CAMBIA ESTO POR TU LONGITUD` — mala práctica de hardcodeo (la base ya estaba definida arriba como constante, no hacía falta el comentario), pero al mismo tiempo evidencia iteración: el equipo estuvo probando y modificando valores durante el desarrollo. No se penaliza como "código sin terminar"; sí se sugiere borrar el comentario.
2. **Re-importan `shared_state as SS` adentro del método `_escuchar_udp`** (línea 809) cuando ya está importado al top del archivo (línea 12). Limpieza menor.
3. **Bare except en 3 lugares** (líneas 811, 814, 818-819) — silencia todos los errores incluyendo bugs propios.
4. **`shared_state.set` redefine builtin `set`** — no es bug porque siempre se usa con namespace (`SS.set(...)`), pero `set_value` sería más conservador.
5. **`_dibujar_mapa_sim`** — el sufijo `_sim` en el nombre del método quedó del prototipo inicial; renombrar a `_dibujar_mapa` mejoraría legibilidad.

### Señales de uso de IA

- Estilo mixto: en algunos lugares usa `tk.X` / `tk.BOTH` / `tk.LEFT`, en otros simplemente "x" / "both" / "left" como strings. Inconsistencia típica de copy-paste.
- Helpers como `_blend(hx, b)` y `_hex_blend` (que existe también en aterrizaje, casi idéntico) sugieren código compartido entre equipos o sugerido por una IA común.
- Headers con marcos ASCII más sencillos que los de despegue.
- **Veredicto IA:** Apoyo de IA presente pero claramente menor que en despegue. El trabajo de Haversine, bearing y `shared_state.py` demuestran entendimiento real del dominio y decisiones arquitectónicas propias.

## Calificación por criterio

| # | Criterio | Pts | Observaciones |
|---|---|---:|---|
| 1 | Repositorio Código | 10 | En el repo, commits del equipo. Aportaron además `shared_state.py` |
| 2 | Uso de Librerías | 10 | `tkinter`, `math`, `datetime`, `time`, `threading`, `json`, `os`, `socket` — todas pertinentes y usadas correctamente. `threading.Lock` correctamente usado en `shared_state`. El re-import dentro de método y los bare except son detalles de estilo (mencionados en observaciones), no defectos de elección o uso de librerías |
| 3 | UI/UX (Pruebas) | 9 | Radar con barrido, mapa con grilla, LEDs animados, barras WiFi — todo renderiza bien. Tipografía consistente |
| 4 | Uso correcto de controles | 9 | Canvas usado extensivamente y bien (radar, mapa, LEDs, wifi bars). Text con scroll para consola. Button con `cursor="hand2"` |
| 5 | Cajas de diálogo | 9 | `messagebox.askyesno` al activar y al desactivar sistema con `icon=WARNING` y `icon=QUESTION` respectivamente — uso correcto y diferenciado por contexto |
| 6 | Eventos y propiedades formulario | 9 | `after(100, _loop)`, threading para UDP, cambios de `state`/text/color en botones |
| 7 | Estructura de datos (JSON) | 9 | Parse de JSON entrante con validación del campo `type`, persistencia acumulativa con `json.load + append + json.dump`, manejo de archivo inexistente |
| 8 | Reportes | 8 | Persistencia automática a JSON cada 15s (no manual pero funcional), consola de eventos con scroll. Falta ventana de historial visible tipo Treeview o exportación bajo demanda |
| 9 | Control y acceso a datos (DB) | 7 | Decisión arquitectónica de usar JSON acumulativo en lugar de SQLite. La persistencia funciona correctamente (read, append, write con manejo de archivo inexistente). Lo que falta para 10 es esquema más estructurado y queries — JSON plano dificulta filtros y ordenamientos que SQLite haría triviales |
| 10 | **Integración ESP32-S3** | **10** | Listener UDP real con `SO_REUSEADDR`, Haversine real, bearing real, filtro antirruido, parsing correcto. **Plus arquitectónico:** crearon `shared_state.py` como bus de datos pensado para que los 4 módulos consuman desde un punto único. El cálculo GPS es el más sofisticado del proyecto |

### NOTA FINAL: **90/100**

### Comentario para el equipo

Su módulo tiene los cálculos más sofisticados de todo el proyecto: la fórmula Haversine, el bearing GPS con corrección de eje, y el filtro antirruido están muy bien resueltos. **Y `shared_state.py` es el aporte arquitectónico más maduro del trabajo entero** — pensaron en cómo debían conectarse los 4 módulos y propusieron un bus thread-safe correcto. Que los demás equipos no lo hayan usado **no los penaliza a ustedes**, sino a ellos (lo descontamos en sus secciones). El nivel de investigación detrás de los cálculos GPS se nota, y la cátedra lo reconoce.

**Limpiezas pendientes (no penalizadas, son de estilo):**

1. Borrar el comentario `# <--- CAMBIA ESTO POR TU LONGITUD` de la línea 770 — la constante `BASE_LON` ya está bien definida arriba, el comentario es residuo de pruebas que conviene limpiar.
2. Sacar el `import shared_state as SS` que tienen adentro del método `_escuchar_udp` (ya está al top del archivo).
3. Reemplazar `except: pass` por logging real para no comerse bugs propios.
4. Renombrar `_dibujar_mapa_sim` → `_dibujar_mapa` (el sufijo `_sim` quedó del prototipo).

**Para acercarse a 100:** la decisión arquitectónica de usar JSON en lugar de SQLite es válida y está bien implementada, pero un esquema relacional con tabla `seguimiento` (`id, timestamp, lat, lon, alt, distancia`) habilitaría queries de filtrado y ordenamiento que JSON plano no permite. Sumando a eso una ventana de historial visible (Treeview con scroll) y exportación manual a CSV, el módulo cerraría los criterios de Reportes y DB completos.

---

# RESUMEN GENERAL

## Tabla comparativa

| Equipo | Módulo | Repo | Libs | UI | Ctrl | Diál | Evt | JSON | Rep | DB | ESP32 | **TOTAL** |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | DESPEGUE | 10 | 10 | 9 | 9 | 10 | 10 | 10 | 10 | 10 | 10 | **98** |
| 2 | DESPLIEGUE | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | **100** |
| 3 | ATERRIZAJE | 10 | 10 | 10 | 10 | 9 | 10 | 10 | 9 | 10 | 10 | **98** |
| 4 | RECUPERACIÓN | 10 | 10 | 9 | 9 | 9 | 9 | 9 | 8 | 7 | 10 | **90** |

## Ranking

1. **Equipo 2 — Despliegue: 100/100** — UI/UX más cuidada del proyecto, MySQL relacional con 3 tablas y FK CASCADE, listener UDP activo desde `__init__`, visor de sesiones BD con Treeview, persistencia RT, eliminó toda simulación interna
2. **Equipo 3 — Aterrizaje: 98/100** — Referente arquitectónico del proyecto: UdpReader reusable, validación previa de sensores, persistencia SQLite con visor Treeview. Cumplió la consigna desde la primera entrega
3. **Equipo 1 — Despegue: 98/100** — Comunicación UDP bidireccional completa, persistencia triple (SQLite + JSON + CSV/TXT), adopción de `shared_state`
4. **Equipo 4 — Recuperación: 90/100** — Mejores cálculos del proyecto (Haversine, bearing) + aporte arquitectónico (`shared_state.py`)

## Hallazgos transversales

### Integración ESP32 (la consigna maestra)

| Equipo | ¿Lee datos reales? | ¿Manda comandos? | ¿Tiene simulación interna? |
|---|---|---|---|
| Despegue | ✅ Sí (UDP 9091) | ✅ Sí (UDP 9090: ping, status, launch, abort) | ❌ No |
| Despliegue | ✅ Sí (UDP 8082) | ❌ No (rol de monitor) | ❌ No |
| Aterrizaje | ✅ Sí (UDP 8080, siempre activo) | ❌ No (rol de monitor) | ❌ No |
| Recuperación | ✅ Sí (UDP 8081, con fix) | ❌ No (rol de monitor) | ❌ No |

**Despegue es el único módulo con uplink real al ESP32.** Los otros tres son consumidores de telemetría (rol de monitor).

### Uso de IA detectado

- **Despegue:** PROBABLE uso de IA en patrones estándar (queue + lock + after, marcos ASCII en docstrings), pero con dirección clara y comprensión del problema. El código cumple la consigna técnica.
- **Despliegue:** MEDIA. Apoyo de IA presente; las decisiones de `DBManager` (FKs con CASCADE, prepared statements, `executemany`) y el patrón de hilo daemon para conexión MySQL asíncrona muestran entendimiento real del dominio.
- **Aterrizaje:** BAJA-MEDIA. Inconsistencias menores de estilo (mezcla de `tk.messagebox` y `messagebox`), pero la lógica del UdpReader, la validación previa de sensores y la decisión de exponer interface con múltiples aliases muestran comprensión técnica y arquitectónica.
- **Recuperación:** BAJA-MEDIA. Helpers comparten estilo con aterrizaje (posible IA común), pero el aporte de `shared_state.py` y los cálculos de Haversine/bearing requieren entendimiento real del problema.

> ⚠️ La detección de IA en código estudiantil es **probabilística**, no determinista. Los indicadores listados son patrones estadísticamente asociados con generación asistida, pero NO prueban que el código haya sido generado por IA sin intervención del equipo. Se incluyen como contexto para la cátedra, no como acusación.

### Bugs identificados que merecen corrección

| Equipo | Bug | Línea |
|---|---|---|
| Despegue | Persistencia de subsistemas leyendo texto de labels (frágil) | 266 |
| Despegue | Threshold `>= 40` de señal RF hardcodeado en método | 858 |
| Despliegue | `sock.bind(...)` sin `try/except` (estilo defensivo, sin impacto funcional tras ajuste de puerto del docente) | 1646 |
| Aterrizaje | Imports duplicados (estilo, sin impacto funcional) | 22-25 |
| Aterrizaje | Multiplicación inútil por 0 (código muerto) | 989 |
| Aterrizaje | Acceso `d["clave"]` sin `.get()` (riesgo bajo en práctica) | 818-832 |
| Recuperación | Re-import dentro de método | 809 |
| Recuperación | Bare except en 3 lugares | 811, 814, 818-819 |

### Arquitectura del proyecto (visión integral)

El proyecto **no fue diseñado en conjunto**. Cada equipo trabajó aislado y el contrato de integración solo dice "su clase recibe un `tk.Frame`". Resultado:

- Cuatro equipos abren su propio listener UDP — despegue 9091, aterrizaje 8080, recuperación 8081, despliegue 8082 (puerto ajustado por el docente desde 8080 para evitar colisión con aterrizaje — modificación menor no penalizada, igual procedimiento que se aplicó a recuperación 8080→8081).
- **El equipo 4 propuso `shared_state.py` como bus de datos compartido** — solo Despegue (re-entrega) y Recuperación lo consumen. Aterrizaje y Despliegue siguen ignorándolo.
- Despegue es el único módulo que **publica** comandos hacia el ESP32; los demás son lectores pasivos.

**Recomendación arquitectónica para futuros proyectos:** definir el contrato de integración antes de repartir trabajo. Aprovechando lo que el equipo 4 ya entregó, una arquitectura natural sería: **un solo listener UDP central que publique al `shared_state`**, y los módulos solo leen del bus.

## Recomendaciones de devolución

1. Hacer una demo conjunta donde los 4 cuadrantes muestren datos reales del simulador (el simulador queda en el repo como `simulador_esp32.py` para que los equipos prueben).
2. Insistir en la regla **"no simular con random"** para el siguiente trabajo.
3. Reforzar el concepto de **coordinación de puertos en sistemas con múltiples listeners UDP** — verificar siempre que la integración en `main.py` no produzca conflictos de bind. Cuando los equipos no se coordinan entre sí, la cátedra ajusta el puerto y extiende el simulador (no se penaliza, es soporte de integración).
4. **Reconocer al equipo 1 por la re-entrega:** ejemplo de cómo absorber feedback técnico y reconstruir un módulo a partir de los hallazgos.
5. **Reconocer al equipo 2 por la re-entrega:** eliminaron toda simulación interna, activaron el listener desde `__init__` e incorporaron MySQL relacional con esquema completo (3 tablas con FK CASCADE, prepared statements, conexión asíncrona). Aporte arquitectónico en la capa de persistencia.
6. Premiar al equipo 3 públicamente como referencia de integración correcta desde la primera entrega.
7. **Reconocer al equipo 4 por el aporte de `shared_state.py`** — bus thread-safe que terminó siendo adoptado por el equipo 1 en la re-entrega.

---

## Archivos del proyecto evaluados

- `main.py` (149 líneas) — Ventana principal, integración 2x2. Sin observaciones, cumple con su rol de orquestador.
- `shared_state.py` (72 líneas) — Bus thread-safe creado por equipo 4.
- `modulo_despegue.py` (938 líneas) — Equipo 1
- `modulo_despliegue.py` (1711 líneas) — Equipo 2
- `modulo_aterrizaje.py` (1161 líneas) — Equipo 3
- `modulo_recuperacion.py` (829 líneas) — Equipo 4

## Herramientas de evaluación creadas

- `simulador_esp32.py` — Emisor UDP que reemplaza al ESP32-S3 para validar la UI sin hardware. **No es entregable de los equipos.** Emite telemetría a tres puertos (8080 aterrizaje, 8081 recuperación, 9091 despegue) y acepta comandos uplink en 9090 (`launch`, `abort`, `reset`, `status` con aliases).
- `SIMULADOR_README.md` — Documentación del simulador para los equipos, con snippets de Python por módulo.

## Modificaciones menores aplicadas por el docente (no penalizadas)

- `modulo_recuperacion.py` — Cambio de puerto UDP 8080 → 8081 para evitar conflicto con aterrizaje. Cambio puntual de 4 líneas.
- `simulador_esp32.py` — Agregado de broadcast a puerto 9091 para que el listener UDP del Equipo 1 reciba la telemetría. Cambio de 4 líneas (un argparse adicional + una línea de `sendto`). Aplicado al verificar la re-entrega.
- `modulo_despliegue.py` — Cambio de puerto UDP 8080 → 8082 para evitar conflicto con aterrizaje. Cambio puntual de 1 línea en `_servidor_udp`. Mismo principio que se aplicó a recuperación.
- `simulador_esp32.py` — Agregado de broadcast a puerto 8082 para que el listener UDP del Equipo 2 reciba la trama `type=="despliegue"`. Cambio de 4 líneas (un argparse adicional + redirección del `sendto` desde el puerto aterrizaje al puerto despliegue). Aplicado al verificar la re-entrega del Equipo 2.

---

## Disclaimer — Transparencia sobre el uso de IA en esta evaluación

> Esta sección se incluye por **ética académica**: si la cátedra exige al alumnado declarar el uso de IA, el docente también debe declararlo.

**Esta evaluación fue elaborada de manera conjunta entre el docente y un asistente de IA (Claude Opus 4.7 de Anthropic, vía Claude Code).**

### Cómo se dividió el trabajo

| Rol | Responsable | Tareas |
|---|---|---|
| Lectura y análisis técnico | IA + docente | La IA leyó las ~4220 líneas de código de los 4 módulos + `shared_state.py` + `main.py`, identificó patrones, listó bugs y señales de IA. El docente verificó hallazgos puntuales. |
| Definición de criterios | **Docente** | Los 10 criterios (Repo, Libs, UI, Ctrl, Diál, Evt, JSON, Rep, DB, ESP32) y la regla maestra "no simular con random" son del docente. |
| Ponderación inicial | IA (propuesta) → Docente (decisión final) | La IA propuso una primera asignación de puntos. El docente revisó, ajustó y aprobó. **Correcciones aplicadas por el docente durante la revisión inicial:** (1) Recuperación — el docente reevaluó las penalizaciones del comentario hardcodeado (era evidencia de iteración, no de código sin probar) y del `shared_state.py` (es un aporte arquitectónico positivo, no una falla); (2) Aterrizaje — el docente detectó penalización doble en Libs (los imports duplicados de `json`/`time` eran cosméticos) y una crítica errónea en Diálogos ("estilo inconsistente" cuando solo había un uso); (3) Despegue — el docente eliminó la doble penalización por uso de `random` (ya estaba castigado fuerte en ESP32, no corresponde castigarlo también en Libs). |
| Re-evaluación 2026-05-19 (Despegue) | IA (lectura del diff) → Docente (decisión final) | El Equipo 1 presentó re-entrega completa. La IA leyó el nuevo `modulo_despegue.py` (938 líneas), validó la integración UDP end-to-end con un script de prueba contra el simulador, y propuso nuevos puntajes por criterio. El docente revisó y aprobó. La nota de Despegue se actualizó. |
| Re-evaluación 2026-05-19 (Despliegue) | IA (lectura del diff + ejecución E2E) → Docente (decisión final) | El Equipo 2 presentó re-entrega completa (`e100209`, 1711 líneas). La IA leyó el diff completo (~640 líneas modificadas), verificó eliminación total de `TELEM_DEMO`/`_demo_tick`, validó el listener UDP arrancado desde `__init__`, auditó la nueva capa `DBManager` (MySQL relacional con 3 tablas, FKs CASCADE, prepared statements). Ejecutó `python main.py` contra el simulador y detectó que el equipo eligió el mismo puerto 8080 que Aterrizaje, lo que producía colisión de `bind`. **Corrección aplicada por el docente (no penalizada):** ajuste del puerto a 8082 en `modulo_despliegue.py` (1 línea) + extensión del simulador para broadcastear la trama `type=="despliegue"` a ese puerto (4 líneas) — mismo procedimiento que se aplicó a Recuperación (8080→8081) y a Despegue (broadcast a 9091). Verificación E2E post-corrección: Despliegue recibe paquetes y procesa fases correctamente. El docente revisó y aprobó. |
| Auditoría retroactiva Recuperación 2026-05-19 | **Docente** | El docente solicitó re-revisar penalizaciones al Equipo 4 que resultaron excesivas: (a) Libs penalizada por re-import y bare except — son detalles de estilo, no de elección/uso de librerías; (b) Diálogos penalizado por "faltan diálogos de error" — el uso de 2 `askyesno` con iconos diferenciados es comparable al de otros equipos; (c) JSON penalizado por "falta esquema de validación" — exigencia que no se aplicó a Aterrizaje, inconsistencia transversal; (d) Reportes — el save automático cada 15s es persistencia real, no ausencia de reportes; (e) DB — castigo excesivo de una decisión arquitectónica válida (JSON acumulativo en lugar de SQLite). Notas finales actualizadas en su sección. |
| Auditoría retroactiva Aterrizaje 2026-05-19 | **Docente** | El docente identificó que el módulo recibió múltiples penalizaciones menores de -1 en criterios donde el código en realidad cumple. Reinterpretaciones aplicadas: (a) los 3 métodos `leer_datos/obtener/read` no son redundancia sino **interface pública con múltiples puntos de entrada** pensada para que otros módulos consuman del reader; (b) los aliases `temp_int → temperatura → temp_interna` son **defensive coding** contra variabilidad del ESP32, no señal de IA confundida; (c) bare except, imports duplicados y mezcla `tk.messagebox/messagebox` son estilo, no defectos funcionales; (d) la validación previa de sensores que bloquea ACTIVAR es la **única implementación de safety interlock** del proyecto. Nota final actualizada en su sección. |
| Detección de IA en código estudiantil | IA (heurísticas) | La IA identificó patrones estadísticamente asociados con generación asistida (docstrings con marcos ASCII uniformes, métodos duplicados, comentarios "esta es la corrección nueva", paletas de colores hardcodeadas, etc.). **Estos indicadores son probabilísticos, no concluyentes.** No se penaliza a ningún equipo por "haber usado IA" — la nota se basa en si el código cumple la consigna. |
| Validación funcional | IA + docente | Se ejecutó `python main.py` + simulador para verificar que la app levanta sin errores. La IA construyó un simulador UDP (`simulador_esp32.py`) para emular el ESP32. |
| Redacción del informe | IA (borrador) → Docente (revisión y firma) | La IA produjo este documento; el docente lo revisó, ajustó tono, corrigió interpretaciones, y aprueba la versión final como propia. |

### Limitaciones que el lector debe conocer

1. **La detección de "uso de IA por equipo" es heurística**, no forense. No tenemos acceso a logs de IDE, historial de prompts ni metadata de generación. Los indicadores son patrones de superficie. Por eso el informe usa palabras como "ALTA/MEDIA/BAJA probabilidad", nunca "definitivamente usado IA". **Ningún equipo es sancionado por el indicador de IA en sí mismo** — solo por incumplimiento de objetivos técnicos.
2. **Las notas finales son del docente.** La IA propuso; el docente decidió. Cualquier apelación se dirige al docente, no al modelo.
3. **El simulador y este informe quedan en el repositorio** para que los equipos puedan auditar el trabajo y proponer correcciones documentadas.

### Por qué se publica este disclaimer

Si pedimos al estudiantado que sea transparente sobre el uso de IA en sus entregas, el equivalente desde la cátedra es declarar abiertamente cuándo usamos IA para evaluar. El objetivo es **modelar la práctica académica que queremos ver**: la IA es una herramienta legítima cuando se documenta y cuando el responsable humano valida y firma.

---

*Evaluación elaborada el 2026-05-18 y re-evaluada el 2026-05-19 tras las re-entregas de los Equipos 1 (Despegue) y 2 (Despliegue). Las notas son finales salvo apelación documentada al docente. El uso de IA en la elaboración de este informe se declara en la sección Disclaimer anterior.*
