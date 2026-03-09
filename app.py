import eventlet
eventlet.monkey_patch()

import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'soner_chat_secret_2026'

# PostgreSQL & SQLite Uyumu
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///sohbet.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
# SocketIO'yu eventlet modunda başlatıyoruz (Mesajların gitmesi için kritik)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Veritabanı Modelleri
class Kullanici(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kullanici_adi = db.Column(db.String(80), unique=True, nullable=False)
    sifre = db.Column(db.String(200), nullable=False)

# Rotalar (Giriş/Kayıt/Index)
@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = Kullanici.query.get(session['user_id'])
    return render_template('sohbet.html', kullanici=user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = Kullanici.query.filter_by(kullanici_adi=request.form['username']).first()
        if user and check_password_hash(user.sifre, request.form['password']):
            session['user_id'] = user.id
            return redirect(url_for('index'))
        flash('Hatalı giriş!')
    return '''<form method="post">Kullanıcı: <input name="username"><br>Şifre: <input type="password" name="password"><br><button>Giriş</button></form>'''

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed = generate_password_hash(request.form['password'])
        yeni = Kullanici(kullanici_adi=request.form['username'], sifre=hashed)
        db.session.add(yeni)
        db.session.commit()
        return redirect(url_for('login'))
    return '''<form method="post">Kullanıcı: <input name="username"><br>Şifre: <input type="password" name="password"><br><button>Kayıt Ol</button></form>'''

# SocketIO Olayları
@socketio.on('mesaj_gonder')
def handle_message(data):
    user = Kullanici.query.get(session['user_id'])
    emit('yeni_mesaj', {'icerik': data['mesaj'], 'gonderen': user.kullanici_adi, 'oda': data['oda']}, broadcast=True)

@socketio.on('ses_sinyali')
def handle_voice(data):
    # Sinyali hedef kişiye veya odaya ilet (WebRTC için kritik)
    room = data.get('oda')
    emit('ses_sinyali_al', data, room=room, include_self=False)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, host='0.0.0.0', port=5000)
