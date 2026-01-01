import threading
import time
import random
import requests
import sqlite3
import datetime
from flask import Flask, render_template_string, request, redirect, url_for, session, make_response
from fpdf import FPDF

# ==========================================
# KONFIGURACJA
# ==========================================
app = Flask(__name__)
app.secret_key = "OMEGA_KEY"
DB_NAME = "laboratorium_omega.db"

# ==========================================
# 1. GENERATOR PDF (SILNIK DRUKARSKI)
# ==========================================
class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'OMEGA LABORATORIES', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 10, 'ul. Szpitalna 1, 00-001 Warszawa | Tel: 999-999-999', 0, 1, 'C')
        self.line(10, 30, 200, 30)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Strona {self.page_no()}', 0, 0, 'C')

def create_pdf(patient_id, results):
    pdf = PDFReport()
    pdf.add_page()
    
    # Dane Pacjenta
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f'RAPORT WYNIKOW BADAN', 0, 1, 'L')
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, f'Pacjent: {patient_id}', 0, 1, 'L')
    pdf.cell(0, 10, f'Data wydruku: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}', 0, 1, 'L')
    pdf.ln(10)
    
    # Nagłówki tabeli
    pdf.set_fill_color(200, 220, 255)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(40, 10, 'Badanie', 1, 0, 'C', 1)
    pdf.cell(40, 10, 'Wynik', 1, 0, 'C', 1)
    pdf.cell(40, 10, 'Jednostka', 1, 0, 'C', 1)
    pdf.cell(40, 10, 'Norma', 1, 0, 'C', 1)
    pdf.cell(30, 10, 'Status', 1, 1, 'C', 1)
    
    # Wiersze tabeli
    pdf.set_font('Arial', '', 10)
    for row in results:
        # Konwersja wszystkiego na tekst (str), aby uniknąć błędu "int has no len"
        test = str(row[2])
        val = str(row[3])
        unit = str(row[5])
        status = str(row[0])
        
        if status == "PANIC":
            pdf.set_text_color(255, 0, 0)
            pdf.set_font('Arial', 'B', 10)
        else:
            pdf.set_text_color(0, 0, 0)
            pdf.set_font('Arial', '', 10)
            
        # Bezpieczne wpisywanie do komórek
        pdf.cell(40, 10, test, 1, 0, 'C')
        pdf.cell(40, 10, val, 1, 0, 'C')
        pdf.cell(40, 10, unit, 1, 0, 'C')
        pdf.cell(40, 10, 'Norma', 1, 0, 'C')
        pdf.cell(30, 10, status, 1, 1, 'C')
        
    # Miejsce na podpis
    pdf.ln(20)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 10, '_' * 30, 0, 1, 'R')
    pdf.cell(0, 5, 'Podpis Diagnosty', 0, 1, 'R')

    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 2. LOGIKA SERWERA I BAZY
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("CREATE TABLE IF NOT EXISTS results (status TEXT, patient_id TEXT, test_code TEXT, value REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, unit TEXT)")
    conn.close()

REF_RANGES = {"TSH": {"unit": "uIU/ml"}, "GLU": {"unit": "mg/dl"}, "K": {"unit": "mmol/l"}}
CRITICAL = { "GLU": {"min": 40, "max": 400}, "K": {"min": 2.5, "max": 6.0} }

def evaluate(code, val):
    if code in CRITICAL and (val < CRITICAL[code]["min"] or val > CRITICAL[code]["max"]): return "PANIC"
    return "AUTO"

# HTML Z PRZYCISKIEM PDF
HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="refresh" content="7">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>OMEGA SYSTEM v3.0</title>
    <style>
        body { font-family: sans-serif; background: #f0f2f5; padding: 10px; }
        .card { background: white; padding: 15px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        h2 { color: #0056b3; border-bottom: 2px solid #ddd; padding-bottom: 10px; }
        table { width: 100%; border-collapse: collapse; font-size: 0.9em; }
        th { background: #333; color: white; padding: 10px; }
        td { padding: 8px; border-bottom: 1px solid #ddd; }
        .panic { color: red; font-weight: bold; }
        .auto { color: green; }
        .btn-pdf { background: #e74c3c; color: white; padding: 5px 10px; text-decoration: none; border-radius: 4px; font-size: 0.8em; }
    </style>
</head>
<body>
    <div class="card">
        <h2>🧬 OMEGA LIS: Panel Diagnosty</h2>
        <p>Symulator aktywny. Dane spływają w czasie rzeczywistym.</p>
    </div>
    
    <div class="card">
        <h3>Ostatnie Wyniki</h3>
        <table>
            <tr><th>Pacjent</th><th>Badanie</th><th>Wynik</th><th>Status</th><th>Akcja</th></tr>
            {% for r in rows %}
            <tr>
                <td><b>{{ r[1] }}</b></td>
                <td>{{ r[2] }}</td>
                <td>{{ r[3] }} {{ r[5] }}</td>
                <td class="{{ 'panic' if r[0] == 'PANIC' else 'auto' }}">{{ r[0] }}</td>
                <td><a href="/pdf/{{ r[1] }}" class="btn-pdf">📄 DRUKUJ PDF</a></td>
            </tr>
            {% endfor %}
        </table>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    conn = sqlite3.connect(DB_NAME)
    rows = conn.execute("SELECT * FROM results ORDER BY timestamp DESC LIMIT 20").fetchall()
    conn.close()
    return render_template_string(HTML, rows=rows)

@app.route('/', methods=['POST'])
def api(): # Endpoint dla symulatora
    try:
        p_id = request.form['patient_id']; code = request.form['test_code']
        val = float(request.form['value'].replace(',', '.'))
        unit = REF_RANGES.get(code, {}).get("unit", "-")
        status = evaluate(code, val)
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("INSERT INTO results (status, patient_id, test_code, value, unit) VALUES (?,?,?,?,?)", (status, p_id, code, val, unit))
        return "OK"
    except: return "ERR"

# --- GENEROWANIE PDF ---
@app.route('/pdf/<patient_id>')
def download_pdf(patient_id):
    conn = sqlite3.connect(DB_NAME)
    data = conn.execute("SELECT * FROM results WHERE patient_id = ? ORDER BY timestamp DESC LIMIT 10", (patient_id,)).fetchall()
    conn.close()
    
    try:
        pdf_bytes = create_pdf(patient_id, data)
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=Wynik_{patient_id}.pdf'
        return response
    except Exception as e:
        return f"BŁĄD PDF: {str(e)}"

# ==========================================
# 3. SYMULATOR (W TLE)
# ==========================================
def simulator():
    time.sleep(2)
    url = "http://127.0.0.1:5000/"
    patients = ["KOWALSKI_JAN", "NOWAK_ADAM", "PACJENT_ZERO", "PESEL_990101"]
    while True:
        try:
            p = random.choice(patients)
            t = random.choice(["GLU", "TSH", "K"])
            v = random.uniform(30, 450) if t == "GLU" else random.uniform(0.1, 7.0)
            requests.post(url, data={"patient_id": p, "test_code": t, "value": f"{v:.2f}"})
        except: pass
        time.sleep(4)

if __name__ == '__main__':
    init_db()
    threading.Thread(target=simulator, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)

        
