# Changelog — HJ ULP PRO

Todos los cambios notables del bot se documentan aquí.

## [4.2.9] — /imap <remitentes>: hasta 10 correos remitentes por comando (como keywords)

### 🔧 Corrección según el OWNER (aclaración del «máximo 10»)
- En v4.2.8 el «máximo 10» se interpretó como tope de **resultados**; el OWNER aclaró: el 10 es para los **correos remitentes del comando**, igual que las 10 keywords.
- **Ahora**:
  - `/imap r1@dom.com, r2@dom.com, ...` — **hasta 10 remitentes** separados por coma (si pasas más → nuevo aviso «Máximo 10 remitentes permitidos»).
  - **Los resultados ya NO tienen tope**: se reportan **TODOS** los buzones que tengan mensajes de cualquiera de esos remitentes.
  - Compatibilidad total: `/imap un-solo-remitente@dom.com` sigue funcionando igual (v4.2.8).

### ⚙️ Motor (imap_checker.py)
- **Búsqueda IMAP `FROM` con `OR` anidado**: para N remitentes se genera una única query `OR FROM "r1" OR FROM "r2" FROM "r3"...` — 1 solo SEARCH por buzón aunque busques 10 remitentes (rápido y preciso).
- Buzón sin mensajes de NINGUNO de los remitentes → descartado (no es hit); `bad_accounts.txt` aclara *no messages from senders*.
- Eliminado el corte `max_hits` (ya no se cancelan chequeos pendientes por tope de resultados).

### 📦 ZIP y textos
- Carpeta `sender/`: informe único — 1 remitente → `remitente_dom.txt`; varios → `senders_N.txt` con cabecera `MESSAGES FROM ANY OF: ...` (buzón | nº mensajes | hasta 5 asuntos/fechas).
- Caption «IMAP + REMITENTES» lista todos los remitentes consultados y el total de buzones (sin «máx. 10»).
- `imap_info` en **ES/EN/PT**: 4º modo con ejemplo multi-remitente y límite «10 keywords o 10 remitentes»; nuevo aviso `imap_too_many_senders`.

### 🧪 Verificación (IMAP simulado + FakeIMAP con OR real)
- 1 remitente → **12 hits sin tope** (antes se cortaba en 10) ✔ · 2 remitentes → unión 16 hits (12 de uno + 4 de otro) con query `OR FROM` verificada ✔ · remitente fantasma → 0 hits, todo descartado ✔ · modo clásico intacto (login OK = hit) ✔ · parseo: 1/varios remitentes, keywords, mixto→keywords, country, >10 → error ✔ · i18n es/en/pt con formatos nuevos + JSONs válidos ✔ · py_compile de los 4 módulos ✔

## [4.2.8] — /imap <remitente>: buzones con mensajes de un correo concreto (máx. 10)

### 📬 Nuevo modo del IMAP Checker
- **`/imap remitente@dominio.com`** (ej. `/imap disneyplus@trx.mail2.disneyplus.com`): encuentra **buzones que hayan recibido mensajes enviados por ese correo**.
  - Búsqueda IMAP nativa **`FROM "remitente"`** — precisa, no confunde el remitente con el cuerpo (a diferencia del `TEXT` de keywords).
  - **Máximo 10 buzones**: al alcanzar el tope se cancelan los chequeos pendientes y se detiene (ahorra conexiones y tiempo).
  - Un buzón válido pero **sin mensajes de ese remitente se descarta** (no aparece como hit); `bad_accounts.txt` aclara: *discarded (bad login or no messages from sender)*.
- El ZIP incluye carpeta **`sender/`** con cada buzón, su número de mensajes del remitente y hasta **5 asuntos/fechas de muestra**.
- Flujo idéntico a keywords: responde al .txt con el comando, o pon el comando primero y envía el .txt después (privado y grupos permitidos).
- `imap_info` actualizado en **ES/EN/PT** con el 4º modo, ejemplos y carpetas del ZIP.

### 🔍 Auditoría de botones vanosos (reporte del OWNER: «si no hay, no hagas nada»)
- Comparados **todos los callbacks de teclados** (`ui.py`) contra el dispatcher de callbacks: **0 callbacks muertos**, 0 botones sin efecto tras las limpiezas v4.2.5/4.2.7 — los `Button.url` (soporte/pagar/compartir) son acciones reales. **No se eliminó nada porque no queda nada vanoso.**

