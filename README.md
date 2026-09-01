# ⚡ HJ ULP PRO — Obsidian Edition v4.0

> Bot de Telegram profesional para búsqueda y gestión de bases de datos con arquitectura modular, pagos automáticos multi-cripto y soporte multi-idioma.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Telethon](https://img.shields.io/badge/Telethon-1.34%2B-2CA5E0?style=for-the-badge)
![SQLite](https://img.shields.io/badge/SQLite-WAL-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Version](https://img.shields.io/badge/v4.0-Obsidian-8B5CF6?style=for-the-badge)

---

## ✨ Novedades v4.0 · Obsidian

| Área | Mejora |
|------|--------|
| 🎨 **Diseño** | Sistema visual unificado *Obsidian*: tarjetas `╭───✦`, banner premium, jerarquía tipográfica y ortografía completa en 3 idiomas |
| ⚡ **Fluidez** | Respuesta instantánea de todos los botones (callback answer universal), animación de búsqueda por fases, caché de usuarios en RAM (cero SQL por mensaje) |
| 💳 **Pagos** | Botón **URL real** «Pagar ahora», verificación manual `🔄 Ya pagué` vía API, auto-delivery por IPN webhook + polling fallback |
| 🛠️ **Nuevos comandos** | `/ping` (latencia + uptime + versión) · `/id` (IDs de usuario y chat) · `/help` |
| 🔐 **Seguridad** | Todos los secretos movidos a `.env` (API_HASH, claves NOWPayments, ADMIN_IDS) |
| 🧹 **Estabilidad** | Shutdown elegante (SIGTERM) con cierre de DB y tareas, `busy_timeout` en SQLite, caché de @usernames con timeout, fix de dependencia `aiohttp` |

---

## 📋 Características

- 🔎 **Motor de búsqueda paralelo** con `mmap` y límites anti-cuelgue (resultados, matches y tiempo)
- 📥 **Descargas hasta 4GB** con streaming, progreso en vivo y cola secuencial anti-FloodWait
- 👥 **Roles**: FREE (1 búsqueda gratis) · VIP · SELLER · OWNER
- 🌐 **Multi-idioma**: Español, English, Português (configurable por usuario)
- 💳 **Pagos automáticos** con NOWPayments (USDT, BTC, ETH, LTC…) + canje de keys
- 📧 **IMAP Checker** con keywords, agrupación por dominio y geolocalización por país (ZIP)
- 🗄️ **SQLite WAL** thread-safe con caché de usuarios y `busy_timeout`
- 🧹 **Auto-limpieza**: archivado a 24h, borrado a 120h
- 🔄 **Auto-actualización** remota vía `/updateBot` (git pull + pm2 restart)
- 📣 **Broadcast** global y solo-VIPs con progreso en vivo

---

## 🚀 Instalación

```bash
# 1. Actualizar sistema
sudo apt update && sudo apt upgrade -y

# 2. Instalar Python 3 y pip
sudo apt install python3 python3-pip python3-venv -y

# 3. Instalar Node.js y pm2
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install nodejs -y
sudo npm install -g pm2

# 4. Clonar el bot
git clone https://github.com/HacheJotaDev/BotUlp.git
cd BotUlp

# 5. Crear entorno virtual e instalar dependencias
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 6. Configurar variables de entorno
cp .env.example .env
nano .env    # ← escribe tu BOT_TOKEN (obligatorio) y revisa el resto

# 7. Iniciar el bot con pm2
pm2 start "venv/bin/python3 bot.py" --name botulp

# 8. Guardar pm2 para que sobreviva reinicios
pm2 save
pm2 startup
```

> ⚠️ **Importante**: el nombre de pm2 debe coincidir con `PM2_NAME` en `.env` para que `/updateBot` pueda reiniciar el servicio.

---

## ⚙️ Variables de entorno (`.env`)

| Variable | Obligatoria | Descripción |
|----------|:-----------:|-------------|
| `BOT_TOKEN` | ✅ | Token del bot (de [@BotFather](https://t.me/BotFather)) |
| `API_ID` / `API_HASH` | ⬜ | Credenciales de Telegram (my.telegram.org) |
| `ADMIN_IDS` | ⬜ | IDs de admins separados por coma: `7656500542,123456789` |
| `BOT_USERNAME` | ⬜ | Username del bot sin @ (para links de canje) |
| `SUPPORT_CONTACT` | ⬜ | Usuario de soporte sin @ (botón 📞 Soporte) |
| `NOWPAYMENTS_API_KEY` | ⬜ | API key de NOWPayments |
| `NOWPAYMENTS_IPN_KEY` | ⬜ | Secret IPN para validar firmas HMAC |
| `NOWPAYMENTS_IPN_URL` | ⬜ | URL pública del webhook: `http://TU_IP:9090/ipn` |
| `NOWPAYMENTS_WEBHOOK_PORT` | ⬜ | Puerto del servidor IPN (defecto `9090`) |
| `PM2_NAME` | ⬜ | Nombres pm2 a probar en `/updateBot`: `botulp,ulp-bot` |
| `USER_CACHE_TTL` | ⬜ | Segundos de caché de usuarios en RAM (defecto `30`) |

> 🔒 **Consejo de seguridad**: si tu repositorio fue público con credenciales dentro del código, **regenera** las claves de NOWPayments y usa siempre `.env` (ya está en `.gitignore`).

---

## 🧭 Comandos

### 👤 Todos los usuarios
| Comando | Descripción |
|---------|-------------|
| `/start` | Menú principal con panel de botones |
| `/url <dominio>` | Iniciar búsqueda de un dominio |
| `/canjear <key>` | Canjear una key VIP |
| `/ping` | Latencia, uptime y versión del bot |
| `/id` | Mostrar tu ID y el ID del chat |

### 👑 VIP
| Comando | Descripción |
|---------|-------------|
| `/imap` | IMAP Checker (responde a un .txt con mail:pass) |
| `/imap kw1, kw2` | Con keywords → ZIP agrupado |
| `/imap country` | Agrupar hits por país → ZIP |

### 🔐 Admin
| Comando | Descripción |
|---------|-------------|
| `/vip <id>` | VIP permanente · `/unvip <id>` remover |
| `/seller <id>` | Asignar seller · `/unseller <id>` remover |
| `/gp` / `/ungp` | Permitir / bloquear grupo actual |
| `/bc <texto>` · `/bcvip <texto>` | Broadcast global / solo VIPs |
| `/sizedisp` | Uso de disco del VPS |
| `/updateBot` | Actualizar desde GitHub y reiniciar |

---

## 🏗️ Arquitectura

```
BotUlp/
├── bot.py              # Punto de entrada: clientes, tareas y shutdown elegante
├── config.py           # Configuración tipada con secretos desde .env
├── handlers.py         # Comandos, callbacks y flujos de conversación
├── database.py         # SQLite WAL + caché de usuarios en RAM
├── search.py           # Motor de búsqueda paralelo (mmap + límites)
├── download.py         # Descargas 4GB con progreso y cola secuencial
├── nowpayments.py      # API de pagos: invoices, polling y entrega VIP
├── webhook_server.py   # Servidor IPN (HMAC-SHA512 verificado)
├── imap_checker.py     # Checker IMAP SSL con keywords y países
├── geoip_checker.py    # Geolocalización de emails (MX + IP)
├── locale.py           # Sistema multi-idioma (design system Obsidian)
├── locales/*.json      # Traducciones ES / EN / PT
├── ui.py               # Teclados inline (botones URL, jerarquía visual)
├── roles.py            # Roles y permisos
├── state.py            # Estado global en memoria
└── utils.py            # Barras de progreso y formateadores
```

---

## 🎨 Design System · Obsidian

Todos los mensajes del bot siguen un lenguaje visual unificado:

```
╭━━━━━━━━━━━━━━━━━━━━╮
┃ ✦ ☾ HJ ULP PRO ☽ ✦
┃ ⚡ v4.0 · Professional
╰━━━━━━━━━━━━━━━━━━━━╯

╭───✦ 👤 MI CUENTA
├─ 🆔 ID: `7656500542`
├─ 🎖️ Rango: VIP
╰───✦
```

- **Tarjetas** `╭───✦ … ╰───✦` para bloques de información
- **Barras de progreso** premium `▰▰▰▰▰▰▱▱▱▱ 52.3%`
- **Botones** con jerarquía: acción primaria primero, `« Volver` siempre al final
- **Spinner por fases** durante búsquedas: escaneo → coincidencias → filtrado

---

## 📬 Soporte

- 📞 Contacto: [@hjofc20](https://t.me/hjofc20)
- 🚀 by @hjofc20 · HJ Dev

---

## 📄 Licencia

Proyecto privado. Todos los derechos reservados © HacheJotaDev
