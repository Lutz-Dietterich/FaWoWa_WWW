# main.py -- put your code here!
import os
import network
import espnow
import time
import socket
import ujson as json
import gc  # Importiere Garbage Collector

# Funktion zum Initialisieren von ESP-NOW
def init_espnow():
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    e = espnow.ESPNow()
    e.active(True)
    print("ESP-NOW erfolgreich aktiviert")
    return e

# ESP-NOW und WLAN initialisieren
e = init_espnow()

# Füge den Sender als Peer hinzu (MAC-Adresse des Senders)
peer = b'\x08\xd1\xf9\xe2\x98\xe0'  # MAC-Adresse des Senders hier eingeben
try:
    e.add_peer(peer)
except Exception as ex:
    print(f"Fehler beim Hinzufügen des Peers: {ex}")

# Variable zum Speichern der empfangenen Daten
espnow_data = {'temperature': 'N/A', 'humidity': 'N/A'}

# Funktion zum Speichern der Daten im Flash-Speicher
def save_data_to_flash(espnow_data):
    try:
        if 'data.json' not in os.listdir():
            with open('data.json', 'w') as f:
                json.dump([], f)  # Erstelle eine leere JSON-Liste
        
        with open('data.json', 'r') as f:
            data = json.load(f)
        
        data.append({'timestamp': time.time(), 'temperature': espnow_data['temperature'], 'humidity': espnow_data['humidity']})
        
        with open('data.json', 'w') as f:
            json.dump(data, f)
        print("Daten erfolgreich im Flash-Speicher gespeichert.")
        
        # Speicher bereinigen
        gc.collect()  # Markierung: Garbage Collector wird aktiviert, um RAM zu bereinigen
    except Exception as e:
        print(f"Fehler beim Speichern der Daten: {e}")

# Funktion zum Empfangen von ESP-NOW Nachrichten
def check_espnow(e, espnow_data):
    if e.any():  # Prüfen, ob Nachrichten vorhanden sind
        try:
            peer, msg = e.recv()
            if msg:  # Prüfen, ob eine Nachricht empfangen wurde
                message = msg.decode('utf-8')
                print(f'Nachricht von {peer}: {message}')
                if "Temperatur" in message:
                    try:
                        temp_str = message.split("Temperatur: ")[1].split("C")[0].strip()  # Entfernt das 'C' am Ende der Temperatur
                        hum_str = message.split("Luftfeuchtigkeit: ")[1].split("%")[0]
                        espnow_data['temperature'] = float(temp_str)  # Temperatur als Float speichern, damit keine Probleme beim Parsen auftreten
                        espnow_data['humidity'] = hum_str
                        print(f"Empfangene Temperatur: {espnow_data['temperature']}°C")
                        print(f"Empfangene Feuchtigkeit: {espnow_data['humidity']}%")
                        save_data_to_flash(espnow_data)  # Speichern der Daten im Flash-Speicher
                        
                        return True  # Daten empfangen, kann mit WLAN und Webserver fortfahren
                    except (IndexError, ValueError) as e:
                        print(f"Fehler beim Verarbeiten der Nachricht: {e}")
            else:
                print("Keine Nachricht empfangen")
        except Exception as e:
            print(f"Fehler beim Empfang: {e}")
    return False  # Keine Daten empfangen


# Funktion zum Starten des Webservers auf Port 80
def start_webserver(espnow_data):
    try:
        addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Ermöglicht die Wiederverwendung des Ports
        s.bind(addr)
        s.listen(1)
        print('Webserver läuft auf Port 80')
        return s
    except OSError as e:
        print("Fehler beim Binden an Port 80:", e)
        return None


