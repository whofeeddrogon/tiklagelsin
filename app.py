from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import uuid
import datetime

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

    conn = get_db_connection()

    sort_type = request.args.get('sort', 1)
    if sort_type == 1:
        query_string = 'SELECT * FROM comments WHERE label = "NON" ORDER BY timeslike DESC'
    elif sort_type == 2:
        query_string = 'SELECT * FROM comments WHERE label = "NON" ORDER BY id'
    else:
        query_string = 'SELECT * FROM comments WHERE label = "NON" ORDER BY id DESC'


    comments = conn.execute(query_string).fetchall()
    conn.close()

    # data clipping
    index = int(request.args.get('n', 3))
    if index < 3:
        index = 3
    if index >= len(comments):
        index = len(comments)
        
    comments = [comments[index] for index in range(index - 3, index)]

    successful = request.args.get('successful', -1)
    return render_template('index.html', comments=comments, successful = successful, n = index // 3, sort_type = sort_type)

@app.route('/add_comment', methods=['POST', 'GET'])
def add_comment():
    
    # username formating
    firstname = request.form.get('firstname')
    lastname = request.form.get('lastname')

    username = f'{firstname}-{lastname}-{uuid.uuid4()}'
    comment = request.form.get('comment')

    # label and conf
    label, conf = get_label_comment(comment)
    is_toxic = label == Label.TOXIC

    conn = get_db_connection()
    conn.execute('INSERT INTO comments (username, comment, timesreported, timeslike, label, confidence, date_posted) VALUES (?, ?, ?, ?, ?, ?, ?)',
                 (username, comment, 0, 0, 'NON' if label == Label.NON else 'TOXIC', 0, datetime.datetime.now().strftime("%B %d, %Y %I:%M%p")))
    conn.commit()
    conn.close()
    
    return redirect(url_for('index') + '?successful=' + ('0' if is_toxic else '1'))

@app.route('/like/<int:comment_id>', methods=['POST'])
def like_comment(comment_id):
    increment_like(comment_id)
    n = request.args.get('n', 0)
    return redirect(url_for('index') + f'/?n={n}')

@app.route('/report/<int:comment_id>', methods=['POST'])
def report_comment(comment_id):
    increment_report(comment_id)
    n = request.args.get('n', 0)
    return redirect(url_for('index') + f'/?n={n}')

@app.route('/search', methods=['GET', 'POST'])
def search():
    conn = get_db_connection()
    search = request.form.get('search')

    searched_comments = conn.execute('SELECT * FROM comments WHERE comment LIKE ?', ('%'+search+'%', )).fetchall()
    conn.close()
    return render_template('index.html', comments=searched_comments, n = 0)

if __name__ == '__main__':
    app.run(debug=True, port=5002)
