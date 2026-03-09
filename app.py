import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'soner_webrtc_final_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sohbet.db'

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

class Kullanici(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kullanici_adi = db.Column(db.String(50), unique=True, nullable=False)
    sifre = db.Column(db.String(255), nullable=False)
    is_super_admin = db.Column(db.Boolean, default=False)

class Oda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ad = db.Column(db.String(50), unique=True, nullable=False)
    tip = db.Column(db.String(10), default='yazi')

with app.app_context():
    db.create_all()
    if Oda.query.count() == 0:
        db.session.add(Oda(ad='#genel', tip='yazi'))
        db.session.add(Oda(ad='🔊 Genel Ses', tip='ses'))
        db.session.commit()

aktif_kullanicilar = {} 

@app.route('/')
def ana_sayfa():
    if 'kullanici' not in session: return redirect(url_for('giris'))
    k = Kullanici.query.filter_by(kullanici_adi=session['kullanici']).first()
    return render_template('sohbet.html', kullanici=k, 
                          yazi_odalar=Oda.query.filter_by(tip='yazi').all(),
                          ses_odalar=Oda.query.filter_by(tip='ses').all())

@app.route('/giris', methods=['GET', 'POST'])
def giris():
    if request.method == 'POST':
        ad = request.form.get('kullanici_adi')
        k = Kullanici.query.filter_by(kullanici_adi=ad).first()
        if k and check_password_hash(k.sifre, request.form.get('sifre')):
            session['kullanici'] = k.kullanici_adi
            return redirect(url_for('ana_sayfa'))
    return render_template('giris.html')

@app.route('/kayit', methods=['GET', 'POST'])
def kayit():
    if request.method == 'POST':
        ad = request.form.get('kullanici_adi')
        if not Kullanici.query.filter_by(kullanici_adi=ad).first():
            is_first = (Kullanici.query.count() == 0)
            db.session.add(Kullanici(kullanici_adi=ad, sifre=generate_password_hash(request.form.get('sifre')), is_super_admin=is_first))
            db.session.commit()
            return redirect(url_for('giris'))
    return render_template('kayit.html')

@app.route('/cikis')
def cikis():
    session.pop('kullanici', None)
    return redirect(url_for('giris'))

@socketio.on('connect')
def connect():
    ad = session.get('kullanici')
    if ad:
        aktif_kullanicilar[ad] = request.sid
        join_room('#genel')
        emit('kullanici_listesi', list(aktif_kullanicilar.keys()), broadcast=True)

@socketio.on('disconnect')
def disconnect():
    ad = session.get('kullanici')
    if ad in aktif_kullanicilar:
        del aktif_kullanicilar[ad]
        emit('kullanici_listesi', list(aktif_kullanicilar.keys()), broadcast=True)

@socketio.on('mesaj_gonder')
def handle_msg(data):
    emit('yeni_mesaj', {'icerik': data['mesaj'], 'gonderen': session.get('kullanici'), 'oda': data['oda']}, room=data['oda'])

@socketio.on('ozel_mesaj')
def handle_private(data):
    hedef = data['hedef']
    if hedef in aktif_kullanicilar:
        emit('yeni_ozel_mesaj', {'gonderen': session.get('kullanici'), 'mesaj': data['mesaj']}, room=aktif_kullanicilar[hedef])

@socketio.on('ses_sinyali')
def handle_voice(data):
    # Ses verisi değil, bağlantı kurma sinyalini iletir
    hedef_sid = aktif_kullanicilar.get(data.get('hedef'))
    if hedef_sid:
        emit('ses_sinyali_al', data, room=hedef_sid)
    elif data.get('type') == 'join':
        emit('ses_sinyali_al', data, room=data['oda'], include_self=False)

if __name__ == '__main__':
    socketio.run(app)