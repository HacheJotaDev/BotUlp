# Changelog — HJ ULP PRO

Todos los cambios notables del bot se documentan aquí.

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