### 🧪 Verificación (IMAP simulado, 25 combos)
- Corte exacto a **10 hits** con cancelación de pendientes ✔ · sin tope encuentra los 12 con mensajes ✔ · modo clásico intacto (login OK = hit) ✔ · regex distingue email/keywords/country ✔ · textos y JSON ES/EN/PT ✔ · py_compile de los 4 módulos ✔

## [4.2.7] — SIN RESULTADOS solo sugiere «24h + Antiguos» si aún no se usó

### 🎯 Ajuste de experiencia (reporte real del OWNER)
- El aviso «⚠️ SIN RESULTADOS → 🔁 Reintenta con «24h + Antiguos»» aparecía **SIEMPRE**, incluso cuando el usuario **ya había buscado con «🗂️ 24h + Antiguos»**: sugerirle reintentar lo que ya escaneó es un aviso vanoso (y con el botón de reintento podía reescanear todo en bucle sin sentido).
- **Ahora**:
  - Búsqueda parcial («⚡ Últimas 24 horas» o «📅 Solo antiguos») sin resultados → aviso con la sugerencia + botón «🔁 Reintentar · 24h + Antiguos» (igual que antes).
  - Búsqueda «🗂️ 24h + Antiguos» sin resultados → aviso **sin sugerencia de reintento**: «📂 Ya se escanearon las bases «24h + Antiguos»» + «📨 Reporta la URL para revisión manual». El teclado queda con **«⚠️ Reportar URL» + «« Volver»** (sin el botón de reintentar).
- El reintento (`retry_all`) ejecuta con rango completo: si tampoco encuentra nada, cae automáticamente en esta nueva variante — **el bucle de reintentos vanosos queda cortado**.

### 🧪 Verificación (Telethon real, sin conexión)
- `Keyboards.no_results()` (parcial): 3 filas, serializa `ReplyInlineMarkup`, mantiene `retry_all`. ✔
- `Keyboards.no_results_exhausted()` (nuevo): 2 filas, serializa `ReplyInlineMarkup`, **sin** `retry_all`. ✔
- Texto `no_results_all` verificado en **ES/EN/PT** (con `{0}` formateado, sin sugerencia de reintento) + fallback ES en `locale.py` + JSON válidos. ✔

## [4.2.6] — Optimización: el bot ya no se congela durante las búsquedas

### 🐌 El bug (reporte real: 4 comandos ignorados + latencias de 68s)
- Durante una búsqueda (`/url …`), el bot **dejaba de responder a TODO** (`/ping`, `/start` en silencio) y al terminar llegaban todas las respuestas de golpe con latencias de 47–68 segundos.
- **Causa raíz**: el motor de búsqueda usaba `mmap.find()` en threads, pero las operaciones de mmap de Python **NO liberan el GIL** — un scan de GBs sostenía el GIL durante toda la llamada C y **congelaba el event loop** (nada del bot podía ejecutarse). Además, una «línea» corrupta de cientos de MB disparaba slice+strip+decode+lower de GBs en llamadas C indivisibles.
- **Medido**: un solo scan de 512MB congelaba el loop **337 ms**; en el VPS con archivos de GBs y 16 workers en paralelo, la congelación era continua durante toda la búsqueda.

### ⚡ Nuevo motor de búsqueda (chunked, misma semántica)
- Lecturas por **chunks de 16MB** con `open()/read()` — la syscall del SO **sí libera el GIL**; cada operación C queda acotada (~15-30ms máximo).
- **Detección por chunk**: si el keyword no está en el chunk (2 scans C case-insensitive), se salta el procesamiento de líneas por completo — velocidad de scan casi igual al mmap original.
- **Detección de frontera** con copia mínima de 3KB: keywords que cruzan el borde entre dos chunks nunca se pierden.
- **Líneas gigantes** (dumps corruptos/binarios > 8MB): se escanean por ventanas acotadas y se saltan sin copiar GBs — el keyword detectado produce el resultado recortado al inicio de la línea (nunca líneas de cientos de MB en los resultados).
- La escritura del archivo de resultados (hasta 500k líneas) y el conteo de líneas van a un thread (`asyncio.to_thread`) — cero trabajo pesado en el loop.

