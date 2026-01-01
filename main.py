import threading
import time
import random
import requests
import sqlite3
import datetime
import socket
from flask import Flask, render_template_string, request, redirect, url_for, session, make_response
from fpdf import FPDF

# --- KONFIGURACJA ---
app = Flask(__name__)
app.secret_key = "ULTIMATE_KEY_2026"
DB_NAME = "omega_ultimate.db" # Nowa baza dla wersji Ultimate
USERS = {"admin": "omega"}      # Login: admin, Hasło: omega

# --- LOGIKA MEDYCZNA ---
REF_RANGES = {
    "TSH": {"unit": "uIU/ml", "min": 0.27, "max": 4.20}, 
    "GLU": {"unit": "mg/dl", "min": 70.0, "max": 99.0}, 
    "K": {"unit": "mmol/l", "min": 3.5, "max": 5.1},
    "CHOL": {"unit": "mg/dl", "min": 0, "max": 190}
}
CRITICAL = { "GLU": {"min": 40.0, "max": 400.0}, "K": {"min": 2.5, "max": 6.5} }

def evaluate_result(code, val):
    if code in CRITICAL:
        if val < CRITICAL[code]["min"] or val > CRITICAL[code]["max"]: return "PANIC"
    if code in REF_RANGES:
        if val < REF_RANGES[code]["min"] or val > REF_RANGES[code]["max"]: return "REVIEW"
    return "AUTO"

# --- BAZA DANYCH ---
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT, test_code TEXT, value REAL, 
                unit TEXT, status TEXT, source TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

# --- GENERATOR PDF ---
class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'OMEGA LABORATORIES', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 10, 'System Mobilny LIS v1.0 | Podkarpackie', 0, 1, 'C')
        self.line(10, 25, 200, 25)
        self.ln(10)