# Funktion zum Verarbeiten von Client-Anfragen
def handle_client(s, espnow_data):
    try:
        s.settimeout(2)  # Erhöhe den Timeout auf 2 Sekunden, damit der Server nicht zu schnell blockiert
        cl, addr = s.accept()
        print('Client verbunden von', addr)
        request = cl.recv(1024).decode()
        print(request)

        # Prüfen, ob die Anfrage nach '/data.json' erfolgt
        if request.startswith('GET /data.json'):
            # Daten für JSON-Antwort laden
            graph_data = []
            try:
                if 'data.json' in os.listdir():
                    with open('data.json', 'r') as f:
                        graph_data = json.load(f)
            except Exception as e:
                print(f"Fehler beim Laden der Daten: {e}")

            # JSON-Daten an den Client senden
            cl.send('HTTP/1.1 200 OK')
            cl.send('Content-Type: application/json')
            cl.send('Connection: close\r\n\r\n')
            cl.sendall(json.dumps(graph_data))
            cl.close()
            return

        # Daten für den Graphen laden
        graph_data = []
        try:
            if 'data.json' in os.listdir():
                with open('data.json', 'r') as f:
                    graph_data = json.load(f)
        except Exception as e:
            print(f"Fehler beim Laden der Daten: {e}")

        # HTML-Seite generieren
        response = f"""
        <html>
        <head>
            <title>ESP-NOW & Webserver</title>
            <meta charset="UTF-8">  <!-- Sicherstellen, dass UTF-8 verwendet wird -->
            <script src="https://cdn.jsdelivr.net/npm/moment@2.29.1/min/moment.min.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-moment@1.0.0"></script>
        </head>
        <body>
            <h1>ESP-NOW Sensordaten</h1>
            <p>Temperatur: {espnow_data['temperature']}°C</p>
            <p>Feuchtigkeit: {espnow_data['humidity']}%</p>
            <h2>Temperatur-Verlauf</h2>
            <canvas id="tempChart" width="400" height="200"></canvas>
            <h2>Feuchtigkeits-Verlauf</h2>
            <canvas id="humChart" width="400" height="200"></canvas>
            <script>
                var tempCtx = document.getElementById('tempChart').getContext('2d');
                var humCtx = document.getElementById('humChart').getContext('2d');
                
                var tempData = {{labels: [], datasets: [{{label: 'Temperatur (°C)', data: [], borderColor: 'red', fill: false}}]}};
                var humData = {{labels: [], datasets: [{{label: 'Feuchtigkeit (%)', data: [], borderColor: 'blue', fill: false}}]}};

                var jsonData = {graph_data};
                jsonData.forEach(function(item) {{
                    var date = new Date(item.timestamp * 1000);
                    var formattedDate = moment(date).toISOString();
                    tempData.labels.push(formattedDate);
                    humData.labels.push(formattedDate);
                    tempData.datasets[0].data.push(item.temperature);
                    humData.datasets[0].data.push(item.humidity);
                }});

                var tempChart = new Chart(tempCtx, {{
                    type: 'line',
                    data: tempData,
                    options: {{
                        responsive: true,
                        scales: {{
                            x: {{
                                type: 'time',
                                time: {{
                                    unit: 'minute',
                                    tooltipFormat: 'YYYY-MM-DDTHH:mm:ssZ'
                                }}
                            }},
                            y: {{
                                min: -5,
                                max: 50,
                                ticks: {{
                                    stepSize: 5
                                }}
                            }}
                        }}
                    }}
                }});

                var humChart = new Chart(humCtx, {{
                    type: 'line',
                    data: humData,
                    options: {{
                        responsive: true,
                        scales: {{
                            x: {{
                                type: 'time',
                                time: {{
                                    unit: 'minute',
                                    tooltipFormat: 'YYYY-MM-DDTHH:mm:ssZ'
                                }}
                            }},
                            y: {{
                                beginAtZero: true
                            }}
                        }}
                    }}
                }});

                setInterval(function() {{
                    fetch('/data.json')
                        .then(response => response.json())
                        .then(jsonData => {{
                            tempData.labels = [];
                            tempData.datasets[0].data = [];
                            humData.labels = [];
                            humData.datasets[0].data = [];
                            
                            jsonData.forEach(function(item) {{
                                var date = new Date(item.timestamp * 1000);
                                var formattedDate = moment(date).toISOString();
                                tempData.labels.push(formattedDate);
                                humData.labels.push(formattedDate);
                                tempData.datasets[0].data.push(item.temperature);
                                humData.datasets[0].data.push(item.humidity);
                            }});
                            
                            tempChart.update();
                            humChart.update();
                        }})
                        .catch(error => console.error('Fehler beim Abrufen der Daten:', error));
                }}, 5000);  // Alle 5 Sekunden abrufen
            </script>
        </body>
        </html>
        """

        cl.send('HTTP/1.1 200 OK\r\n')
        cl.send('Content-Type: text/html\r\n')
        cl.send('Connection: close\r\n\r\n')
        cl.sendall(response)
        cl.close()

        # Speicher bereinigen
        gc.collect()  # Markierung: Garbage Collector wird aktiviert, um RAM nach Client-Anfrage zu bereinigen
    except OSError as e:
        # Wenn kein Client verbunden ist oder Timeout abläuft, passiert nichts
        pass

# WLAN verbinden
def connect_wifi(ssid, password):
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    sta.connect(ssid, password)

    timeout = 10  # Timeout für die Verbindung auf 10 Sekunden setzen
    while not sta.isconnected() and timeout > 0:
        print('Verbinde mit WLAN...')
        time.sleep(1)  # Warte 1 Sekunde
        timeout -= 1

    if sta.isconnected():
        print('WLAN verbunden:', sta.ifconfig())
        return sta.ifconfig()[0]  # IP-Adresse zurückgeben
    else:
        print("WLAN-Verbindung fehlgeschlagen.")
        return None

# WLAN trennen
def disconnect_wifi():
    sta = network.WLAN(network.STA_IF)
    if sta.isconnected():
        print("WLAN wird getrennt...")
        sta.disconnect()
        sta.active(False)
        time.sleep(1)  # Warte, um sicherzustellen, dass das WLAN korrekt deaktiviert wird

# Endlosschleife für den Prozess
while True:
    print("Warte auf ESP-NOW-Daten...")

    while not check_espnow(e, espnow_data):  # Warte auf ESP-NOW-Daten
        time.sleep(1)

    print("Daten empfangen, WLAN wird verbunden.")
    

    # WLAN-Zugangsdaten
    ssid = 'NTGR_05C1'
    password = 'E665u3A6'

    # Entferne den Peer vor dem WLAN-Verbindungsaufbau
    e.active(False)
    time.sleep(1)  # Kleines Delay, um ESP-NOW korrekt zu deaktivieren

    ip_address = connect_wifi(ssid, password)  # Verbinde mit WLAN

    if ip_address is not None:
        print("WLAN verbunden, Webserver wird gestartet.")
        server_socket = start_webserver(espnow_data)  # Starte den Webserver mit den empfangenen Daten

        if server_socket is not None:
            start_time = time.time()
            # Countdown von 45 Sekunden
            while time.time() - start_time < 45:
                handle_client(server_socket, espnow_data)  # Verarbeite Client-Anfragen
                time.sleep(1)  # Kurz warten, um die Schleife nicht zu überlasten

            print("45 Sekunden abgelaufen, Webserver wird gestoppt.")
            server_socket.close()  # Schließe den Webserver
            disconnect_wifi()  # WLAN trennen

    # Nach Trennung ESP-NOW wieder aktivieren
    e = init_espnow()
    try:
        e.add_peer(peer)
    except Exception as ex:
        print(f"Fehler beim Hinzufügen des Peers: {ex}")
        
        

    time.sleep(1)  # Pause, bevor erneut auf ESP-NOW-Daten gewartet wird