### 🧪 Verificación (Python real, archivos sintéticos de hasta 512MB)
- **Corrección exacta** vs algoritmo original: keyword cruzando chunks, inicio/fin de archivo, sin `\n` final, líneas vacías, dedup, separadores MAIL (`:`, `|`, `;`), USERPASS, líneas gigantes y falsos positivos de frontera (3 bugs cazados y corregidos por la batería de tests antes del push).
- **Rendimiento**: congelación máxima del loop **31ms** durante un scan de 512MB (antes: 337ms por scan y congelación total en producción); búsqueda completa en ~1s por 512MB.
- El bot queda **100% responsivo durante las búsquedas**: `/ping`, `/start` y cualquier comando responden al instante mientras escanea.

## [4.2.5] — SIN RESULTADOS con reintento directo + limpieza de botones vanosos

### 🐛 El problema del flujo «⚠️ SIN RESULTADOS»
- El mensaje decía **«Prueba con «24h + Antiguos» o reporta la URL»**, pero el teclado **no tenía ningún botón para hacerlo**: el usuario tenía que darle a «Nueva búsqueda», reescribir el dominio, reelegir el rango de tiempo y reelegir el formato (4 pasos para repetir la misma búsqueda).
- El teclado además mostraba **«💎 Comprar VIP»**, vanoso: el VIP ya lo tiene quien es VIP y el FREE ya lo tiene en el menú principal.
- **Bug del reporte**: «⚠️ Reportar URL» siempre enviaba al admin `URL: Desconocido`, porque `temp_state` se limpia justo antes de ejecutar la búsqueda y el callback ya no encontraba el dominio.

### ✅ Fix
- **Botón «🔁 Reintentar · 24h + Antiguos»**: un solo toque reejecuta la MISMA búsqueda (mismo dominio, mismo formato) escaneando Descargas + Histórico (`t_opt='all'`), sin reescribir nada. Respeta reglas de acceso (FREE/VIP/grupo permitido), anti-superposición y no consume la búsqueda gratis si no hay resultados.
- `state.py`: nuevo `last_search` por usuario — contexto de la última búsqueda ejecutada (dominio, formato, chat, etc.).
- `handlers.py`: el reporte de URL ahora manda el **dominio real** buscado, no «Desconocido».
- **Botones vanosos eliminados**: «💎 Comprar VIP» y «🔍 Nueva búsqueda» fuera del teclado de SIN RESULTADOS (el menú principal ya los tiene); «👤 Mi cuenta» fuera del panel de Referidos (se abrió desde el menú que ya lo tiene).
- Texto del aviso actualizado en ES/EN/PT para que coincida con el botón («Reintenta con «24h + Antiguos»…»).

## [4.2.4] — CAUSA RAÍZ del error interno: teclados con filas anidadas

### 💥 El bug exacto (gracias al diagnóstico en vivo de v4.2.3)
- El OWNER recibía: `🔧 Diagnóstico: AttributeError: 'list' object has no attribute 'SUBCLASS_OF_ID'` — error de Telethon al **serializar un teclado donde una fila contiene una lista en vez de un botón**.
- **Afectados**: teclado principal FREE y OWNER/ADMIN (el botón «🌐 Idioma», definido como *fila*, estaba anidado dentro de la fila «📋 Comandos») y el panel «👥 Referidos» (el botón «« Volver» definido como lista de filas) — este último roto desde v4.2.0.
- VIP y SELLER funcionaban porque ahí el botón de idioma estaba como fila suelta.
- Resultado: `/start`, `/cmds` y el botón de referidos **explotaban al construir el teclado** → error interno.

### ✅ Fix
- `ui.py`: separados `LANG_BUTTON` (botón individual, para filas de 2) y `LANG_BTN` (fila de 1, VIP/SELLER); panel de referidos con la fila «« Volver» directa.
- `handlers.py`: red de seguridad en `/start` y `/cmd` — si el envío con teclado falla, **reintenta sin botones** para que la bienvenida nunca se pierda.

### 🧪 Verificación
- Los **20 teclados** del bot (los 4 roles × variantes de bono, admin, pagos, idiomas, referidos…) validados con `build_reply_markup` de **Telethon real**: 5 rotos antes → **0 rotos después**.
- Sin construcción manual de botones en handlers.py (todo sale de `ui.py` ya validado).

## [4.2.3] — Diagnóstico en vivo: el OWNER ve la causa exacta del error

