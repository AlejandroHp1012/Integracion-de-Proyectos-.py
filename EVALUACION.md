# EVALUACIÓN FINAL — Programación II

**Proyecto:** Integración de Proyectos — Misión Alpha-001 (Centro de Control de Cohete)
**Repositorio:** `https://github.com/AlejandroHp1012/Integracion-de-Proyectos-.py`
**Fecha de evaluación:** 2026-05-18
**Evaluador:** Docente cátedra Prog. II
**Commit evaluado:** `ba9cf07` (post pull del 2026-05-18)

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

**Archivo:** `modulo_despegue.py` (554 líneas)
**Cuadrante:** Q1 (cyan)
**Responsable declarado:** "MAVLink integrado vía ESP32"

## Análisis técnico

El módulo presenta un wizard de 5 pasos visualmente impecable: encender sistema → conectar cohete → verificar señal RF → confirmar enlace → cuenta regresiva → liftoff/abort. Estéticamente es el más cuidado: paleta cyan/ámbar coherente, animaciones, telemetría con tags, indicadores LED, etc.

**El problema crítico:** TODO el módulo es teatro. No hay comunicación real con ESP32 a pesar del header que dice "MAVLink integrado".

### Hallazgos graves

1. **`_start_wifi_sim()` líneas 391-409** — la "intensidad de señal WiFi" se inventa con `random.randint(-3, 5)`. No abre ningún socket.
2. **`_start_wind_sim()` líneas 411-424** — la velocidad del viento se inventa con `random.uniform(0, 45)`.
3. **`_verify_done()` línea 487** — la "calidad de señal RF" se inventa con `random.randint(70, 99)`. La verificación siempre va a estar entre 70 y 99 (pasa siempre el threshold de 80% en ~80% de los casos por puro azar).
4. **`_do_connect()` línea 463 + `_connect_done()` línea 472** — el botón "CONECTAR" solo dispara un `after(2000, ...)` que pone un label en verde. No abre socket, no manda nada, no escucha. Es un timer cosmético.
5. **`_do_launch()` línea 516** — el objetivo declarado del módulo era enviar la señal de despegue al ESP32. En lugar de eso, se ejecuta `_cdown()` que solo cambia el label local `T-10, T-9, ...`. **Nunca se transmite la orden de lanzamiento.**
6. No usan `shared_state` para publicar el estado del sistema, aunque `shared_state.py` tiene un slot `"launch_state"` esperándolo.

### Señales de uso de IA

- Estructura de docstring decorativa (`╔══...══╗`) consistente con generación AI.
- Comentarios redundantes en cada bloque (`# ── Reloj ──`, `# ── Botón ──`).
- Sobrecarga visual: 6 subsistemas decorativos (BATERIA/GPS/GIROSCOPIO/...) que todos cambian a "OK" al mismo tiempo, sin lógica real.
- Animación de cuenta regresiva con colores por umbral (`RED if n<=3 else AMBER if n<=6 else CYAN`) — patrón típico de IA.
- **Veredicto IA:** ALTA probabilidad de generación asistida por IA, con poca o nula adaptación al objetivo real del módulo.

## Calificación por criterio

