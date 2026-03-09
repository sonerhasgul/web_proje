import eventlet
eventlet.monkey_patch()  # EN ÜSTTE KALMALI!

import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'soner_gizli_anahtar_2026'

# --- VERİTABANI AYARI (PostgreSQL & SQLite Uyumu) ---
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///sohbet.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- SOCKET.IO AYARI (Async Modu Şart) ---
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- VERİTABANI MODELLERİ ---
class Kullanici(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kullanici_adi = db.Column(db.String(80), unique=True, nullable=False)
    sifre = db.Column(db.String(200), nullable=False)

# --- ANA SAYFA VE GİRİŞ SİSTEMİ ---
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = Kullanici.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))
    return render_template('sohbet.html', kullanici=user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = Kullanici.query.filter_by(kullanici_adi=username).first()
        if user and check_password_hash(user.sifre, password):
            session['user_id'] = user.id
            return redirect(url_for('index'))
        flash('Kullanıcı adı veya şifre hatalı!')
    return render_template('login.html') # Login sayfan olduğunu varsayıyorum

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if Kullanici.query.filter_by(kullanici_adi=username).first():
            flash('Bu kullanıcı adı alınmış!')
        else:
            hashed_password = generate_password_hash(password)
            yeni_kullanici = Kullanici(kullanici_adi=username, sifre=hashed_password)
            db.session.add(yeni_kullanici)
            db.session.commit()
            flash('Kayıt başarılı! Giriş yapabilirsiniz.')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- SOHBET VE SES OLAYLARI (SOCKET.IO) ---
@socketio.on('mesaj_gonder')
def handle_message(data):
    user_id = session.get('user_id')
    if user_id:
        user = Kullanici.query.get(user_id)
        emit('yeni_mesaj', {
            'icerik': data['mesaj'],
            'gonderen': user.kullanici_adi,
            'oda': data['oda']
        }, broadcast=True)

@socketio.on('ses_sinyali')
def handle_voice(data):
    # Bu kısım ses tekliflerini (offer/answer/ice) diğer kullanıcılara iletir
    emit('ses_sinyali_al', data, broadcast=True, include_self=False)

# --- UYGULAMAYI BAŞLAT ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, host='0.0.0.0', port=5000)