### 🔎 Por qué salía «⚠️ Ocurrió un error interno»
- Tras v4.2.2, la garantía anti-mudez de `/start` **ya no deja al bot mudo**: si algo falla responde con el aviso de error. Ese mensaje confirma que el código llega al handler y que una **excepción del entorno del VPS** (datos de la DB, proceso, red de Telegram) se está capturando correctamente.
- Verificación end-to-end del handler `/start` con los módulos reales del bot y 8 escenarios (OWNER, FREE nuevo, FREE usado, referido, key inválida, grupo, DB con schema antiguo + migraciones, dict de fila vieja): **todos responden correctamente en entorno limpio** → el fallo es específico del entorno de producción.

### 🛡️ Blindaje del handler
- Accesos defensivos `user.get('search_count', 0)` en los 5 puntos que leían la columna con corchetes directos (`/start`, bienvenida tras canjear, reenvío tras `back_main`, «Mi cuenta» y cambio de idioma) — una fila antigua o migración fallida ya **no puede** provocar `KeyError`.
- `/cmd` y `/help` ahora también tienen try/except anti-mudez propio (antes un fallo los dejaba en silencio).

### 🔧 Diagnóstico en Telegram (solo admins)
- Cuando el error ocurre, el **OWNER ve la causa técnica exacta** en la propia respuesta: `🔧 Diagnóstico (solo admins): TipoError: mensaje` (recortado a 200 chars). Los usuarios normales siguen viendo solo el aviso genérico.
- Con esto no hace falta entrar al VPS a leer logs: el siguiente `/start` fallido muestra la causa raíz en el chat.

## [4.2.2] — Fix: comandos con @mención en grupos + /start a prueba de fallos

### 🐛 El bug real de «/start no responde»
- **Causa encontrada**: en grupos, Telegram envía los comandos con mención — `/start@MiBot` — y el patrón estricto introducido en v4.2.1 ya no los capturaba (el bot se quedaba mudo). Lo mismo ocurría con `/cmd@MiBot`, `/help@MiBot` y `/url@MiBot enlace` (esta última ¡desde la versión original!).
- **Fix**: todos los patrones de comandos de usuario aceptan ahora la forma `@mención`: `/start@MiBot`, `/cmds@MiBot`, `/cmd@MiBot`, `/help@MiBot`, `/url@MiBot enlace`, `/url@MiBot` (ayuda), `/id@MiBot` y `/canjear@MiBot HJ-XXX`.

### 🛡️ Garantía anti-mudez en /start
- El handler de `/start` está protegido con try/except: si cualquier error inesperado ocurre, el bot **responde con un aviso de error** (texto plano, a prueba de Markdown) en lugar de quedarse callado, y registra el traceback completo en el log.

### 🔧 Interno
- 1 clave nueva de localización (`start_error`) en ES/EN/PT (91 claves sincronizadas).
- Verificación end-to-end con Telethon real: los 23 handlers registran y despachan correctamente en privado y en grupos permitidos (con y sin @mención).

## [4.2.1] — Comandos que nunca se quedan mudos

### 🗣️ Correcciones de comandos
- **`/url` sin enlace ahora responde**: antes el bot ignoraba `/url` enviado sin argumento (silencio total). Ahora muestra una tarjeta de ayuda con el uso correcto — ✍️ Ejemplo: `/url ejemplo.com` — en el idioma del usuario.
- **`/cmds` restaurado**: `/start` y `/cmds` son ahora el mismo comando (alias el uno del otro). Da igual cuál escribas — ambos abren la bienvenida con el menú principal. `/cmd` y `/help` siguen mostrando la lista de comandos como siempre.

### 🔧 Interno
- Patrón de `/start` unificado a `/(start|cmds)(\s|$)` — más estricto (ya no captura texto como `/startup`) y compatible con deep links (`ref_<id>`, keys `HJ-`).
- Nuevo handler `/url\s*$` que solo captura el comando vacío, sin interferir con la búsqueda: el patrón real se endureció a `/url\s+(\S.*)` (exige contenido no-espacio, evita dobles respuestas y términos en blanco).
- 1 clave nueva de localización (`url_usage`) en ES/EN/PT (90 claves sincronizadas).

## [4.2.0] — Sistema de Referidos