| # | Criterio | Pts | Observaciones |
|---|---|---:|---|
| 1 | Repositorio Código | 10 | Está en el repo, commits del equipo presentes |
| 2 | Uso de Librerías | 10 | `tkinter`, `ttk`, `messagebox`, `random`, `time`, `threading` — todas pertinentes y usadas correctamente. La crítica al uso de `random` para simular telemetría pertenece al criterio ESP32 (donde ya se penalizó fuerte); no se penaliza dos veces |
| 3 | UI/UX (Pruebas) | 9 | La interfaz corre, se renderiza completa, animaciones fluidas, sin crashes |
| 4 | Uso correcto de controles | 9 | Buttons, Labels, Canvas para barras WiFi, Progressbar para señal, Text con scroll para telemetría |
| 5 | Cajas de diálogo | 9 | `messagebox.askyesno` antes de apagar, lanzar, abortar — uso correcto con `icon=warning` |
| 6 | Eventos y propiedades formulario | 9 | `after()` para reloj/simulaciones, callbacks por botón, cambio de `state` de widgets, `textvariable` con `StringVar` |
| 7 | Estructura de datos (JSON) | 0 | El módulo no maneja JSON. Aunque sea su rol, no hay save/load |
| 8 | Reportes | 5 | Solo log en pantalla (`telem_text`). No hay exportación CSV/TXT ni persistencia |
| 9 | Control y acceso a datos (DB) | 0 | No hay base de datos. Toda la sesión se pierde al cerrar |
| 10 | **Integración ESP32-S3** | **1** | **CRÍTICO**: 100% simulado con `random`. Botón LANZAR no manda nada. No hay socket abierto. El objetivo principal del módulo está incumplido |

### NOTA FINAL: **62/100**

### Comentario para el equipo

El trabajo visual es excelente — la UI es la más pulida de los 4 cuadrantes. **Pero el objetivo del módulo no se cumplió.** Su rol era **enviar la señal de despegue al ESP32** y **leer su estado real**. Lo que entregaron es un mockup animado: la señal WiFi, el viento, la verificación de señal RF y la cuenta regresiva son todos `random.randint(...)`. El botón "ACTIVAR DESPEGUE" debería abrir un socket o serial al ESP32 y mandar un comando `LAUNCH` — en lugar de eso, solo cuenta hacia atrás localmente. La consigna decía "no simular, controlar y monitorear el cohete real". Les recomendamos: (a) eliminar `_start_wifi_sim` y `_start_wind_sim`, (b) leer wifi/viento desde `shared_state` o desde un UDP listener, (c) que `_do_launch` envíe `{"cmd":"launch"}` por socket al ESP32, (d) escribir el estado del sistema en `shared_state["launch_state"]` para que recuperación lo lea.

---

# Equipo 2 — DESPLIEGUE

**Archivo:** `modulo_despliegue.py` (1455 líneas — el más extenso)
**Cuadrante:** Q2 (naranja)

## Análisis técnico

Es el módulo más completo en funcionalidad: tracking de 6 fases de vuelo, gráficas de altitud/velocidad con canvas, paracaídas animado, persistencia JSON con validación de esquema, exportación CSV/TXT, reset con confirmación, cronómetro de fase, umbral configurable, manejo del cierre de ventana. Esfuerzo visible y trabajo serio.

### Lo que está bien

- **Persistencia JSON con esquema validado** (`_cargar_sesion` línea 1002): valida que existan `meta`, `estado`, `historial`; valida campos requeridos; valida que la fase cargada sea válida. Manejo de errores con `messagebox.showerror`.
- **Exportación dual** (CSV o TXT) según extensión elegida en `filedialog.asksaveasfilename`.
- **Confirmación al cerrar** (`_on_closing` línea 1105) con `askyesnocancel` ofreciendo guardar antes de salir — UX muy cuidada.
- **UDP listener real** en el bloque `if __name__ == "__main__"` línea 1380 con cálculo de fase basado en delta de altitud (detección de apogeo por 3 lecturas consecutivas a la baja).
- **Reset con re-arranque de DEMO opcional** (`_reset_mision` línea 1121) — vuelve a STANDBY y pregunta si lanzar demo.

### Hallazgos

1. **`TELEM_DEMO` líneas 59-72** — array hardcodeado con 12 keyframes de "telemetría simulada". El método `_demo_tick` (línea 1292) los reproduce como si fueran datos del cohete. Aunque está desactivado por defecto en el `__main__`, sigue presente como ruta de simulación.
2. **UDP listener inactivo en main.py** — el listener UDP está dentro de `if __name__ == "__main__"`, por lo que cuando `main.py` importa el módulo, ese bloque no corre y el cuadrante queda esperando datos que nunca llegan. **Falla de integración crítica.**
3. **Re-implementan servidor UDP** en lugar de delegar en `shared_state.py`. Es código duplicado con aterrizaje y recuperación.

