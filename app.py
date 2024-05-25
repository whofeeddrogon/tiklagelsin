from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import uuid
import datetime
import hashlib
import math

from api import Response, Label, send_comment

app = Flask(__name__)
DATABASE = 'comments.db'

"""
    args:
        comment: str
    output:
        label (Label enum 0 for NON 1 for TOXIC), conf (float)

    example:
        label, conf = get_label_comment('yemekler çok güzel')
"""
def get_label_comment(comment) -> tuple[Label, float]:
    resp = send_comment(comment)
    return resp.get_label(), resp.get_conf()

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def increment_like(comment_id):
    conn = get_db_connection()
    conn.execute('UPDATE comments SET timeslike = timeslike + 1 WHERE id = ?', (comment_id,))
    conn.commit()
    conn.close()

def increment_report(comment_id):
    conn = get_db_connection()
    conn.execute('UPDATE comments SET timesreported = timesreported + 1 WHERE id = ?', (comment_id,))
    conn.commit()
    conn.close()

@app.route('/', methods=['GET', 'POST'])
def index():

    session_user = session.get('user')
    if not session_user:
        return redirect(url_for('login'))

    conn = get_db_connection()
    query_string = 'SELECT * FROM comments WHERE is_showed = 1'

    sort_type = int(request.args.get('sort_type', 0))
    
    if sort_type == 0:
        sort_type = int(session.get('sort_type', 1))
    else:
        session['sort_type'] = sort_type

    if sort_type == 1:
        query_string += ' ORDER BY timeslike DESC'
    elif sort_type == 2:
        query_string += ' ORDER BY id'
    elif sort_type == 3:
        query_string += ' ORDER BY id DESC'


    page = int(request.args.get('page', '0'))
    comments = list(conn.execute(query_string).fetchall())
    total_page = math.ceil(len(comments) / 5)

    comments = [dict(row) for row in comments[5 * page: 5*page + 5]]
    all_users = conn.execute('SELECT * FROM users').fetchall()

    page = {
            'prev_num': page - 1,
            'next_num': page + 1,
            'total_page': total_page
            }

    for comment in comments:
        comment_user = None
        for user in all_users:
            if comment['user_uuid'] == user['uuid']:
                comment_user = user
                break
        if not comment['is_anon']:
            comment['username'] = comment_user['firstname'] + ' ' + comment_user['surname']
        else:
            comment['username'] = comment_user['firstname'][0] + '*** ' + comment_user['surname'][0] + '***'

    user = conn.execute('SELECT * FROM users WHERE uuid = ?', (session_user, )).fetchall()[0]
    conn.close()

    return render_template('index.html', user = user, comments=comments, \
                           page = page, sort_type = sort_type)

