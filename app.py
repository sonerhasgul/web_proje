import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'soner_chat_secret_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sohbet.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Modeller
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
    if not Oda.query.filter_by(ad='#genel').first():
        db.session.add(Oda(ad='#genel', tip='yazi'))
        db.session.add(Oda(ad='🔊 Sesli Meydan', tip='ses'))
        db.session.commit()

aktif_kullanicilar = {} 

# --- ROTALAR ---
@app.route('/')
def ana_sayfa():
    if 'kullanici' not in session: return redirect(url_for('giris'))
    k = Kullanici.query.filter_by(kullanici_adi=session['kullanici']).first()
    return render_template('sohbet.html', kullanici=k, 
                          yazi_odalar=Oda.query.filter_by(tip='yazi').all(),
                          ses_odalar=Oda.query.filter_by(tip='ses').all())

# ADMIN PANELİ ROTASI (Geri Geldi!)
@app.route('/admin', methods=['GET', 'POST'])
def admin_paneli():
    if 'kullanici' not in session: return redirect(url_for('giris'))
    k = Kullanici.query.filter_by(kullanici_adi=session['kullanici']).first()
    if not k or not k.is_super_admin: return "Yetkisiz Erişim!", 403
    
    if request.method == 'POST':
        oda_adi = request.form.get('oda_adi')
        oda_tipi = request.form.get('oda_tipi')
        if oda_adi:
            yeni_oda = Oda(ad=oda_adi, tip=oda_tipi)
            db.session.add(yeni_oda)
            db.session.commit()
            return redirect(url_for('admin_paneli'))

    odalar = Oda.query.all()
    kullanicilar = Kullanici.query.all()
    return render_template('admin.html', odalar=odalar, kullanicilar=kullanicilar)

@app.route('/oda_sil/<int:id>')
def oda_sil(id):
    k = Kullanici.query.filter_by(kullanici_adi=session.get('kullanici')).first()
    if k and k.is_super_admin:
        oda = Oda.query.get(id)
        if oda and oda.ad != '#genel':
            db.session.delete(oda)
            db.session.commit()
    return redirect(url_for('admin_paneli'))

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

# --- SOCKET ---
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

@socketio.on('ses_sinyali')
def handle_voice(data):
    hedef_sid = aktif_kullanicilar.get(data.get('hedef'))
    if hedef_sid: emit('ses_sinyali_al', data, room=hedef_sid)
    elif data.get('type') == 'join': emit('ses_sinyali_al', data, room=data['oda'], include_self=False)

if __name__ == '__main__':
    # host='0.0.0.0' sayesinde ağdaki herkes bağlanabilir
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)