### Señales de uso de IA

- Comentarios decorativos abundantes (`# ── MEJORAS ───`, `# ══════════════════════`).
- Bloques marcados explícitamente como `# ── LÓGICA ORIGINAL (sin cambios) ─────` (líneas 873, 919) — indica que el equipo o una IA pegó código encima del original.
- Helper `_lighten` con un diccionario hardcodeado de 9 colores en lugar de un cálculo HSL real.
- **Veredicto IA:** Probable apoyo de IA, pero con clara intervención y trabajo del equipo. Hay decisiones de diseño coherentes y una arquitectura sostenida a lo largo de 1455 líneas que sugiere comprensión.

## Calificación por criterio

| # | Criterio | Pts | Observaciones |
|---|---|---:|---|
| 1 | Repositorio Código | 10 | Está en repo, varios commits del equipo |
| 2 | Uso de Librerías | 10 | `tkinter`, `ttk`, `messagebox`, `filedialog`, `time`, `math`, `json`, `os`, `datetime`, `csv` — uso pertinente |
| 3 | UI/UX (Pruebas) | 10 | Layout en 3 columnas, paracaídas animado, gráficas en canvas, scroll, indicadores LED de fase, paleta clara consistente |
| 4 | Uso correcto de controles | 10 | Entry con placeholder + bind FocusIn/FocusOut, StringVar, Text con tags de color, Progressbar implícito en gráficas, Treeview no usado pero hay buen uso de Canvas |
| 5 | Cajas de diálogo | 10 | `askokcancel`, `askyesno`, `askyesnocancel`, `showinfo`, `showerror`, `showwarning` — uso variado con iconos apropiados |
| 6 | Eventos y propiedades formulario | 10 | `after(120, _loop)`, `bind("<FocusIn>")`, `bind("<FocusOut>")`, `bind("<Return>")`, `protocol("WM_DELETE_WINDOW")`, `state="disabled/normal"` |
| 7 | Estructura de datos (JSON) | 10 | Save/load con metadata, estado, historial, eventos. Validación de esquema completa al cargar. Indent=2, ensure_ascii=False |
| 8 | Reportes | 10 | Log en pantalla con tags de color, export a TXT (con header) o CSV (con DictWriter). Mensaje de confirmación post-export. Límite de 500 eventos en memoria |
| 9 | Control y acceso a datos (DB) | 4 | No usa SQLite — la persistencia es solo JSON. Para un módulo de telemetría sería esperable. Lo salva parcialmente la robustez del JSON |
| 10 | **Integración ESP32-S3** | **3** | Tienen listener UDP real con cálculo de fase, **pero está dentro del `__main__` block** → inactivo cuando se integra via main.py. Usan TELEM_DEMO como ruta de simulación. No usan `shared_state` |

### NOTA FINAL: **87/100**

### Comentario para el equipo

Excelente trabajo. Funcionalmente es el módulo más completo: persistencia JSON, exportación dual, confirmaciones, reset, cronómetro por fase, todo correcto. La UI/UX es de nivel profesional. **Lo que les baja la nota es la integración:** su listener UDP solo se activa cuando ejecutan `python modulo_despliegue.py` standalone, pero cuando `main.py` los importa, ese código nunca corre y su cuadrante queda ciego. La solución es **sacar el listener UDP del `__main__` block** y arrancarlo en `__init__` (igual que hizo el equipo 3 con `UdpReader`). Además, eliminen `TELEM_DEMO` y `_demo_tick` — la consigna era no simular. Si quieren agregar persistencia robusta, SQLite con una tabla `eventos` y otra `fases` mejoraría el criterio de DB.

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

### Hallazgos negativos