def generate_pdf(patient_id, data):
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f'PACJENT: {patient_id}', 0, 1)
    pdf.cell(0, 10, f'DATA: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}', 0, 1)
    pdf.ln(5)
    
    # Nagłówki
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font('Arial', 'B', 10)
    for h in ['Badanie', 'Wynik', 'Jednostka', 'Status', 'Zrodlo']: pdf.cell(38, 10, h, 1, 0, 'C', 1)
    pdf.ln()
    
    # Dane
    pdf.set_font('Arial', '', 10)
    for row in data:
        # row: (test, val, unit, status, source)
        pdf.set_text_color(255,0,0) if row[3]=="PANIC" else pdf.set_text_color(0)
        for item in row: pdf.cell(38, 10, str(item), 1, 0, 'C')
        pdf.ln()
        
    # Podpis
    pdf.ln(20)
    pdf.set_text_color(0)
    pdf.cell(0, 10, "_"*30, 0, 1, 'R')
    pdf.cell(0, 10, "Podpis Diagnosty", 0, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFEJS HTML (TOTALNY) ---
HTML_LOGIN = """
<!DOCTYPE html>
<html>
<body style="background:#121212; color:white; font-family:sans-serif; display:flex; justify-content:center; align-items:center; height:100vh; margin:0;">
    <div style="background:#1e1e1e; padding:40px; border-radius:15px; text-align:center; box-shadow:0 10px 30px rgba(0,0,0,0.5); width:300px;">
        <div style="font-size:50px; margin-bottom:10px;">🧬</div>
        <h2 style="margin:0 0 20px 0; color:#bb86fc;">OMEGA SYSTEM</h2>
        <form method="POST">
            <input type="text" name="username" placeholder="Login (admin)" style="padding:15px; width:100%; margin:5px 0; border:none; border-radius:8px; background:#333; color:white;"><br>
            <input type="password" name="password" placeholder="Haslo (omega)" style="padding:15px; width:100%; margin:5px 0; border:none; border-radius:8px; background:#333; color:white;"><br>
            <button type="submit" style="padding:15px; background:#bb86fc; border:none; color:black; font-weight:bold; cursor:pointer; width:100%; border-radius:8px; margin-top:15px;">ZALOGUJ DO SYSTEMU</button>
        </form>
    </div>
</body>
</html>
"""

HTML_DASHBOARD = """
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="refresh" content="7"> <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>OMEGA ULTIMATE</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #121212; color: #e0e0e0; padding: 10px; margin:0; }
        .nav { background: #1f1f1f; padding: 15px; border-radius:10px; display:flex; justify-content:space-between; align-items:center; border: 1px solid #333; }
        .card { background: #1e1e1e; padding: 15px; margin-top: 15px; border-radius: 10px; border: 1px solid #333; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        h3 { margin-top: 0; color: #bb86fc; border-bottom: 1px solid #333; padding-bottom: 10px; }
        
        /* FORMULARZ I SKANER */
        input, select, button { width: 100%; padding: 12px; margin: 5px 0; border-radius: 6px; border: 1px solid #444; background: #2c2c2c; color: white; box-sizing: border-box;}
        .btn-scan { background: #03dac6; color: black; font-weight: bold; border: none; cursor: pointer; }
        .btn-submit { background: #bb86fc; color: black; font-weight: bold; border: none; cursor: pointer; }
        
        /* TABELA */
        table { width: 100%; border-collapse: collapse; font-size: 0.85em; margin-top: 10px; }
        th { background: #2c2c2c; color: #bb86fc; padding: 10px; text-align: left; }
        td { padding: 10px; border-bottom: 1px solid #333; }
        .PANIC { color: #cf6679; font-weight: bold; }
        .AUTO { color: #03dac6; }
        .source-IoT { color: #aaaaaa; font-style: italic; }
        .source-MANUAL { color: #ffb74d; font-weight: bold; }
        .btn-pdf { background: #cf6679; color: black; text-decoration: none; padding: 5px 10px; border-radius: 4px; font-weight:bold; font-size: 0.8em; }
        
        /* UKRYTY INPUT KAMERY */
        #cameraInput { display: none; }
    </style>
</head>
<body>
    <div class="nav">
        <span>👨‍⚕️ <b>Operator: {{ user }}</b></span>
        <a href="/logout" style="color:#cf6679; text-decoration:none;">Wyloguj</a>
    </div>

    <div class="card">
        <h3>📸 Przyjęcie Próbki (Manual / Scan)</h3>
        
        <input type="file" id="cameraInput" accept="image/*" capture="environment">
        <button class="btn-scan" onclick="document.getElementById('cameraInput').click()">📷 URUCHOM APARAT (SKANUJ KOD)</button>
        <p id="scanStatus" style="color: gray; font-size: 0.8em; text-align: center; margin: 5px;">Zrób zdjęcie kodu kreskowego lub wpisz ręcznie.</p>

        <form method="POST" action="/manual_add">
            <input type="text" id="patient_id" name="patient_id" placeholder="ID Pacjenta (np. z kodu)" required>
            <div style="display:flex; gap:5px;">
                <select name="test_code" style="flex:1;">
                    <option value="TSH">TSH</option>
                    <option value="GLU">Glukoza</option>
                    <option value="K">Potas</option>
                    <option value="CHOL">Cholesterol</option>
                </select>
                <input type="number" step="0.01" name="value" placeholder="Wynik" style="flex:1;" required>
            </div>
            <button type="submit" class="btn-submit">ZATWIERDŹ WYNIK</button>
        </form>
    </div>

    <div class="card">
        <h3>📡 Baza Danych (Live Feed)</h3>
        <table>
            <thead><tr><th>Czas</th><th>Pacjent</th><th>Badanie</th><th>Wynik</th><th>Źródło</th><th>Akcja</th></tr></thead>
            <tbody>
                {% for r in rows %}
                <tr>
                    <td>{{ r[6][11:19] }}</td>
                    <td><b>{{ r[1] }}</b></td>
                    <td>{{ r[2] }}</td>
                    <td class="{{ r[5] }}">{{ r[3] }} {{ r[4] }}</td>
                    <td class="source-{{ r[6] }}">{{ r[6] }}</td> <td><a href="/pdf/{{ r[1] }}" class="btn-pdf">PDF</a></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <script>
        const fileInput = document.getElementById('cameraInput');
        const statusTxt = document.getElementById('scanStatus');
        const idField = document.getElementById('patient_id');

        if ('BarcodeDetector' in window) {
            const barcodeDetector = new BarcodeDetector({formats: ['qr_code', 'ean_13', 'code_128', 'code_39', 'data_matrix']});
            fileInput.addEventListener('change', async (e) => {
                const file = e.target.files[0];
                if (!file) return;
                statusTxt.innerHTML = "⏳ Analiza zdjęcia...";
                try {
                    const image = await createImageBitmap(file);
                    const barcodes = await barcodeDetector.detect(image);
                    if (barcodes.length > 0) {
                        idField.value = barcodes[0].rawValue;
                        statusTxt.innerHTML = "✅ ODCZYTANO: " + barcodes[0].rawValue;
                        statusTxt.style.color = "#03dac6";
                    } else {
                        statusTxt.innerHTML = "❌ Nie wykryto kodu. Wpisz ręcznie.";
                        statusTxt.style.color = "#cf6679";
                    }
                } catch (err) { statusTxt.innerHTML = "Błąd skanera: " + err; }
            });
        }
    </script>
</body>
</html>
"""

# --- BACKEND (FLASK) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] in USERS: # Uproszczone logowanie
            session['logged_in'] = True; session['user'] = request.form['username']
            return redirect(url_for('dashboard'))
    return render_template_string(HTML_LOGIN)

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/')
def dashboard():
    if not session.get('logged_in'): return redirect(url_for('login'))
    with sqlite3.connect(DB_NAME) as conn:
        # Pobieramy ostatnie 15 wyników
        rows = conn.execute("SELECT * FROM results ORDER BY id DESC LIMIT 15").fetchall()
    return render_template_string(HTML_DASHBOARD, rows=rows, user=session['user'])

# Endpoint: Ręczne dodawanie (z formularza)
@app.route('/manual_add', methods=['POST'])
def manual_add():
    if not session.get('logged_in'): return redirect(url_for('login'))
    try:
        p_id = request.form['patient_id']
        code = request.form['test_code']
        val = float(request.form['value'].replace(',', '.'))
        unit = REF_RANGES.get(code, {}).get("unit", "-")
        status = evaluate_result(code, val)
        
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("INSERT INTO results (patient_id, test_code, value, unit, status, source) VALUES (?,?,?,?,?,?)", 
                         (p_id, code, val, unit, status, "MANUAL"))
            conn.commit()
    except: pass
    return redirect(url_for('dashboard'))

# Endpoint: Automat (Symulator)
@app.route('/api/result', methods=['POST'])
def api():
    try:
        data = request.form
        p_id, code = data['patient_id'], data['test_code']
        val = float(data['value'].replace(',', '.'))
        unit = REF_RANGES.get(code, {}).get("unit", "-")
        status = evaluate_result(code, val)
        
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("INSERT INTO results (patient_id, test_code, value, unit, status, source) VALUES (?,?,?,?,?,?)", 
                         (p_id, code, val, unit, status, "IoT"))
            conn.commit()
        return "OK"
    except: return "ERR"

# Endpoint: PDF
@app.route('/pdf/<patient_id>')
def pdf(patient_id):
    with sqlite3.connect(DB_NAME) as conn:
        data = conn.execute("SELECT test_code, value, unit, status, source FROM results WHERE patient_id=? ORDER BY id DESC LIMIT 10", (patient_id,)).fetchall()
    resp = make_response(generate_pdf(patient_id, data))
    resp.headers['Content-Type'] = 'application/pdf'
    resp.headers['Content-Disposition'] = f'attachment; filename=Wynik_{patient_id}.pdf'
    return resp

# --- SYMULATOR W TLE ---
def run_simulator():
    time.sleep(3)
    target = "http://127.0.0.1:5000/api/result"
    patients = ["JAN_KOWALSKI", "ADAM_NOWAK", "PACJENT_ZERO"]
    while True:
        try:
            p = random.choice(patients)
            t = random.choice(["GLU", "TSH", "K"])
            v = random.uniform(30, 450) if t == "GLU" else random.uniform(0.1, 7.0)
            requests.post(target, data={"patient_id": p, "test_code": t, "value": f"{v:.2f}"})
            print(f"💉 IoT SEND: {p} -> {t}")
        except: pass
        time.sleep(4) # Co 4 sekundy nowy wynik z maszyny

if __name__ == '__main__':
    init_db()
    threading.Thread(target=run_simulator, daemon=True).start()
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]; s.close()
        print(f"\n🚀 SYSTEM ULTIMATE GOTOWY: http://{ip}:5000\n")
    except: pass
    
    app.run(host='0.0.0.0', port=5000)
    
    """
⚠️  OMEGA LIS - LIABILITY WAIVER & DISCLAIMER  ⚠️

This software is for EDUCATIONAL USE ONLY.
It is NOT a certified medical device.
DO NOT use for real patient diagnosis or treatment.

The author assumes no liability for any consequences 
resulting from the use of this software.

All patient data generated by this system is FAKE.
"""

