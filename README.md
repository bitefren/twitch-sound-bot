# 🔊 SoundBot - Twitch Sound Alerts con Puntos

Bot de Twitch que permite a tus viewers canjear puntos por reproducir sonidos en tu stream.

## ✨ Características

- 🎵 Sube tus propios audios desde el panel web
- ⭐ Sistema de puntos automático (ganan al chatear)
- 🎮 Panel de control fácil de usar
- 📊 Ver top usuarios y logs de canjes
- 🔗 Overlay listo para OBS

## 🚀 Deploy en 1 Click

### Opción 1: Koyeb (Recomendado - 100% gratis 24/7)

[![Deploy to Koyeb](https://www.koyeb.com/static/images/deploy/button.svg)](https://app.koyeb.com/deploy?type=git&repository=github.com/TU_USUARIO/twitch-sound-bot&branch=main&name=soundbot)

### Opción 2: Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/soundbot)

### Opción 3: Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

## ⚙️ Configuración Inicial (Solo 1 vez)

### 1. Crear App en Twitch

1. Ve a [dev.twitch.tv/console](https://dev.twitch.tv/console)
2. Click "Register Your Application"
3. Llena:
   - **Name**: SoundBot (o el nombre que quieras)
   - **OAuth Redirect URL**: `https://TU-APP.koyeb.app/callback`
   - **Category**: Chat Bot
4. Click "Create"
5. Copia el **Client ID** y genera un **Client Secret**

### 2. Variables de Entorno

Configura estas variables en tu hosting:

| Variable | Valor |
|----------|-------|
| `TWITCH_CLIENT_ID` | Tu Client ID de Twitch |
| `TWITCH_CLIENT_SECRET` | Tu Client Secret |
| `REDIRECT_URI` | `https://TU-APP.koyeb.app/callback` |
| `SECRET_KEY` | Cualquier texto aleatorio largo |

### 3. ¡Listo!

- Entra a `https://TU-APP.koyeb.app`
- Click "Conectar con Twitch"
- Sube tus sonidos
- Copia el overlay a OBS

## 💬 Comandos del Chat

| Comando | Descripción |
|---------|-------------|
| `!puntos` | Ver tus puntos |
| `!sonidos` | Lista de sonidos disponibles |
| `!canjear nombre` | Reproducir un sonido |

## 🎬 Configurar OBS

1. En OBS, click derecho → **Add** → **Browser Source**
2. Pega la URL del overlay (la encuentras en tu dashboard)
3. Tamaño recomendado: 400x100
4. ✅ Marca "Control audio via OBS"
5. ¡Listo!

## 📁 Estructura

```
├── main.py              # Bot + API + Dashboard
├── templates/
│   ├── index.html       # Landing page
│   ├── dashboard.html   # Panel de control
│   └── overlay.html     # Overlay para OBS
├── uploads/             # Audios subidos
├── requirements.txt
└── Procfile
```

## 🔧 Desarrollo Local

```bash
# Clonar
git clone https://github.com/TU_USUARIO/twitch-sound-bot
cd twitch-sound-bot

# Instalar
pip install -r requirements.txt

# Variables de entorno
export TWITCH_CLIENT_ID=xxx
export TWITCH_CLIENT_SECRET=xxx
export REDIRECT_URI=http://localhost:5000/callback

# Correr
python main.py
```

## 📝 Licencia

MIT - Úsalo como quieras.

---

Hecho con 💜 para streamers