1. **Imports duplicados líneas 22-25**: `import socket`, `import threading`, `import json`, `import time` repetidos después de la línea 17 — código mal limpiado.
2. **Tres métodos haciendo lo mismo** (`leer_datos`, `obtener`, `read` — líneas 106-116): retornan exactamente `self._ultimo_dato`. Señal clara de que se probaron tres nombres distintos sin saber cuál era el esperado.
3. **Comentario "¡Esta es la corrección nueva!" línea 66** — comentario delator de parche en producción.
4. **Línea 989** `int((time.time() - (_reader._ultimo_paquete or time.time())) * 0)` — multiplicación por 0 hace que la variable siempre sea 0. Código muerto.
5. **Acceso directo `d["gy"]` líneas 818-832** sin `.get()` — si llega un paquete con campos faltantes, KeyError. Frágil. Se salva parcialmente porque el UdpReader expone `datos = {}` si nada llegó, lo que también daría KeyError, pero solo se ejecuta si `_reader.conectado` es True y los paquetes están llegando.
6. **`tk.messagebox.askyesno` línea 322** — funciona en Python 3 por efecto colateral del `from tkinter import messagebox` línea 14, pero es estilo incorrecto. Debió ser `messagebox.askyesno(...)`.
7. **Bare `except: pass` líneas 83-85** — silencia errores sin loguear.

### Señales de uso de IA

- Tres aliases idénticos para el mismo método (`leer_datos`, `obtener`, `read`) → muy característico de IA que no sabe cuál de los nombres usa el caller.
- Mezcla de patrones: en algunos lugares usa `messagebox.askyesno`, en otros `tk.messagebox.askyesno`. Inconsistencia típica de copy-paste de fuentes mezcladas.
- Estructura defensiva con aliases `temp_int → temperatura → temp_interna` (3 veces el mismo dato) sugiere reescritura por IA sin entender el flujo.
- **Veredicto IA:** Apoyo parcial de IA, pero el corazón del módulo (UdpReader + SQLite + UI estructurada) muestra comprensión. El equipo entendió el objetivo y lo ejecutó bien.

## Calificación por criterio

| # | Criterio | Pts | Observaciones |
|---|---|---:|---|
| 1 | Repositorio Código | 10 | En el repo, varios commits |
| 2 | Uso de Librerías | 9 | 10 librerías pertinentes y bien usadas (tkinter, ttk, messagebox, math, sqlite3, json, time, datetime, socket, threading). 2 líneas duplicadas (`json`/`time` líneas 24-25) son cosméticas, sin penalización. -1 por bare except sin logging (línea 84) |
| 3 | UI/UX (Pruebas) | 9 | Renderiza completo, 3 columnas, perfil de descenso animado, brújula de actitud, LEDs de sensor. Penalización menor por tamaño compacto |
| 4 | Uso correcto de controles | 9 | Treeview con scrollbars en historial, Entry para límite, Canvas con animaciones, botones con estados |
| 5 | Cajas de diálogo | 8 | `messagebox.askyesno` en limpiar BD con `parent=self` (modal correcto, uso técnicamente impecable). Variedad limitada — solo 1 tipo de diálogo, sin `showinfo`/`showerror`/`showwarning` para feedback al operador |
| 6 | Eventos y propiedades formulario | 9 | `after(100, _loop)`, threading para validación, `state="disabled/normal"`, `cv.delete("all")` para refresh |
| 7 | Estructura de datos (JSON) | 9 | Persisten como JSON dentro del campo `datos` de SQLite, con `json.dumps`. Mapeo de aliases en el reader |
| 8 | Reportes | 9 | Ventana de historial completa con tabla, filtro, totales. Log de telemetría en panel. Falta exportación a archivo |
| 9 | Control y acceso a datos (DB) | 10 | SQLite real con esquema, INSERT periódico, SELECT con ORDER y LIMIT, ventana visual con Treeview, botón LIMPIAR. Ejemplar |
| 10 | **Integración ESP32-S3** | **9** | UdpReader activo desde el import, hilo daemon, validación previa de sensores que bloquea el ACTIVAR, lectura real sin simulación, mapeo defensivo de campos del ESP32. -1 solo por el acceso `d["clave"]` sin `.get()` que podría romper con paquetes parciales |

