import json
import os
import requests
import datetime
import asyncio
import sqlite3
from collections import defaultdict
from googletrans import Translator
import matplotlib.pyplot as plt
import openai
from typing import Dict, Tuple, Optional

# Konfiguration
BEWERTUNGEN_DATEI = "bewertungen.json"
BENUTZERPROFILE_DATEI = "benutzerprofile.json"
ERINNERUNGEN_DATEI = "erinnerungen.json"
WETTER_API_KEY = "dein_api_schluessel"
WETTER_API_URL = "http://api.openweathermap.org/data/2.5/weather"
OPENAI_API_KEY = "dein_openai_schluessel"
openai.api_key = OPENAI_API_KEY

# SQLite-Datenbank initialisieren
def init_db():
    conn = sqlite3.connect('chatbot.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS bewertungen
                 (antwort TEXT PRIMARY KEY, bewertung INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS benutzerprofile
                 (benutzer_id TEXT, antwort TEXT, bewertung INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS erinnerungen
                 (benutzer_id TEXT, text TEXT, zeit TEXT)''')
    conn.commit()
    return conn

# Datenbankverbindung
conn = init_db()

# Funktion, um die beste Antwort basierend auf den Bewertungen auszuwählen
def beste_antwort() -> str:
    c = conn.cursor()
    c.execute("SELECT antwort FROM bewertungen ORDER BY bewertung DESC LIMIT 1")
    result = c.fetchone()
    return result[0] if result else "Ich bin mir nicht sicher, was du meinst."

# Funktion, um das Feedback des Benutzers zu verarbeiten
def verarbeite_feedback(antwort: str, feedback: str, benutzer_id: str):
    c = conn.cursor()
    bewertung = 1 if feedback == "gut" else -1 if feedback == "schlecht" else 0.5
    c.execute("INSERT OR REPLACE INTO bewertungen (antwort, bewertung) VALUES (?, ?)",
              (antwort, bewertung))
    c.execute("INSERT INTO benutzerprofile (benutzer_id, antwort, bewertung) VALUES (?, ?, ?)",
              (benutzer_id, antwort, bewertung))
    conn.commit()

# Funktion, um die Stimmung des Benutzers zu erkennen
def erkenne_stimmung(eingabe: str) -> str:
    positive_wörter = ["gut", "super", "toll", "glücklich", "fantastisch"]
    negative_wörter = ["schlecht", "traurig", "müde", "wütend", "nervös"]
    if any(word in eingabe for word in positive_wörter):
        return "positiv"
    elif any(word in eingabe for word in negative_wörter):
        return "negativ"
    return "neutral"

# Asynchrone Funktion, um das Wetter abzurufen (mit Caching)
wetter_cache: Dict[str, str] = {}
async def hole_wetter(stadt: str) -> str:
    if stadt in wetter_cache:
        return wetter_cache[stadt]
    try:
        response = await asyncio.to_thread(requests.get, WETTER_API_URL, params={"q": stadt, "appid": WETTER_API_KEY, "units": "metric", "lang": "de"})
        if response.status_code == 200:
            wetter_daten = response.json()
            wetter = wetter_daten["weather"][0]["description"]
            temperatur = wetter_daten["main"]["temp"]
            antwort = f"Das Wetter in {stadt} ist {wetter} bei {temperatur}°C."
            wetter_cache[stadt] = antwort
            return antwort
        return "Entschuldigung, ich konnte das Wetter nicht abrufen."
    except Exception as e:
        return "Fehler beim Abrufen der Wetterdaten."

# Funktion, um Erinnerungen hinzuzufügen
def erinnerung_hinzufügen(benutzer_id: str, erinnerung: str, zeit: str) -> str:
    c = conn.cursor()
    c.execute("INSERT INTO erinnerungen (benutzer_id, text, zeit) VALUES (?, ?, ?)",
              (benutzer_id, erinnerung, zeit))
    conn.commit()
    return f"Erinnerung hinzugefügt: {erinnerung} um {zeit}."

# Funktion, um Erinnerungen anzuzeigen
def zeige_erinnerungen(benutzer_id: str) -> str:
    c = conn.cursor()
    c.execute("SELECT text, zeit FROM erinnerungen WHERE benutzer_id = ?", (benutzer_id,))
    erinnerungen = c.fetchall()
    if erinnerungen:
        return "Deine Erinnerungen:\n" + "\n".join([f"{e[0]} um {e[1]}" for e in erinnerungen])
    return "Du hast keine Erinnerungen."

# Asynchrone Funktion für KI-gestützte Konversationen
async def ki_konversation(eingabe: str) -> str:
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=[{"role": "user", "content": eingabe}],
            max_tokens=150
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        return "Entschuldigung, ich konnte keine Antwort generieren."

# Einfache NLP-Funktion zur Intent- und Entitätserkennung
def verstehe_eingabe(eingabe: str) -> Tuple[str, Dict[str, str]]:
    eingabe = eingabe.lower()
    if "hallo" in eingabe:
        return "begrüßung", {}
    elif "geht" in eingabe or "wie" in eingabe:
        return "befinden", {}
    elif "machst" in eingabe or "tust" in eingabe:
        return "aktivität", {}
    elif "witz" in eingabe:
        return "witz", {}
    elif "wetter" in eingabe:
        stadt = eingabe.split("in ")[-1] if "in " in eingabe else "Berlin"
        return "wetter", {"stadt": stadt}
    elif "farbe" in eingabe:
        return "lieblingsfarbe", {}
    elif "hilf" in eingabe:
        return "hilfe", {}
    elif "erinnere" in eingabe:
        return "erinnerung", {"text": eingabe.split("erinnere mich an ")[-1], "zeit": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}
    elif "erinnerungen" in eingabe:
        return "zeige_erinnerungen", {}
    elif "quiz" in eingabe:
        return "quiz", {}
    return "unbekannt", {}

# Asynchrone Funktion zur dynamischen Antwortgenerierung
async def generiere_antwort(intent: str, benutzer_id: str, stimmung: str, benutzereingabe: str, entitäten: Dict[str, str]) -> str:
    if intent == "begrüßung":
        return f"Hallo! Schön, dich wiederzusehen, Benutzer {benutzer_id}."
    elif intent == "befinden":
        if stimmung == "positiv":
            return "Das freut mich zu hören! 😊"
        elif stimmung == "negativ":
            return "Oh, das tut mir leid. Kann ich dir helfen? 😢"
        return "Mir geht es gut, danke der Nachfrage!"
    elif intent == "aktivität":
        return "Ich lerne gerade, besser mit dir zu kommunizieren."
    elif intent == "witz":
        return "Warum können Geister so schlecht lügen? Weil man durch sie hindurchsieht!"
    elif intent == "wetter":
        stadt = entitäten.get("stadt", "Berlin")
        return await hole_wetter(stadt)
    elif intent == "lieblingsfarbe":
        return "Meine Lieblingsfarbe ist Blau. Und deine?"
    elif intent == "hilfe":
        return "Natürlich, wie kann ich dir helfen?"
    elif intent == "erinnerung":
        return erinnerung_hinzufügen(benutzer_id, entitäten["text"], entitäten["zeit"])
    elif intent == "zeige_erinnerungen":
        return zeige_erinnerungen(benutzer_id)
    elif intent == "quiz":
        return "Lass uns ein Quiz spielen! Frage: Was ist die Hauptstadt von Frankreich?"
    return await ki_konversation(benutzereingabe)

# Asynchrone Hauptschleife des Chatbots
async def chatbot():
    print("Chatbot: Hallo! Ich bin ein lernender Chatbot. Sprich mit mir!")
    benutzer_id = input("Bitte gib deine Benutzer-ID ein (z. B. deinen Namen): ")
    
    while True:
        benutzereingabe = input("Du: ")
        if benutzereingabe.lower() == "exit":
            print("Chatbot: Tschüss! Bis zum nächsten Mal.")
            break
        
        intent, entitäten = verstehe_eingabe(benutzereingabe)
        stimmung = erkenne_stimmung(benutzereingabe)
        antwort = await generiere_antwort(intent, benutzer_id, stimmung, benutzereingabe, entitäten)
        print(f"Chatbot: {antwort}")
        
        feedback = input("War die Antwort gut, schlecht oder neutral? (gut/schlecht/neutral): ")
        verarbeite_feedback(antwort, feedback, benutzer_id)

# Starte den Chatbot
if __name__ == "__main__":
    asyncio.run(chatbot())