@app.route('/add_comment', methods=['POST', 'GET'])
def add_comment():
    
    user = session.get('user')
    comment = request.form.get('comment')
    is_anon = request.form.get('anon', '0')

    # label and conf
    label, conf = get_label_comment(comment)
    is_toxic = label == Label.TOXIC

    conn = get_db_connection()
    conn.execute('INSERT INTO comments (user_uuid, comment, timesreported, timeslike, label, confidence, date_posted, is_anon, is_showed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                 (user, comment, 0, 0, 'NON' if not is_toxic else 'TOXIC', conf, datetime.datetime.now().strftime("%B %d, %Y %I:%M%p"), is_anon, 1 if not is_toxic else 0))
    conn.commit()
    conn.close()
    
    if not is_toxic:
        flash('Yorumunuz paylaşılmıştır, teşekkür ederiz.', 'ok')
    else:
        flash('Bu yorum paylaşılamamaktadır! Lütfen düzeltip tekrar gönderiniz.', 'error')

    return redirect(url_for('index'))

@app.route('/like/<int:comment_id>', methods=['POST'])
def like_comment(comment_id):
    increment_like(comment_id)
    flash('Beğeniniz yoruma başarıyla eklendi.', 'ok')
    return redirect(url_for('index'))

@app.route('/report/<int:comment_id>', methods=['POST'])
def report_comment(comment_id):
    increment_report(comment_id)
    flash('Yorum başarıyla işaretlendi, teşekkürler.', 'ok')
    return redirect(url_for('index'))

@app.route('/search', methods=['GET', 'POST'])
def search():
    conn = get_db_connection()
    search = request.form.get('search')

    searched_comments = conn.execute('SELECT * FROM comments WHERE comment LIKE ?', ('%'+search+'%', )).fetchall()
    conn.close()
    return render_template('index.html', comments=searched_comments, n = 0)

## ADMIN KISIMLARI

@app.route('/admin', methods=['GET'])
def admin():

    conn = get_db_connection()

    user = session.get('user')
    all_users = conn.execute('SELECT * FROM users WHERE uuid = ? and is_admin = ?', (user, 1, )).fetchall()
    if len(all_users) <= 0:
        flash('İzniniz yok!!', 'error')
        return redirect(url_for('index'))

    all_comments = conn.execute('SELECT * FROM comments').fetchall()
    all_comments = [dict(row) for row in all_comments]
    conn.close()

    for comment in all_comments:
        conf = comment['confidence']
        if comment['label'] == 'NON':
            conf = 1 - conf
        comment['toxic_conf'] = conf

    reported_comments = list(filter(lambda c: True if c['timesreported'] > 0 and not c['admin_label'] else False, all_comments))
    published_comments = list(filter(lambda c: c['is_showed'], all_comments))
    deteced_comments = list(filter(lambda c: not c['is_showed'], all_comments))

    return render_template('admin.html', reported_comments = reported_comments, published_comments = published_comments, deteced_comments = deteced_comments)

"""
    Admin, eğer yorum çok raporlandıysa veya yanlış labellandığı düşünülüyorsa
    düzeltme işlemi yapılıyor
"""
@app.route('/accept', methods=['GET'])
def accept():
    id = request.args.get('id')

    conn = get_db_connection()
    comments = conn.execute('SELECT * FROM comments WHERE id = ?', (id, )).fetchall()

    if len(comments) <= 0:
        flash('Bir hata meydana geldi!', 'error')
        conn.close()
        return redirect(url_for('admin'))
    
    conn.execute('UPDATE comments SET admin_label=?, admin_datetime=?, is_showed=? WHERE id = ?', \
                    ('NON', datetime.datetime.now().strftime("%B %d, %Y %I:%M%p"), 1, id, ))
    conn.commit()
    
    conn.close()
    flash('Başarıyla işlem gerçekleştirildi', 'ok')
    return redirect(url_for('admin'))


"""
    Admin, yorumu toxic olarak labellıyor 
"""
@app.route('/delete', methods=['GET'])
def delete():
    id = request.args.get('id')

    conn = get_db_connection()
    comments = conn.execute('SELECT * FROM comments WHERE id = ?', (id, )).fetchall()

    if len(comments) <= 0:
        flash('Bir hata meydana geldi!', 'error')
        conn.close()
        return redirect(url_for('admin'))

    conn.execute('UPDATE comments SET admin_label=?, admin_datetime=?, is_showed=? WHERE id = ?', \
                    ('TOXIC', datetime.datetime.now().strftime("%B %d, %Y %I:%M%p"), 0, id, ))
    conn.commit()

    conn.close()
    flash('Başarıyla işlem gerçekleştirildi', 'ok')
    return redirect(url_for('admin'))

"""
    Admin, kullanıcıyı engelliyor sistemden
"""
@app.route('/block', methods=['GET'])
def block():
    id = request.args.get('id')

    conn = get_db_connection()
    comments = conn.execute('SELECT * FROM comments WHERE id = ?', (id, )).fetchall()
    if len(comments) <= 0:
        flash('Bir hata meydana geldi!', 'error')
        conn.close()
        return redirect(url_for('admin'))
    comment = comments[0]

    conn.execute('UPDATE users SET is_allowed=? WHERE uuid = ?', \
                    (0, comment['user_uuid'], ))
    conn.commit()

    flash('Başarıyla işlem gerçekleştirildi', 'ok')
    return redirect(url_for('admin'))


## LOGIN KISIMLARI

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    
    session_user = session.get('user')
    if session_user:
        return redirect(url_for('index'))
    
    mail = request.form.get('mail')
    password = hashlib.md5(str(request.form.get('password')).encode('utf-8')).hexdigest()

    conn = get_db_connection()
    found_users = conn.execute('SELECT * FROM users WHERE mail = ? and password = ?', (mail, password, )).fetchall()
    conn.close()

    if len(found_users) <= 0:
        flash('Mail adresi veya şifreniz hatalı, lütfen kontrol ediniz!', 'error')
        return redirect(url_for('login'))
    elif found_users[0]['is_allowed'] == 0:
        flash('Yasaklandınız', 'error')
        return redirect(url_for('login'))
    session['user'] = found_users[0]['uuid']

    return redirect(url_for('index'))

@app.route('/register', methods=['POST'])
def register():

    firstname = request.form.get('firstname')
    lastname = request.form.get('lastname')
    mail = request.form.get('mail')
    password = hashlib.md5(str(request.form.get('password')).encode('utf-8')).hexdigest()

    conn = get_db_connection()
    same_mail_users = conn.execute('SELECT * FROM users WHERE mail = ?', (mail, )).fetchall()

    if len(same_mail_users) > 0:
        flash('Mail adresi kullanımda lütfen giriş yapınız!', 'error')
        conn.close()

        return redirect(url_for('login'))
    
    _uuid = f"{uuid.uuid4()}"
    conn.execute('INSERT INTO users (firstname, surname, mail, uuid, password) VALUES (?, ?, ?, ?, ?)',
                 (firstname, lastname, mail, _uuid, password))
    conn.commit()
    conn.close()

    flash('Hesabınız başarıyla oluşturuldu, giriş yapabilirsiniz.', 'ok')
    return redirect(url_for('index'))

@app.route('/logout', methods=['GET'])
def logout():
    session.pop('user')
    flash('Başarıyla çıkış yapıldı', 'ok')

    return redirect(url_for('login'))

if __name__ == '__main__':
    app.secret_key = 'SECRET_KEY_MY_SECRET_KEY_MY_SECRET_KEY'
    app.run(debug=True, port=5002)