### NOTA FINAL: **91/100**

### Comentario para el equipo

Excelente trabajo y el ejemplo a seguir en integración. Su módulo es el único que cumple realmente la consigna: leer datos reales del ESP32, persistirlos, mostrarlos y exigir validación previa de sensores. La cátedra los reconoce públicamente como referencia para los demás equipos. **Limpiezas pendientes:** (a) borrar los imports duplicados de `json` y `time` en las líneas 24-25, (b) quedarse con UN solo método de lectura (`leer_datos` o `obtener`, no los tres), (c) cambiar `d["gy"]` por `d.get("gy", 0.0)` para tolerar paquetes incompletos, (d) reemplazar `except Exception: pass` por logging real, (e) borrar el `int(... * 0)` de la línea 989, (f) agregar variedad de diálogos (`showinfo` al ACTIVAR, `showerror` ante fallo de sensores). Con eso pueden llegar a 96-98/100.

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
- Headers decorativos más sencillos que despegue.
- **Veredicto IA:** Apoyo de IA presente pero claramente menor que en despegue. El trabajo de Haversine, bearing y `shared_state.py` demuestran entendimiento real del dominio y decisiones arquitectónicas propias.

## Calificación por criterio

| # | Criterio | Pts | Observaciones |
|---|---|---:|---|
| 1 | Repositorio Código | 10 | En el repo, commits del equipo. Aportaron además `shared_state.py` |
| 2 | Uso de Librerías | 8 | `tkinter`, `math`, `datetime`, `time`, `threading`, `json`, `os`, `socket` — todo pertinente. `threading.Lock` correctamente usado en shared_state. Re-import adentro de método (-1), bare except (-1) |
| 3 | UI/UX (Pruebas) | 9 | Radar con barrido, mapa con grilla, LEDs animados, barras WiFi — todo renderiza bien. Tipografía consistente |
| 4 | Uso correcto de controles | 9 | Canvas usado extensivamente y bien (radar, mapa, LEDs, wifi bars). Text con scroll para consola. Button con `cursor="hand2"` |
| 5 | Cajas de diálogo | 8 | `messagebox.askyesno` al activar/desactivar sistema con icon=WARNING/QUESTION. Faltan diálogos de error en caso de fallo de socket |
| 6 | Eventos y propiedades formulario | 9 | `after(100, _loop)`, threading para UDP, cambios de `state`/text/color en botones |
| 7 | Estructura de datos (JSON) | 8 | Parse de JSON entrante con validación de `type`, guardado acumulativo con `json.load + append + json.dump`. Falta esquema de validación |
| 8 | Reportes | 7 | Log en consola, save JSON cada 15s. Falta export manual o ventana de historial visible |
| 9 | Control y acceso a datos (DB) | 4 | No usa SQLite. Solo JSON acumulativo. Para un módulo de seguimiento sería esperable BD |
| 10 | **Integración ESP32-S3** | **10** | Listener UDP real con `SO_REUSEADDR`, Haversine real, bearing real, filtro antirruido, parsing correcto. **Plus arquitectónico:** crearon `shared_state.py` como bus de datos pensado para que los 4 módulos consuman desde un punto único. El cálculo GPS es el más sofisticado del proyecto |

### NOTA FINAL: **82/100**

### Comentario para el equipo

Su módulo tiene los cálculos más sofisticados de todo el proyecto: la fórmula Haversine, el bearing GPS con corrección de eje, y el filtro antirruido están muy bien resueltos. **Y `shared_state.py` es el aporte arquitectónico más maduro del trabajo entero** — pensaron en cómo debían conectarse los 4 módulos y propusieron un bus thread-safe correcto. Que los demás equipos no lo hayan usado **no los penaliza a ustedes**, sino a ellos (lo descontamos en sus secciones).

