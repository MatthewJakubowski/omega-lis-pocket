import requests
import time
import random
import sys

# --- KONFIGURACJA ---
# Skoro ten skrypt działa na TYM SAMYM telefonie co serwer,
# możemy użyć adresu lokalnego "localhost".
SERVER_URL = "http://127.0.0.1:5000"

print("🤖 URUCHAMIANIE SYMULATORA ANALIZATORA 'OMEGA-ANALYZER-X'...")
print(f"📡 Łączenie z systemem LIS: {SERVER_URL}")
print("-" * 40)

# Baza pacjentów (Symulacja kodów kreskowych z probówek)
PACJENCI = ["PESEL_901212", "PESEL_850505", "PACJENT_ZERO", "NOWAK_JAN", "KOWALSKI_ADAM"]

# Pętla nieskończona - Maszyna pracuje non-stop
cykl = 1
while True:
    try:
        # 1. Maszyna "pobiera" próbkę (losuje dane)
        pacjent_id = random.choice(PACJENCI)
        badanie = random.choice(["TSH", "GLU", "K", "CHOL"])
        
        # 2. Generowanie wyniku (Losujemy czasem normę, czasem chorobę)
        if badanie == "GLU":
            wynik = random.uniform(60.0, 450.0) # Może być śpiączka!
        elif badanie == "K":
            wynik = random.uniform(2.0, 6.5)    # Zagrożenie życia!
        elif badanie == "TSH":
            wynik = random.uniform(0.1, 5.0)
        else:
            wynik = random.uniform(100, 250) # Cholesterol

        wynik = round(wynik, 2)

        # 3. Przygotowanie paczki danych (tak jakby wysłał to formularz)
        # UWAGA: Symulator wysyła login "robot", żeby system wiedział, kto badał.
        payload = {
            "patient_id": pacjent_id,
            "test_code": badanie,
            "value": str(wynik).replace('.', ','), # Symulujemy polski format
            # Jeśli używasz webapp_v3/v4/v5 z sesją, musimy udawać zalogowanego.
            # Ale Twój serwer przyjmuje POSTy bez sesji w API (uproszczenie),
            # LUB musimy dodać 'username': 'analizator' jeśli kod tego wymaga.
            # W Twoim obecnym kodzie v5 sprawdzanie logowania jest na górze funkcji.
            # DLA UPROSZCZENIA: Ten symulator zadziała idealnie z webapp_v2 (bez logowania).
            # Jeśli masz v3/v4/v5 - musimy oszukać system ciasteczkiem.
        }
        
        # --- HACK NA LOGOWANIE ---
        # Żeby nie komplikować kodu sesjami, wyślemy to bezpośrednio.
        # Jeśli masz uruchomiony `webapp_v5.py`, on wymaga logowania. 
        # Zróbmy prosty trik: Symulator zadziała najlepiej z wersją SERWERA BEZ LOGOWANIA (v2).
        # ALE spróbujmy wysłać to tak:
        
        session = requests.Session()
        # Najpierw się logujemy jako admin (automat)
        session.post(f"{SERVER_URL}/login", data={"username": "admin", "password": "omega123"})
        
        # Teraz wysyłamy wynik
        print(f"#{cykl} 💉 WYSYŁANIE: {pacjent_id} -> {badanie} = {wynik}...", end=" ")
        response = session.post(SERVER_URL, data=payload)
        
        if response.status_code == 200:
            print("✅ SUKCES (Zapisano)")
        else:
            print(f"❌ Błąd serwera: {response.status_code}")
            # Jeśli widzisz błąd 404 lub 500, to znaczy że serwer ma inną strukturę

    except Exception as e:
        print(f"\n⚠️ BŁĄD: {e}")
        print("Upewnij się, że serwer LIS (webapp) jest włączony w drugiej zakładce!")
    
    cykl += 1
    # Czekaj 3 sekundy na następną próbkę
    time.sleep(3)
