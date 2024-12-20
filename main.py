# main.py -- put your code here!import network
import network
import espnow
import time
import socket

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
                        temp_str = message.split("Temperatur: ")[1].split("°C")[0]
                        hum_str = message.split("Luftfeuchtigkeit: ")[1].split("%")[0]
                        espnow_data['temperature'] = temp_str
                        espnow_data['humidity'] = hum_str
                        print(f"Empfangene Temperatur: {espnow_data['temperature']}°C")
                        print(f"Empfangene Feuchtigkeit: {espnow_data['humidity']}%")
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
        s.settimeout(0.5)  # Setze einen kurzen Timeout, damit der Server nicht blockiert
        cl, addr = s.accept()
        print('Client verbunden von', addr)
        request = cl.recv(1024).decode()
        print(request)

        # HTML-Seite generieren
        response = f"""
        <html>
        <head>
            <title>ESP-NOW & Webserver</title>
            <meta charset="UTF-8">  <!-- Sicherstellen, dass UTF-8 verwendet wird -->
            <meta http-equiv="refresh" content="5">
        </head>
        <body>
            <h1>ESP-NOW Sensordaten</h1>
            <p>Temperatur: {espnow_data['temperature']}°C</p>
            <p>Feuchtigkeit: {espnow_data['humidity']}%</p>
        </body>
        </html>
        """

        cl.send('HTTP/1.1 200 OK\r\n')
        cl.send('Content-Type: text/html\r\n')
        cl.send('Connection: close\r\n\r\n')
        cl.sendall(response)
        cl.close()
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