**Limpiezas pendientes:**

1. Borrar el comentario `# <--- CAMBIA ESTO POR TU LONGITUD` de la línea 770 — la constante `BASE_LON` ya está bien definida arriba, el comentario es residuo de pruebas que conviene limpiar.
2. Sacar el `import shared_state as SS` que tienen adentro del método `_escuchar_udp` (ya está al top del archivo).
3. Reemplazar `except: pass` por logging real para no comerse bugs propios.
4. Renombrar `_dibujar_mapa_sim` → `_dibujar_mapa` (el sufijo `_sim` quedó del prototipo).

**Para subir la nota considerablemente:** agreguen SQLite con una tabla `seguimiento` (`id, timestamp, lat, lon, alt, distancia`) y una ventana de historial similar a la del equipo 3. Con eso, el criterio DB sube de 4 a 10 y la nota final llega cerca de 90.

---

# RESUMEN GENERAL

## Tabla comparativa

| Equipo | Módulo | Repo | Libs | UI | Ctrl | Diál | Evt | JSON | Rep | DB | ESP32 | **TOTAL** |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | DESPEGUE | 10 | 10 | 9 | 9 | 9 | 9 | 0 | 5 | 0 | 1 | **62** |
| 2 | DESPLIEGUE | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 4 | 3 | **87** |
| 3 | ATERRIZAJE | 10 | 9 | 9 | 9 | 8 | 9 | 9 | 9 | 10 | 9 | **91** |
| 4 | RECUPERACIÓN | 10 | 8 | 9 | 9 | 8 | 9 | 8 | 7 | 4 | 10 | **82** |

## Ranking

1. **Equipo 3 — Aterrizaje: 91/100** — Ejemplar en integración ESP32 y persistencia
2. **Equipo 2 — Despliegue: 87/100** — Más funcionalidad y mejor UX, fallido en integración
3. **Equipo 4 — Recuperación: 82/100** — Mejores cálculos del proyecto + aporte arquitectónico (`shared_state.py`)
4. **Equipo 1 — Despegue: 62/100** — Mejor estética, peor cumplimiento del objetivo

## Hallazgos transversales

### Integración ESP32 (la consigna maestra)

| Equipo | ¿Lee datos reales? | ¿Manda comandos? | ¿Tiene simulación interna? |
|---|---|---|---|
| Despegue | ❌ No | ❌ No | ✅ Sí, con `random` |
| Despliegue | ⚠️ Solo standalone | ❌ No | ✅ Sí, `TELEM_DEMO` |
| Aterrizaje | ✅ Sí (UDP siempre activo) | ❌ No (rol de monitor) | ❌ No |
| Recuperación | ✅ Sí (UDP con fix) | ❌ No (rol de monitor) | ❌ No |

### Uso de IA detectado

- **Despegue:** ALTA probabilidad de generación AI con poca adaptación. Comentarios decorativos, simulaciones random, código de presentación sin lógica real.
- **Despliegue:** MEDIA. Mucho código real pero con marcadores de re-edición ("LÓGICA ORIGINAL (sin cambios)").
- **Aterrizaje:** BAJA-MEDIA. Tiene aliases delatores (3 métodos hacen lo mismo) e imports duplicados, pero la lógica del UdpReader y SQLite muestra comprensión.
- **Recuperación:** BAJA-MEDIA. Helpers comparten estilo con aterrizaje (posible IA común), pero el aporte de `shared_state.py` y los cálculos de Haversine/bearing requieren entendimiento real del problema.

> ⚠️ La detección de IA en código estudiantil es **probabilística**, no determinista. Los indicadores listados son patrones estadísticamente asociados con generación asistida, pero NO prueban que el código haya sido generado por IA sin intervención del equipo. Se incluyen como contexto para la cátedra, no como acusación.

### Bugs identificados que merecen corrección

