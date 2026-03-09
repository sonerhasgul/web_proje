import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'soner_mirc_final_fix'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sohbet.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

class Kullanici(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kullanici_adi = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    sifre = db.Column(db.String(255), nullable=False)
    profil_resmi = db.Column(db.String(100), default='default.png')
    is_super_admin = db.Column(db.Boolean, default=False)
    oda_yetkileri = db.Column(db.String(255), default='')

class Oda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ad = db.Column(db.String(50), unique=True, nullable=False)
    tip = db.Column(db.String(10), default='yazi')

with app.app_context():
    db.create_all()
    if Oda.query.count() == 0:
        db.session.add(Oda(ad='#genel', tip='yazi'))
        db.session.commit()

aktif_kullanicilar = {}

# --- HELPER FONKSİYONLAR ---
def yetki_kontrol(user_ad, oda_adi):
    u = Kullanici.query.filter_by(kullanici_adi=user_ad).first()
    if not u: return False
    if u.is_super_admin: return True
    return oda_adi in (u.oda_yetkileri.split(',') if u.oda_yetkileri else [])

def online_liste_yayini(oda_adi):
    liste = []
    for ad, info in aktif_kullanicilar.items():
        if info['oda'] == oda_adi:
            prefix = "@" if yetki_kontrol(ad, oda_adi) else ""
            liste.append({'ad': prefix + ad, 'foto': info['foto']})
    socketio.emit('kullanici_listesi', liste, room=oda_adi)

# --- WEB ROTALARI ---
@app.route('/')
def ana_sayfa():
    if 'kullanici' not in session: return redirect(url_for('giris'))
    k = Kullanici.query.filter_by(kullanici_adi=session['kullanici']).first()
    if not k: return redirect(url_for('cikis'))
    
    # HATAYI BURADA ÇÖZÜYORUZ: Hem yazi_odalar hem de ses_odalar gönderilmeli
    yazi_odalar = Oda.query.filter_by(tip='yazi').all()
    ses_odalar = Oda.query.filter_by(tip='ses').all()
    return render_template('sohbet.html', kullanici=k, yazi_odalar=yazi_odalar, ses_odalar=ses_odalar)

@app.route('/giris', methods=['GET', 'POST'])
def giris():
    if request.method == 'POST':
        ad = request.form.get('kullanici_adi')
        sifre = request.form.get('sifre')
        k = Kullanici.query.filter_by(kullanici_adi=ad).first()
        if k and check_password_hash(k.sifre, sifre):
            session['kullanici'] = k.kullanici_adi
            return redirect(url_for('ana_sayfa'))
        flash('Hatalı kullanıcı adı veya şifre!', 'danger')
    return render_template('giris.html')

@app.route('/kayit', methods=['GET', 'POST'])
def kayit():
    if request.method == 'POST':
        ad = request.form.get('kullanici_adi')
        if Kullanici.query.filter_by(kullanici_adi=ad).first():
            flash('Bu kullanıcı adı alınmış!', 'danger')
            return redirect(url_for('kayit'))
        
        is_first = (Kullanici.query.count() == 0)
        yeni = Kullanici(
            kullanici_adi=ad, 
            email=request.form.get('email'),
            sifre=generate_password_hash(request.form.get('sifre')),
            is_super_admin=is_first
        )
        db.session.add(yeni); db.session.commit()
        return redirect(url_for('giris'))
    return render_template('kayit.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if 'kullanici' not in session: return redirect(url_for('giris'))
    k = Kullanici.query.filter_by(kullanici_adi=session['kullanici']).first()
    if not k or not k.is_super_admin: return "Yetkisiz Alan!", 403
    
    if request.method == 'POST':
        if 'yeni_oda_ad' in request.form:
            yeni_ad = request.form.get('yeni_oda_ad')
            tip = request.form.get('oda_tipi')
            if not Oda.query.filter_by(ad=yeni_ad).first():
                db.session.add(Oda(ad=yeni_ad, tip=tip))
                db.session.commit()
    
    tum_odalar = Oda.query.all()
    tum_kullanicilar = Kullanici.query.all()
    return render_template('admin.html', odalar=tum_odalar, kullanicilar=tum_kullanicilar)

@app.route('/oda_sil/<int:id>')
def oda_sil(id):
    if 'kullanici' in session:
        k = Kullanici.query.filter_by(kullanici_adi=session['kullanici']).first()
        if k and k.is_super_admin:
            o = Oda.query.get(id)
            if o: db.session.delete(o); db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/profil', methods=['GET', 'POST'])
def profil():
    if 'kullanici' not in session: return redirect(url_for('giris'))
    k = Kullanici.query.filter_by(kullanici_adi=session['kullanici']).first()
    if request.method == 'POST' and 'foto' in request.files:
        f = request.files['foto']
        if f.filename:
            fname = secure_filename(f"{k.kullanici_adi}_{f.filename}")
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
            k.profil_resmi = fname; db.session.commit()
    return render_template('profil.html', kullanici=k)

@app.route('/cikis')
def cikis():
    session.pop('kullanici', None)
    return redirect(url_for('giris'))

# --- SOCKET ---
@socketio.on('connect')
def connect():
    ad = session.get('kullanici')
    if ad:
        k = Kullanici.query.filter_by(kullanici_adi=ad).first()
        aktif_kullanicilar[ad] = {'sid': request.sid, 'oda': '#genel', 'foto': k.profil_resmi if k else 'default.png'}
        join_room('#genel')
        online_liste_yayini('#genel')

@socketio.on('disconnect')
def disconnect():
    ad = session.get('kullanici')
    if ad in aktif_kullanicilar:
        oda = aktif_kullanicilar[ad]['oda']
        del aktif_kullanicilar[ad]
        online_liste_yayini(oda)

@socketio.on('oda_degistir')
def oda_degistir(data):
    ad = session.get('kullanici')
    yeni = data.get('yeni_oda')
    if ad in aktif_kullanicilar:
        eski = aktif_kullanicilar[ad]['oda']
        leave_room(eski); join_room(yeni)
        aktif_kullanicilar[ad]['oda'] = yeni
        online_liste_yayini(eski); online_liste_yayini(yeni)

@socketio.on('mesaj_gonder')
def handle_msg(data):
    ad = session.get('kullanici')
    if ad in aktif_kullanicilar:
        oda = aktif_kullanicilar[ad]['oda']
        prefix = "@" if yetki_kontrol(ad, oda) else ""
        emit('yeni_mesaj', {'icerik': data['mesaj'], 'gonderen': prefix + ad, 'oda': oda}, room=oda)

@socketio.on('admin_komut')
def admin_komut(data):
    admin = Kullanici.query.filter_by(kullanici_adi=session.get('kullanici')).first()
    if admin and admin.is_super_admin:
        u = Kullanici.query.filter_by(kullanici_adi=data['hedef']).first()
        if u:
            if data['islem'] == 'super_admin_yap': u.is_super_admin = True
            elif data['islem'] == 'oda_op_yap':
                mevcut = u.oda_yetkileri.split(',') if u.oda_yetkileri else []
                if data['oda'] not in mevcut:
                    mevcut.append(data['oda'])
                    u.oda_yetkileri = ','.join(filter(None, mevcut))
            elif data['islem'] == 'yetki_temizle':
                u.is_super_admin = False; u.oda_yetkileri = ''
            db.session.commit()
            emit('reload_needed', broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)