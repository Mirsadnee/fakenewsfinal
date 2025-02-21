import hashlib
import os
import secrets
import string
import nltk
import pyotp
import requests
import pickle
import random
import time
import re
from flask_mail import Mail, Message
from flask import Flask, flash, render_template, request, redirect, url_for, session
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.security import check_password_hash
import mysql.connector
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import PassiveAggressiveClassifier


nltk.download('punkt')
nltk.download('stopwords')
nltk.download('wordnet')
nltk.download('omw-1.4')

# Krijimi i instancës së Flask
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(16))

# Lidhja me bazën e të dhënave MySQL
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",  # Vendosni fjalëkalimin tuaj të MySQL këtu, nëse ekziston
        database="fake_news_detection"
    )


# Ngarko modelin dhe vektorizuesin e ruajtur
loaded_model = pickle.load(open("model.pkl", 'rb'))
vector = pickle.load(open("vector.pkl", 'rb'))
lemmatizer = WordNetLemmatizer()
stpwrds = set(stopwords.words('english'))

# Testo modelin dhe vektorizuesin jashtë aplikacionit
test_text = "This is a test news article."
vectorized_test = vector.transform([test_text])
try:
    test_pred = loaded_model.predict(vectorized_test)
    print("Test prediction:", test_pred)
except Exception as e:
    print("Error testing model:", str(e))

# Funksioni për aksesimin e përdoruesve nga DB
def get_user(username):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    return cursor.fetchone()

def is_admin(username):
    user = get_user(username)
    return user['is_admin'] if user else False

def add_user(username, password, email, is_admin=False):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        encrypted_password = generate_password_hash(password)  # Ndryshohet kjo linjë
        query = "INSERT INTO users (username, password, email, is_admin) VALUES (%s, %s, %s, %s)"
        cursor.execute(query, (username, encrypted_password, email, is_admin))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"Përdoruesi {username} u shtua me sukses.")
    except mysql.connector.Error as e:
        print(f"Gabim gjatë shtimit të përdoruesit në bazën e të dhënave: {e}")
        raise






def update_user_otp(username, otp):
    conn = get_db_connection()
    cursor = conn.cursor()
    otp_expiry = datetime.now() + timedelta(minutes=5)
    cursor.execute("UPDATE users SET otp = %s, otp_created_at = %s WHERE username = %s", (otp, otp_expiry, username))
    conn.commit()

def validate_otp(username, otp):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT otp, otp_created_at FROM users WHERE username = %s", (username,))
    result = cursor.fetchone()
    if result:
        if result['otp'] == otp and datetime.now() <= result['otp_created_at']:
            return True
    return False

# Funksioni për detektimin e lajmeve të rreme
def fake_news_det(news):
    print("Original message:", news)
    review = re.sub(r'[^a-zA-Z\s]', '', news.lower())
    print("After removing non-alphabetic characters:", review)
    review = nltk.word_tokenize(review)
    print("Tokenized words:", review)
    corpus = [lemmatizer.lemmatize(word) for word in review if word not in stpwrds]
    print("Lemmatized words:", corpus)
    input_data = [' '.join(corpus)]
    print("Final input for model:", input_data)
    vectorized_input_data = vector.transform(input_data)
    print("Vectorized input:", vectorized_input_data)
    try:
        prediction = loaded_model.predict(vectorized_input_data)
        print("Prediction:", prediction)
    except Exception as e:
        print("Error during prediction:", str(e))
        return ["error"]  # Return an error result for debugging
    return prediction



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        print(f"Po përpiqet të bëjë login me përdoruesin: {username}")  # Debugging

        user = get_user(username)

        if user and check_password_hash(user['password'], password):
            session['logged_in'] = True
            session['username'] = username
            session['otp_verified'] = False
            print(f"Përdoruesi {username} u logua me sukses!")  # Debugging
            otp = random.randint(100000, 999999)
            update_user_otp(username, otp)
            print(f"OTP për përdoruesin {username} është: {otp}")  # Debugging

            if is_admin(username):
                session['is_admin'] = True

            return redirect(url_for('verify_otp'))
        else:
            flash("Kredencialet janë të pasaktë!", "danger")
            print("Kredencialet janë të pasaktë!")  # Debugging
    return render_template('login.html')



@app.route('/admin')
def admin_dashboard():
    # Merr të gjithë përdoruesit nga baza e të dhënave
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()  # Këtu merrni të gjithë përdoruesit nga DB
    conn.close()  # Mbyll lidhjen me DB
    return render_template('admin_dashboard.html', users=users)