### 👥 Nuevo: Programa de Referidos
- **Gana búsquedas gratis invitando amigos**: cada usuario tiene un enlace único `https://t.me/UlpHJBot?start=ref_<su_id>`.
- **Bono doble**: cuando alguien se une con tu enlace, **tú recibes +1 búsqueda gratis** y **tu amigo recibe +1 búsqueda extra** (además de su regalo de bienvenida) — 2 búsquedas gratis en total para el invitado.
- **Sin límite**: por cada amigo que se una, +1 búsqueda. Invita a todos los que quieras.
- **Panel «👥 Referidos»**: nuevo botón en el menú de los 4 rangos (FREE · VIP · SELLER · OWNER) con tu enlace personal, amigos invitados, búsquedas gratis disponibles y explicación del programa.
- **Botón «📢 Compartir mi link»**: abre el diálogo nativo de Telegram para reenviar tu enlace con un mensaje promocional pre-escrito.
- **Notificación instantánea al referidor**: «🎉 ¡NUEVO REFERIDO! {nombre} se unió con tu enlace — Recompensa: +1 búsqueda gratis» en el idioma del referidor.
- **Tarjeta «BONO DE INVITACIÓN»** en la bienvenida del usuario invitado con el total de búsquedas gratis acumuladas.

### 🎫 Búsquedas gratis inteligentes
- El botón de búsqueda muestra el total disponible: «🎁 Búsqueda gratis (1/1)» o «🎁 Búsquedas gratis (3)» cuando hay bonos acumulados.
- Las búsquedas de bono se consumen automáticamente tras la inicial, con confirmación en el resultado («🎁 Usaste una búsqueda de tu bono — Te quedan N»).
- Sin búsquedas restantes: upsell que sugiere VIP **o invitar amigos** para conseguir más gratis.
- «Mi cuenta» ahora muestra estadísticas de referidos: `👥 Referidos · 🎁 Bonos`.

### 🛡️ Anti-abuso
- Solo usuarios **genuinamente nuevos** pueden ser referidos (se comprueba antes de crear su registro).
- Un usuario solo puede ser referido **una vez** (guard atómico `referrer_id IS NULL` en SQLite).
- **Auto-referido bloqueado** y el referidor debe ser un usuario real registrado del bot.
- Re-validación del acceso gratis al momento de ejecutar búsquedas encoladas (evita consumo fantasma).

### 🔧 Interno
- DB: columnas `bonus_searches` y `referrer_id` en `users` + índice `idx_users_referrer` (migración automática).
- `can_search()` reconoce los bonos de referidos; `_check_search_access` distingue `initial` / `bonus`.
- Mensaje de acceso denegado actualizado con el nuevo camino gratis («O invita amigos y gana búsquedas gratis»).
- 9 claves nuevas de localización en ES/EN/PT (89 claves sincronizadas) y banners actualizados a v4.2.

## [4.1.0] — Professional Polish

