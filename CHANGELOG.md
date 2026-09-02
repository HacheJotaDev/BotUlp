# Changelog — HJ ULP PRO

Todos los cambios notables del bot se documentan aquí.

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
