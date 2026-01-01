from flask import Flask, render_template_string, request, redirect, url_for, session
import sqlite3

app = Flask(__name__)
app.secret_key = "OMEGA_SECRET_KEY_2026"
DB_NAME = "laboratorium_omega.db"
USERS = {"admin": "omega123", "laborant": "lab2026"}

# --- BAZA WIEDZY (NORMY) ---
REF_RANGES = {
    "TSH": {"min": 0.27, "max": 4.20, "unit": "uIU/ml"},
    "GLU": {"min": 70.0, "max": 99.0, "unit": "mg/dl"},
    "K": {"min": 3.5, "max": 5.1, "unit": "mmol/l"},
    "CHOL": {"min": 0, "max": 190, "unit": "mg/dl"}
}
CRITICAL_RANGES = { "GLU": {"min": 40.0, "max": 400.0}, "K": {"min": 2.5, "max": 6.0} }

def evaluate_result(test_code, value):
    if test_code in CRITICAL_RANGES:
        crit = CRITICAL_RANGES[test_code]
        if value < crit["min"] or value > crit["max"]: return "PANIC"
    if test_code in REF_RANGES:
        ref = REF_RANGES[test_code]
        if value < ref["min"] or value > ref["max"]: return "REVIEW"
    return "AUTO"

# --- HTML Z NATYWNYM SKANEREM (OFFLINE) ---
HTML_DASHBOARD = """
<!DOCTYPE html>
<html>
<head>
    <title>OMEGA LIS - Native</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: 'Segoe UI', sans-serif; background-color: #f0f2f5; padding: 10px; margin: 0; }
        .navbar { background: #0056b3; color: white; padding: 15px; display: flex; justify-content: space-between; border-radius: 5px; margin-bottom: 20px; }
        .card { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; }
        input, select, button { width: 100%; padding: 12px; margin: 8px 0; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
        
        /* Specjalny przycisk aparatu */
        .camera-btn { 
            background-color: #8e44ad; color: white; font-weight: bold; border: none; 
            padding: 15px; font-size: 1.1em; display: flex; align-items: center; justify-content: center;
        }
        
        /* Ukryty input pliku - to nasz trik */
        #cameraInput { display: none; }
        
        .status-PANIC { color: red; font-weight: 900; }
        .status-AUTO { color: green; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; font-size: 0.9em; margin-top: 10px; }
        td, th { padding: 10px; border-bottom: 1px solid #ddd; text-align: left; }
    </style>
</head>
<body>
    <div class="navbar">
        <strong>🏥 Operator: {{ user }}</strong>
        <a href="/logout" style="color: white;">Wyloguj</a>
    </div>

    <div class="card">
        <h3>📸 Skaner (Tryb Offline)</h3>
        
        <input type="file" id="cameraInput" accept="image/*" capture="environment">
        
        <button class="camera-btn" onclick="document.getElementById('cameraInput').click()">
            📷 ZROB ZDJĘCIE KODU
        </button>
        <p id="scanStatus" style="color: gray; font-size: 0.8em; text-align: center;">Kliknij przycisk, zrób zdjęcie kodu kreskowego, a system go odczyta.</p>

        <form method="POST">
            <label>ID Pacjenta (z kodu):</label>
            <input type="text" id="patient_id" name="patient_id" placeholder="Czekam na skan..." required>
            
            <select name="test_code">
                <option value="TSH">TSH</option>
                <option value="GLU">GLU</option>
                <option value="K">K (Potas)</option>
                <option value="CHOL">Cholesterol</option>
            </select>
            <input type="number" step="0.01" name="value" placeholder="Wynik" required>
            <button type="submit" style="background-color: #27ae60; color: white; border: none;">ZATWIERDŹ</button>
        </form>
    </div>
    
    <div class="card">
        <h3>Wyniki</h3>
        <table>
            {% for row in results %}
            <tr>
                <td>{{ row[1] }}</td>
                <td><b>{{ row[2] }}</b>: {{ row[3] }}</td>
                <td class="status-{{ row[0] }}">{{ row[0] }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>

    <script>
        const fileInput = document.getElementById('cameraInput');
        const statusTxt = document.getElementById('scanStatus');
        const idField = document.getElementById('patient_id');

        // Sprawdzamy czy przeglądarka obsługuje "BarcodeDetector" (Chrome/Android ma to wbudowane)
        if (!('BarcodeDetector' in window)) {
            statusTxt.innerHTML = "⚠️ Twoja przeglądarka nie ma wbudowanego detektora. Wpisz kod ręcznie.";
        } else {
            const barcodeDetector = new BarcodeDetector({formats: ['qr_code', 'ean_13', 'code_128', 'code_39']});

            fileInput.addEventListener('change', async (e) => {
                const file = e.target.files[0];
                if (!file) return;

                statusTxt.innerHTML = "⏳ Analiza zdjęcia...";
                
                try {
                    // Tworzymy obraz w pamięci
                    const image = await createImageBitmap(file);
                    // Skanujemy go natywnym silnikiem Chrome
                    const barcodes = await barcodeDetector.detect(image);
                    
                    if (barcodes.length > 0) {
                        const code = barcodes[0].rawValue;
                        idField.value = code;
                        statusTxt.innerHTML = "✅ SUKCES! Odczytano: " + code;
                        // Odtwórz dźwięk sukcesu (opcjonalne)
                        // new Audio('https://actions.google.com/sounds/v1/science_fiction/scifi_input_accept.ogg').play();
                    } else {
                        statusTxt.innerHTML = "❌ Nie wykryto kodu na zdjęciu. Spróbuj zbliżyć aparat.";
                    }
                } catch (err) {
                    statusTxt.innerHTML = "❌ Błąd: " + err;
                }
            });
        }
    </script>
</body>
</html>
"""

# Reszta backendu (bez zmian)
HTML_LOGIN = """<!DOCTYPE html><html><body style="font-family:sans-serif;background:#2c3e50;display:flex;justify-content:center;align-items:center;height:100vh;"><div style="background:white;padding:40px;border-radius:10px;"><form method="POST"><input type="text" name="username" placeholder="Login"><input type="password" name="password" placeholder="Hasło"><button type="submit">OK</button></form></div></body></html>"""

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] in USERS and USERS[request.form['username']] == request.form['password']:
            session['logged_in'] = True; session['user'] = request.form['username']; return redirect(url_for('index'))
    return render_template_string(HTML_LOGIN)

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
def index():
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    if request.method == 'POST':
        p_id = request.form['patient_id']; code = request.form['test_code']
        val = float(request.form['value'].replace(',', '.'))
        status = evaluate_result(code, val)
        unit = REF_RANGES.get(code, {}).get("unit", "-")
        cursor.execute("INSERT INTO results (patient_id, test_code, value, unit, status) VALUES (?, ?, ?, ?, ?)", (p_id, code, val, unit, status))
        conn.commit(); return redirect(url_for('index'))
    data = cursor.execute("SELECT status, patient_id, test_code, value, timestamp, unit FROM results ORDER BY timestamp DESC LIMIT 10").fetchall()
    conn.close()
    return render_template_string(HTML_DASHBOARD, results=data, user=session['user'])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
