import eventlet
eventlet.monkey_patch()

import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'soner_chat_2026_ozel'

# --- VERİTABANI BAĞLANTISI ---
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///sohbet.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- MODEL ---
class Kullanici(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kullanici_adi = db.Column(db.String(80), unique=True, nullable=False)
    sifre = db.Column(db.String(200), nullable=False)

# --- ROTALAR ---
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
        return "Hata: Kullanıcı adı veya şifre yanlış. <a href='/login'>Geri Dön</a>"
    return '''
    <body style="background:#1a1a1a;color:white;display:flex;flex-direction:column;align-items:center;padding-top:50px;font-family:sans-serif;">
        <h2>Giriş Yap</h2>
        <form method="post" style="display:flex;flex-direction:column;gap:10px;width:200px;">
            <input name="username" placeholder="Kullanıcı Adı" required style="padding:8px;">
            <input type="password" name="password" placeholder="Şifre" required style="padding:8px;">
            <button type="submit" style="padding:10px;background:#0056b3;color:white;border:none;cursor:pointer;">Giriş</button>
        </form>
        <p>Hesabın yok mu? <a href="/register" style="color:#2ecc71;">Kayıt Ol</a></p>
    </body>
    '''

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        u = request.form.get('username')
        p = request.form.get('password')
        if Kullanici.query.filter_by(kullanici_adi=u).first():
            return "Bu kullanıcı adı zaten var. <a href='/register'>Geri Dön</a>"
        yeni = Kullanici(kullanici_adi=u, sifre=generate_password_hash(p))
        db.session.add(yeni)
        db.session.commit()
        return redirect(url_for('login'))
    return '''
    <body style="background:#1a1a1a;color:white;display:flex;flex-direction:column;align-items:center;padding-top:50px;font-family:sans-serif;">
        <h2>Kayıt Ol</h2>
        <form method="post" style="display:flex;flex-direction:column;gap:10px;width:200px;">
            <input name="username" placeholder="Kullanıcı Adı" required style="padding:8px;">
            <input type="password" name="password" placeholder="Şifre" required style="padding:8px;">
            <button type="submit" style="padding:10px;background:#2ecc71;color:white;border:none;cursor:pointer;">Kayıt Ol</button>
        </form>
        <a href="/login" style="color:#0056b3;">Giriş Ekranına Dön</a>
    </body>
    '''

# --- SOCKET OLAYLARI ---
@socketio.on('mesaj_gonder')
def handle_message(data):
    user = Kullanici.query.get(session.get('user_id'))
    if user:
        emit('yeni_mesaj', {'icerik': data['mesaj'], 'gonderen': user.kullanici_adi, 'oda': data['oda']}, broadcast=True)

@socketio.on('ses_sinyali')
def handle_voice(data):
    emit('ses_sinyali_al', data, broadcast=True, include_self=False)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # Render için dinamik port ayarı
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