| Equipo | Bug | Línea |
|---|---|---|
| Despegue | Toda la "telemetría" es `random.*` | 391-424, 487 |
| Despliegue | Listener UDP en `__main__` → inactivo al integrar | 1304 |
| Aterrizaje | Imports duplicados | 22-25 |
| Aterrizaje | 3 métodos hacen lo mismo (`leer_datos/obtener/read`) | 106-116 |
| Aterrizaje | Multiplicación inútil por 0 | 989 |
| Aterrizaje | Acceso `d["clave"]` sin `.get()` | 818-832 |
| Recuperación | Re-import dentro de método | 809 |
| Recuperación | Bare except en 3 lugares | 811, 814, 818-819 |
| Arquitectura | `shared_state` no se llena en `main.py` (responsabilidad de los publishers, no de Recuperación que es consumer) | — |

### Arquitectura del proyecto (visión integral)

El proyecto **no fue diseñado en conjunto**. Cada equipo trabajó aislado y el contrato de integración solo dice "su clase recibe un `tk.Frame`". Resultado:

- Cuatro escuchas UDP distintos (despegue+despliegue+aterrizaje+recuperación), tres de los cuales bindarían al mismo puerto 8080 si estuvieran todos activos simultáneamente.
- **El equipo 4 propuso `shared_state.py` como solución a este problema** — un bus thread-safe que los demás módulos podrían haber usado para evitar listeners duplicados. Quedó implementado pero solo Recuperación lo consume.
- Aterrizaje toma el puerto 8080 al importar, despliegue tiene su listener inactivo en `__main__`. Solo aterrizaje y recuperación reciben datos reales al integrar (post fix de puerto).

**Recomendación arquitectónica para futuros proyectos:** definir el contrato de integración antes de repartir trabajo. Aprovechando lo que el equipo 4 ya entregó, una arquitectura natural sería: **un solo listener UDP central que publique al `shared_state`**, y los módulos solo leen del bus.

## Recomendaciones de devolución

1. Hacer una demo conjunta donde los 4 cuadrantes muestren datos reales del simulador (el simulador queda en el repo como `simulador_esp32.py` para que los equipos prueben).
2. Insistir en la regla **"no simular con random"** para el siguiente trabajo.
3. Reforzar el concepto de **separación entre __main__ y módulo importado** — el equipo 2 perdió 10 puntos por este detalle.
4. Premiar al equipo 3 públicamente como referencia de integración correcta.
5. **Reconocer al equipo 4 por el aporte de `shared_state.py`** y proponer que sea adoptado por los demás equipos en la re-entrega.

---

## Archivos del proyecto evaluados

- `main.py` (149 líneas) — Ventana principal, integración 2x2. Sin observaciones, cumple con su rol de orquestador.
- `shared_state.py` (72 líneas) — Bus thread-safe creado por equipo 4. Buen diseño, infrautilizado por los demás equipos.
- `modulo_despegue.py` (554 líneas) — Equipo 1
- `modulo_despliegue.py` (1455 líneas) — Equipo 2
- `modulo_aterrizaje.py` (1161 líneas) — Equipo 3
- `modulo_recuperacion.py` (829 líneas) — Equipo 4

## Herramientas de evaluación creadas

- `simulador_esp32.py` (567 líneas) — Emisor UDP que reemplaza al ESP32-S3 para validar la UI sin hardware. **No es entregable de los equipos.** Mantenerlo en el repo para futuras evaluaciones / re-pruebas. Incluye listener de comandos uplink (puerto 9090) que permite a los equipos enviar `{"cmd":"launch"}` y similares para arrancar la misión simulada.
- `SIMULADOR_README.md` — Documentación del simulador para los equipos, con snippets de Python por módulo.

## Modificación menor aplicada por el docente

- `modulo_recuperacion.py` — Cambio de puerto UDP 8080 → 8081 para evitar conflicto con aterrizaje. Cambio puntual de 4 líneas. **No se penalizó al equipo por este detalle**, se considera ajuste menor de integración corregible en segundos.

---

