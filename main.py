import os
import json
import asyncio
import threading
from flask import Flask, render_template, request, redirect, jsonify, send_from_directory, session, url_for
from flask_cors import CORS
from twitchio.ext import commands
from werkzeug.utils import secure_filename
import requests
import sqlite3
from functools import wraps
import secrets

# Config
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
CORS(app)

# Twitch OAuth Config
CLIENT_ID = os.environ.get('TWITCH_CLIENT_ID', '')
CLIENT_SECRET = os.environ.get('TWITCH_CLIENT_SECRET', '')
REDIRECT_URI = os.environ.get('REDIRECT_URI', 'http://localhost:5000/callback')

# Storage
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max

# Database
def get_db():
    conn = sqlite3.connect('bot.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            token TEXT,
            points_per_msg INTEGER DEFAULT 1,
            cooldown INTEGER DEFAULT 30
        );
        CREATE TABLE IF NOT EXISTS sounds (
            id INTEGER PRIMARY KEY,
            channel TEXT,
            name TEXT,
            filename TEXT,
            cost INTEGER DEFAULT 50,
            UNIQUE(channel, name)
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            channel TEXT,
            username TEXT,
            points INTEGER DEFAULT 0,
            UNIQUE(channel, username)
        );
        CREATE TABLE IF NOT EXISTS queue (
            id INTEGER PRIMARY KEY,
            channel TEXT,
            sound TEXT,
            username TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY,
            channel TEXT,
            username TEXT,
            sound TEXT,
            cost INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()
    return conn

db = init_db()

# Auth decorator
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'channel' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ============ ROUTES ============

@app.route('/')
def index():
    if 'channel' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html', client_id=CLIENT_ID, redirect_uri=REDIRECT_URI)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return "Error: No code", 400
    
    # Exchange code for token
    resp = requests.post('https://id.twitch.tv/oauth2/token', data={
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': REDIRECT_URI
    })
    
    if resp.status_code != 200:
        return f"Error getting token: {resp.text}", 400
    
    token_data = resp.json()
    access_token = token_data['access_token']
    
    # Get user info
    user_resp = requests.get('https://api.twitch.tv/helix/users', headers={
        'Authorization': f'Bearer {access_token}',
        'Client-Id': CLIENT_ID
    })
    
    if user_resp.status_code != 200:
        return "Error getting user", 400
    
    user_data = user_resp.json()['data'][0]
    channel = user_data['login']
    
    # Save to DB
    db.execute('''
        INSERT OR REPLACE INTO channels (name, token) VALUES (?, ?)
    ''', (channel, access_token))
    db.commit()
    
    session['channel'] = channel
    session['token'] = access_token
    
    # Restart bot to include new channel
    restart_bot()
    
    return redirect(url_for('dashboard'))

@app.route('/login')
def login():
    return render_template('index.html', client_id=CLIENT_ID, redirect_uri=REDIRECT_URI)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    channel = session['channel']
    
    # Get sounds
    sounds = db.execute('SELECT * FROM sounds WHERE channel = ?', (channel,)).fetchall()
    
    # Get config
    config = db.execute('SELECT * FROM channels WHERE name = ?', (channel,)).fetchone()
    
    # Get top users
    top_users = db.execute('''
        SELECT username, points FROM users WHERE channel = ? ORDER BY points DESC LIMIT 10
    ''', (channel,)).fetchall()
    
    # Get recent logs
    logs = db.execute('''
        SELECT * FROM logs WHERE channel = ? ORDER BY timestamp DESC LIMIT 20
    ''', (channel,)).fetchall()
    
    overlay_url = request.host_url + f'overlay/{channel}'
    
    return render_template('dashboard.html', 
        channel=channel,
        sounds=sounds,
        config=config,
        top_users=top_users,
        logs=logs,
        overlay_url=overlay_url
    )

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    channel = session['channel']
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    
    file = request.files['file']
    name = request.form.get('name', '').lower().replace(' ', '_')
    cost = int(request.form.get('cost', 50))
    
    if not name:
        name = os.path.splitext(file.filename)[0].lower().replace(' ', '_')
    
    filename = secure_filename(f"{channel}_{name}.mp3")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    db.execute('''
        INSERT OR REPLACE INTO sounds (channel, name, filename, cost) VALUES (?, ?, ?, ?)
    ''', (channel, name, filename, cost))
    db.commit()
    
    return jsonify({'success': True})

@app.route('/delete_sound/<name>', methods=['POST'])
@login_required
def delete_sound(name):
    channel = session['channel']
    
    sound = db.execute('SELECT filename FROM sounds WHERE channel = ? AND name = ?', (channel, name)).fetchone()
    if sound:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], sound['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
        db.execute('DELETE FROM sounds WHERE channel = ? AND name = ?', (channel, name))
        db.commit()
    
    return jsonify({'success': True})

@app.route('/update_config', methods=['POST'])
@login_required
def update_config():
    channel = session['channel']
    data = request.json
    
    db.execute('''
        UPDATE channels SET points_per_msg = ?, cooldown = ? WHERE name = ?
    ''', (data.get('points_per_msg', 1), data.get('cooldown', 30), channel))
    db.commit()
    
    return jsonify({'success': True})

@app.route('/overlay/<channel>')
def overlay(channel):
    return render_template('overlay.html', channel=channel)

@app.route('/poll/<channel>')
def poll(channel):
    row = db.execute('SELECT id, sound, username FROM queue WHERE channel = ? LIMIT 1', (channel,)).fetchone()
    if row:
        db.execute('DELETE FROM queue WHERE id = ?', (row['id'],))
        db.commit()
        return jsonify({'sound': row['sound'], 'username': row['username']})
    return jsonify({'sound': None})

@app.route('/audio/<filename>')
def audio(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/sounds/<channel>')
def api_sounds(channel):
    sounds = db.execute('SELECT name, cost FROM sounds WHERE channel = ?', (channel,)).fetchall()
    return jsonify([dict(s) for s in sounds])

# ============ TWITCH BOT ============

class TwitchBot(commands.Bot):
    def __init__(self, channels_data):
        self.channels_data = {c['name']: c for c in channels_data}
        tokens = [c['token'] for c in channels_data if c['token']]
        channel_names = [c['name'] for c in channels_data]
        
        if not tokens:
            return
            
        super().__init__(
            token=tokens[0],  # Use first token for connection
            prefix='!',
            initial_channels=channel_names
        )
        self.cooldowns = {}

    async def event_ready(self):
        print(f'Bot ready | Channels: {", ".join(self.channels_data.keys())}')

    async def event_message(self, msg):
        if msg.echo or not msg.author:
            return
        
        channel = msg.channel.name
        username = msg.author.name
        
        # Add points
        config = db.execute('SELECT points_per_msg FROM channels WHERE name = ?', (channel,)).fetchone()
        points = config['points_per_msg'] if config else 1
        
        db.execute('''
            INSERT INTO users (channel, username, points) VALUES (?, ?, ?)
            ON CONFLICT(channel, username) DO UPDATE SET points = points + ?
        ''', (channel, username, points, points))
        db.commit()
        
        await self.handle_commands(msg)

    @commands.command(name='puntos')
    async def cmd_puntos(self, ctx):
        row = db.execute('SELECT points FROM users WHERE channel = ? AND username = ?', 
            (ctx.channel.name, ctx.author.name)).fetchone()
        points = row['points'] if row else 0
        await ctx.send(f'@{ctx.author.name} → {points} puntos')

    @commands.command(name='sonidos')
    async def cmd_sonidos(self, ctx):
        sounds = db.execute('SELECT name, cost FROM sounds WHERE channel = ?', (ctx.channel.name,)).fetchall()
        if not sounds:
            await ctx.send('No hay sonidos disponibles')
            return
        lista = ' | '.join([f'{s["name"]} ({s["cost"]}p)' for s in sounds])
        await ctx.send(f'Sonidos: {lista}')

    @commands.command(name='canjear')
    async def cmd_canjear(self, ctx, sound_name: str = None):
        if not sound_name:
            await ctx.send(f'@{ctx.author.name} usa: !canjear <nombre>')
            return
        
        channel = ctx.channel.name
        username = ctx.author.name
        
        # Check cooldown
        config = db.execute('SELECT cooldown FROM channels WHERE name = ?', (channel,)).fetchone()
        cooldown = config['cooldown'] if config else 30
        
        key = f'{channel}:{username}'
        import time
        now = time.time()
        if key in self.cooldowns and now - self.cooldowns[key] < cooldown:
            wait = int(cooldown - (now - self.cooldowns[key]))
            await ctx.send(f'@{username} espera {wait}s')
            return
        
        # Check sound exists
        sound = db.execute('SELECT * FROM sounds WHERE channel = ? AND name = ?', 
            (channel, sound_name.lower())).fetchone()
        if not sound:
            await ctx.send(f'@{username} sonido no encontrado')
            return
        
        # Check points
        user = db.execute('SELECT points FROM users WHERE channel = ? AND username = ?',
            (channel, username)).fetchone()
        points = user['points'] if user else 0
        
        if points < sound['cost']:
            await ctx.send(f'@{username} necesitas {sound["cost"]} puntos (tienes {points})')
            return
        
        # Deduct points
        db.execute('UPDATE users SET points = points - ? WHERE channel = ? AND username = ?',
            (sound['cost'], channel, username))
        
        # Queue sound
        db.execute('INSERT INTO queue (channel, sound, username) VALUES (?, ?, ?)',
            (channel, sound['filename'], username))
        
        # Log
        db.execute('INSERT INTO logs (channel, username, sound, cost) VALUES (?, ?, ?, ?)',
            (channel, username, sound_name, sound['cost']))
        
        db.commit()
        
        self.cooldowns[key] = now
        await ctx.send(f'🔊 @{username} → {sound_name}!')

bot = None
bot_thread = None

def run_bot():
    global bot
    channels = db.execute('SELECT * FROM channels').fetchall()
    if not channels:
        print("No channels registered")
        return
    
    bot = TwitchBot([dict(c) for c in channels])
    if hasattr(bot, 'run'):
        bot.run()

def restart_bot():
    global bot, bot_thread
    if bot:
        asyncio.run(bot.close())
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

# ============ START ============

if __name__ == '__main__':
    # Start bot in background
    restart_bot()
    
    # Start Flask
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
