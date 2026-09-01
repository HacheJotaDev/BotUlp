# Changelog — HJ ULP PRO

Todos los cambios notables del bot se documentan aquí.

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