## Disclaimer — Transparencia sobre el uso de IA en esta evaluación

> Esta sección se incluye por **ética académica**: si la cátedra exige al alumnado declarar el uso de IA, el docente también debe declararlo.

**Esta evaluación fue elaborada de manera conjunta entre el docente y un asistente de IA (Claude Opus 4.7 de Anthropic, vía Claude Code).**

### Cómo se dividió el trabajo

| Rol | Responsable | Tareas |
|---|---|---|
| Lectura y análisis técnico | IA + docente | La IA leyó las ~4220 líneas de código de los 4 módulos + `shared_state.py` + `main.py`, identificó patrones, listó bugs y señales de IA. El docente verificó hallazgos puntuales. |
| Definición de criterios | **Docente** | Los 10 criterios (Repo, Libs, UI, Ctrl, Diál, Evt, JSON, Rep, DB, ESP32) y la regla maestra "no simular con random" son del docente. |
| Ponderación inicial | IA (propuesta) → Docente (decisión final) | La IA propuso una primera asignación de puntos. El docente revisó, ajustó y aprobó. **Tres correcciones puntuales aplicadas por el docente durante la revisión:** (1) Recuperación pasó de 79 a 82 — el docente reevaluó las penalizaciones del comentario hardcodeado (era evidencia de iteración, no de código sin probar) y del `shared_state.py` (es un aporte arquitectónico positivo, no una falla); (2) Aterrizaje pasó de 88 a 91 — el docente detectó penalización doble en Libs (los imports duplicados de `json`/`time` eran cosméticos) y una crítica errónea en Diálogos ("estilo inconsistente" cuando solo había un uso); (3) Despegue pasó de 60 a 62 — el docente eliminó la doble penalización por uso de `random` (ya estaba castigado fuerte en ESP32, no corresponde castigarlo también en Libs). |
| Detección de IA en código estudiantil | IA (heurísticas) | La IA identificó patrones estadísticamente asociados con generación asistida (docstrings decorativos uniformes, métodos duplicados, comentarios "esta es la corrección nueva", paletas de colores hardcodeadas, etc.). **Estos indicadores son probabilísticos, no concluyentes.** No se penaliza a ningún equipo por "haber usado IA" — la nota se basa en si el código cumple la consigna. |
| Validación funcional | IA + docente | Se ejecutó `python main.py` + simulador para verificar que la app levanta sin errores. La IA construyó un simulador UDP (`simulador_esp32.py`) para emular el ESP32. |
| Redacción del informe | IA (borrador) → Docente (revisión y firma) | La IA produjo este documento; el docente lo revisó, ajustó tono, corrigió interpretaciones, y aprueba la versión final como propia. |

### Limitaciones que el lector debe conocer

1. **La detección de "uso de IA por equipo" es heurística**, no forense. No tenemos acceso a logs de IDE, historial de prompts ni metadata de generación. Los indicadores son patrones de superficie. Por eso el informe usa palabras como "ALTA/MEDIA/BAJA probabilidad", nunca "definitivamente usado IA". **Ningún equipo es sancionado por el indicador de IA en sí mismo** — solo por incumplimiento de objetivos técnicos.
2. **Las notas finales son del docente.** La IA propuso; el docente decidió. Cualquier apelación se dirige al docente, no al modelo.
3. **El simulador y este informe quedan en el repositorio** para que los equipos puedan auditar el trabajo y proponer correcciones documentadas.

### Por qué se publica este disclaimer

Si pedimos al estudiantado que sea transparente sobre el uso de IA en sus entregas, el equivalente desde la cátedra es declarar abiertamente cuándo usamos IA para evaluar. El objetivo es **modelar la práctica académica que queremos ver**: la IA es una herramienta legítima cuando se documenta y cuando el responsable humano valida y firma.

---

*Evaluación elaborada el 2026-05-18. Las notas son finales salvo apelación documentada al docente. El uso de IA en la elaboración de este informe se declara en la sección Disclaimer anterior.*