@app.route('/admin/add-user', methods=['POST'])
def add_user_route():
    username = request.form['new_admin_username']
    email = request.form['new_admin_email']
    password = request.form['new_admin_password']
    is_admin = 'new_admin_role' in request.form
    add_user(username, password, email, is_admin)
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/update-user', methods=['POST'])
def update_user():
    user_id = int(request.form['user_id'])
    username = request.form['username']
    email = request.form['email']
    is_admin = 'is_admin' in request.form

    # Lidhja me bazën e të dhënave dhe përditësimi i të dhënave të përdoruesit
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users 
        SET username = %s, email = %s, is_admin = %s 
        WHERE id = %s
    """, (username, email, is_admin, user_id))
    conn.commit()  # Konfirmo ndryshimet
    conn.close()  # Mbyll lidhjen me DB

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-user', methods=['POST'])
def delete_user():
    user_id = int(request.form['user_id'])

    # Lidhja me bazën e të dhënave dhe fshirja e përdoruesit
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()  # Konfirmo fshirjen
    conn.close()  # Mbyll lidhjen me DB

    return redirect(url_for('admin_dashboard'))

# Rruga për verifikimin e OTP
@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        entered_otp = request.form['otp']
        if validate_otp(session['username'], entered_otp):
            session['otp_verified'] = True  # Përditëso ndryshoren në sesion
            flash("OTP e verifikuar me sukses!", "success")
            return redirect(url_for('home'))
        else:
            flash("OTP është e pasaktë ose ka skaduar!", "danger")
    
    return render_template('verify_otp.html')

# Rruga për faqen kryesore
@app.route('/')
def home():
    if 'logged_in' in session and session.get('otp_verified'):
        return render_template('index.html')
    elif 'logged_in' in session:
        return redirect(url_for('verify_otp'))
    return redirect(url_for('login'))

# Rruga për parashikimin
@app.route('/predict', methods=['GET', 'POST'])
def predict():
    if request.method == 'POST':
        message = request.form['news']  # Merr tekstin e futur nga përdoruesi
        pred = fake_news_det(message)  # Thirr funksionin për parashikim

        # Vendos logjikën për të përcaktuar rezultatin
        if pred[0] == 1:
            result = "Fake News 📰"
        else:
            result = "Real News 📰"

        # Kalo rezultatin te shablloni
        return render_template('prediction.html', prediction=result)

    # Nëse metoda është GET, shfaq faqen pa rezultat
    return render_template('prediction.html', prediction=None)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if not username or not email or not password:
            flash('Të gjitha fushat janë të detyrueshme.')
            return redirect(url_for('register'))

        try:
            add_user(username, password, email)
            flash('Regjistrimi u krye me sukses! Mund të kyçeni tani.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash('Gabim gjatë regjistrimit: ' + str(e), 'danger')
           
    return render_template('register.html')




# Rruga për kërkesën për harresë fjalëkalimi
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']

        # Kontrollo nëse emaili ekziston në bazën e të dhënave
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user:
            # Gjenero një OTP dhe përditëso përdoruesin
            otp = random.randint(100000, 999999)
            update_user_otp(user['username'], otp)
            flash(f"Një kod për verifikim është dërguar në emailin tuaj ({email}).", "info")
            print(f"OTP për {email}: {otp}")  # Printo OTP për testim
            session['reset_username'] = user['username']  # Ruaj username për sesion
            return redirect(url_for('reset_password'))
        else:
            flash("Emaili i futur nuk ekziston në sistem!", "danger")
    
    return render_template('forgot_password.html')

# Rruga për rivendosjen e fjalëkalimit
@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if 'reset_username' not in session:
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        otp = request.form['otp']
        new_password = request.form['new_password']

        # Verifiko OTP-në dhe përditëso fjalëkalimin
        if validate_otp(session['reset_username'], otp):
            conn = get_db_connection()
            cursor = conn.cursor()
            hashed_password = generate_password_hash(new_password)
            cursor.execute("UPDATE users SET password = %s WHERE username = %s", 
                           (hashed_password, session['reset_username']))
            conn.commit()
            conn.close()

            flash("Fjalëkalimi është rivendosur me sukses! Mund të bëni login tani.", "success")
            session.pop('reset_username', None)
            return redirect(url_for('login'))
        else:
            flash("OTP është e pasaktë ose ka skaduar!", "danger")
    
    return render_template('reset_password.html')

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'username' not in session:
        flash("Ju lutem kyçuni për të parë profilin tuaj.", "warning")
        return redirect(url_for('login'))

    username = session['username']

    # Lidhja me bazën e të dhënave për të marrë informacionet e përdoruesit
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()

    if not user:
        flash("Përdoruesi nuk ekziston!", "danger")
        return redirect(url_for('logout'))

    if request.method == 'POST':
        new_email = request.form['email']
        new_password = request.form['password']

        # Përditësimi i email-it dhe fjalëkalimit (nëse është i dhënë)
        update_query = "UPDATE users SET email = %s"
        values = [new_email]

        if new_password.strip():  # Kontrollo nëse është futur një fjalëkalim i ri
            hashed_password = generate_password_hash(new_password)
            update_query += ", password = %s"
            values.append(hashed_password)

        update_query += " WHERE username = %s"
        values.append(username)

        cursor.execute(update_query, values)
        conn.commit()
        conn.close()

        flash("Të dhënat tuaja janë përditësuar me sukses!", "success")
        return redirect(url_for('profile'))

    return render_template('profile.html', user=user)


# Rruga për logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    
    app.run(host='127.0.0.1', port=5000)