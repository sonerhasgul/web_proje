import eventlet
eventlet.monkey_patch()

import os
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'soner_ultra_secret'

# DB Ayarı
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///sohbet.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Çevrimiçi kullanıcıları tutan liste
online_users = {}

class Kullanici(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kullanici_adi = db.Column(db.String(80), unique=True, nullable=False)
    sifre = db.Column(db.String(200), nullable=False)

@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = Kullanici.query.get(session['user_id'])
    if not user: return redirect(url_for('login'))
    return render_template('sohbet.html', kullanici=user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('username')
        p = request.form.get('password')
        user = Kullanici.query.filter_by(kullanici_adi=u).first()
        if user and check_password_hash(user.sifre, p):
            session['user_id'] = user.id
            return redirect(url_for('index'))
    return '''<body style="background:#0f0f0f;color:white;text-align:center;padding:100px;font-family:sans-serif;">
        <h2 style="color:#8e44ad">SONER CHAT</h2>
        <form method="post" style="display:inline-block;background:#1a1a1a;padding:20px;border-radius:10px;">
            <input name="username" placeholder="Kullanıcı" style="padding:10px;margin:5px;"><br>
            <input type="password" name="password" placeholder="Şifre" style="padding:10px;margin:5px;"><br>
            <button style="padding:10px 20px;background:#8e44ad;color:white;border:none;margin-top:10px;cursor:pointer;">Giriş Yap</button>
        </form><br><a href="/register" style="color:#666;text-decoration:none;font-size:0.8rem;">Kayıt Ol</a></body>'''

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        u = request.form.get('username')
        p = request.form.get('password')
        if not Kullanici.query.filter_by(kullanici_adi=u).first():
            db.session.add(Kullanici(kullanici_adi=u, sifre=generate_password_hash(p)))
            db.session.commit()
            return redirect(url_for('login'))
    return '''<body style="background:#0f0f0f;color:white;text-align:center;padding:100px;font-family:sans-serif;">
        <h2>Kayıt Ol</h2><form method="post"><input name="username" placeholder="Kullanıcı"><br><input type="password" name="password" placeholder="Şifre"><br><button>Kayıt</button></form></body>'''

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# SocketIO Olayları
@socketio.on('connect')
def connect():
    user = Kullanici.query.get(session.get('user_id'))
    if user:
        online_users[request.sid] = user.kullanici_adi
        emit('kullanici_listesi', list(set(online_users.values())), broadcast=True)

@socketio.on('disconnect')
def disconnect():
    if request.sid in online_users:
        del online_users[request.sid]
        emit('kullanici_listesi', list(set(online_users.values())), broadcast=True)

@socketio.on('mesaj_gonder')
def handle_message(data):
    user = Kullanici.query.get(session.get('user_id'))
    if user:
        emit('yeni_mesaj', {'icerik': data['mesaj'], 'gonderen': user.kullanici_adi, 'oda': data.get('oda', '#genel')}, broadcast=True)

@socketio.on('ses_sinyali')
def handle_voice(data):
    emit('ses_sinyali_al', data, broadcast=True, include_self=False)

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