### 🎨 Diseño
- **Insignias únicas por rango**: el rango se muestra con identidad propia en bienvenida y cuenta — 🆓 FREE · 💎 VIP · 💼 SELLER · 👑 OWNER.
- **«Mi cuenta» rediseñado**: fecha de registro (Miembro desde), barra de vigencia VIP `▰▰▰▰▱▱`, días restantes con gramática correcta (resta/restan) y fecha DD/MM/AAAA.
- **Aviso de renovación inteligente**: los VIPs con ≤ 3 días de suscripción ven una advertencia en la bienvenida y en su cuenta para renovar a tiempo.
- **Teclado «Sin resultados» mejorado**: acceso directo a Nueva búsqueda, Reportar URL y Comprar VIP sin volver al menú.
- **Botones bajo el archivo de resultados**: «Nueva búsqueda» y «Mi cuenta» adjuntos al archivo entregado — flujo continuo sin pasos extra.
- Banner y textos actualizados a v4.1 en los 3 idiomas (ES/EN/PT) con claves nuevas sincronizadas en locale.py y locales/*.json.

### 🔧 Corregido
- Días VIP redondeados hacia arriba (23h restantes muestra «1 día», antes «0 días»).
- Tildes en respuestas del sistema («Grupo añadido», antes «anadido»).
- README y docstrings alineados con la nomenclatura de 4 rangos (OWNER).

## [4.0.1] — Restauración de funciones

### 🔧 Corregido
- **💎 Comprar VIP restaurado en el menú FREE**: el botón ahora está SIEMPRE visible para usuarios FREE (en 4.0.0 desaparecía mientras la búsqueda gratis estuviera disponible, y el usuario no tenía forma de comprar desde el menú).
- **💎 Renovar VIP añadido al menú VIP**: los usuarios VIP pueden renovar su suscripción directamente desde el menú principal.
- **Rango OWNER**: el rango máximo ahora se muestra como `OWNER` (antes `ADMIN`), reflejando los 4 rangos del bot: FREE · VIP · SELLER · OWNER. Se mantiene `UserRole.ADMIN` como alias interno — cero cambios requeridos en el resto del código.
- Menú FREE reorganizado: `Búsqueda gratis` + `Comprar VIP` + `Canjear key` visibles a la vez, como en versiones anteriores.
- README actualizado con la nomenclatura de 4 rangos (FREE · VIP · SELLER · OWNER).

## [4.0.0] — Obsidian Edition

### 🎨 Diseño
- **Nuevo design system "Obsidian"** unificado en todos los mensajes: tarjetas `╭───✦`, banner premium con identidad propia, separadores `┈` y jerarquía tipográfica consistente.
- Textos reescritos con **ortografía completa** (acentos y eñes) en ES/EN/PT.
- Barra de progreso premium `▰▱` en búsquedas, descargas y disco.
- **Teclados rediseñados**: etiquetas consistentes, botón `« Volver` universal, botón de soporte permanente.
- Saludos personalizados con el **nombre del usuario** (`¡Hola, Juan!`).
- Listas admin (VIPs/Sellers) con formato de tarjeta elegante.

### ⚡ Fluidez
- **Callback answer universal**: todos los botones responden al instante (adiós spinners eternos).
- **Caché de usuarios en RAM** (TTL configurable): cada mensaje ya no hace SELECT+UPDATE+commit en SQLite.
- `last_active` con throttle de 5 minutos (menos escrituras).
- Animación de búsqueda con **fases dinámicas** (escaneo → coincidencias → filtrado) e intervalo suave anti-FloodWait.
- Búsqueda inicia con `answer()` inmediato del botón.
- Listas de VIPs con **caché de usernames** y timeout por consulta (antes podían bloquearse con FloodWait).
- Comandos `/cmd` y `/help` fusionados.

### 💳 Pagos
- **Botón URL real** «💳 Pagar ahora» que abre la invoice de NOWPayments directamente.
- **Verificación manual real**: «🔄 Ya pagué» consulta el estado vía API y entrega el VIP al confirmar (antes solo redirigía).
- Pantalla de estado de pago con plan y monto.
- Feedback localizado para pagos expirados/fallidos/pendientes.

### 🆕 Comandos nuevos
- `/ping` — latencia, uptime y versión del bot.
- `/id` — ID del usuario y del chat actual.
- `/help` — alias de `/cmd`.

### 🔐 Seguridad
- **Todos los secretos movidos a `.env`**: API_ID, API_HASH, claves NOWPayments, ADMIN_IDS, BOT_USERNAME, soporte y PM2_NAME (con fallback a los valores previos para no romper despliegues).
- `.env.example` documentado con todas las variables.

### 🧹 Estabilidad y código
- **Shutdown elegante**: SIGTERM/SIGINT cancelan tareas, cierran webhook, clientes y DB ordenadamente.
- `db.close()` + `busy_timeout=5000` en SQLite.
- Fix: dependencia **`aiohttp` faltante** en `requirements.txt` (crash en installs limpios).
- Fix: `/updateBot` probaba un único nombre pm2 (`botulp`) que no coincidía con el README (`ulp-bot`) — ahora configurable vía `PM2_NAME`.
- Fix: header roto `╝══─✦` y typo «GEOLICALIZANDO» en textos IMAP.
- Fix: inconsistencias menores de formato y variables sin usar en `download.py`.
- Banner de arranque y logs de versión.

### 📚 Documentación
- README profesional completo: badges, tablas de variables y comandos, arquitectura, design system y guía de seguridad.

## [3.5.0] — Historial

- Motor de búsqueda paralelo con límites anti-cuelgue
- Invoice multi-cripto + IPN webhook auto-delivery
- Sistema multi-idioma ES/EN/PT
- IMAP Checker v2 con keywords, países y ZIP
- Cola de búsquedas por usuario (anti-superposición)
