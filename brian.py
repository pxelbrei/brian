import json
import os
import requests
import datetime
import asyncio
import sqlite3
import random
from itertools import permutations
from collections import defaultdict
from googletrans import Translator
import openai
from typing import Dict, Tuple, Optional, List

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

# Funktionen für Brians spezielle Features
def generiere_anagramm(wort: str) -> str:
    try:
        anagramme = [''.join(p) for p in permutations(wort.lower())]
        einzigartig = list(set(anagramme))
        return f"🧩 Anagramme für '{wort}': {', '.join(einzigartig[:5])}..." if einzigartig else "Keine Anagramme gefunden."
    except:
        return "Hmm, meine Neuronen sind heute etwas langsam. Frag später nochmal!"

brian_witze = [
    "Warum heißt Brian wie Brain? Weil ich dir immer einen Schritt voraus denke! 🧠",
    "Was sagt ein Brain im Fitnessstudio? 'Ich trainiere meine Neuronen!' 💪",
    "Wie viele Brian braucht man, um eine Glühbirne zu wechseln? Keine – ich denke im Dunkeln besser! 🕶️"
]

# Funktion, um die beste Antwort basierend auf den Bewertungen auszuwählen
def beste_antwort() -> str:
    c = conn.cursor()
    c.execute("SELECT antwort FROM bewertungen ORDER BY bewertung DESC LIMIT 1")
    result = c.fetchone()
    return result[0] if result else "Hmm, meine Synapsen brauchen mehr Daten. Frag etwas anderes!"

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
            antwort = f"🌤️ Das Wetter in {stadt} ist {wetter} bei {temperatur}°C."
            wetter_cache[stadt] = antwort
            return antwort
        return "❌ Entschuldigung, ich konnte das Wetter nicht abrufen."
    except Exception as e:
        return "⚡ Fehler beim Abrufen der Wetterdaten."

# Funktion, um Erinnerungen hinzuzufügen
def erinnerung_hinzufügen(benutzer_id: str, erinnerung: str, zeit: str) -> str:
    c = conn.cursor()
    c.execute("INSERT INTO erinnerungen (benutzer_id, text, zeit) VALUES (?, ?, ?)",
              (benutzer_id, erinnerung, zeit))
    conn.commit()
    return f"📅 Erinnerung hinzugefügt: '{erinnerung}' um {zeit}."

# Funktion, um Erinnerungen anzuzeigen
def zeige_erinnerungen(benutzer_id: str) -> str:
    c = conn.cursor()
    c.execute("SELECT text, zeit FROM erinnerungen WHERE benutzer_id = ?", (benutzer_id,))
    erinnerungen = c.fetchall()
    if erinnerungen:
        return "🗒️ Deine Erinnerungen:\n" + "\n".join([f"- {e[0]} (⏰ {e[1]})" for e in erinnerungen])
    return "🤷 Du hast keine Erinnerungen."

# Asynchrone Funktion für KI-gestützte Konversationen
async def ki_konversation(eingabe: str) -> str:
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=[{"role": "user", "content": f"Antworte als Brian, ein freundlicher KI-Chatbot mit Brain-Metaphern: {eingabe}"}],
            max_tokens=150
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        return "❌ Meine Neuronen sind heute überlastet. Frag später nochmal!"

# Einfache NLP-Funktion zur Intent- und Entitätserkennung
def verstehe_eingabe(eingabe: str) -> Tuple[str, Dict[str, str]]:
    eingabe = eingabe.lower()
    if "brian" in eingabe:
        return "name_ansprache", {}
    elif any(wort in eingabe for wort in ["anagramm", "anagram"]):
        return "anagramm", {"wort": eingabe.split("anagramm")[-1].strip()}
    elif any(wort in eingabe for wort in ["witz", "joke", "lachen"]):
        return "witz", {}
    elif "wetter" in eingabe:
        stadt = eingabe.split("in ")[-1] if "in " in eingabe else "Berlin"
        return "wetter", {"stadt": stadt}
    elif "erinnere" in eingabe:
        return "erinnerung", {"text": eingabe.split("erinnere mich an ")[-1], "zeit": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}
    elif "erinnerungen" in eingabe:
        return "zeige_erinnerungen", {}
    return "unbekannt", {}

# Asynchrone Funktion zur dynamischen Antwortgenerierung
async def generiere_antwort(intent: str, benutzer_id: str, stimmung: str, benutzereingabe: str, entitäten: Dict[str, str]) -> str:
    if intent == "name_ansprache":
        return random.choice([
            "🔍 Ja, das bin ich! Mein Name ist ein Anagramm für 'Brain'. 😉",
            "🧠 Brian hier! Wie kann ich dir helfen?",
            "🌟 Brainpower aktiviert! Was möchtest du wissen?"
        ])
    elif intent == "anagramm":
        wort = entitäten.get("wort", "")
        if not wort:
            return "🤔 Bitte nenne ein Wort, z.B.: 'Erstelle ein Anagramm für Brain'."
        return generiere_anagramm(wort)
    elif intent == "witz":
        return random.choice(brian_witze)
    elif intent == "wetter":
        stadt = entitäten.get("stadt", "Berlin")
        return await hole_wetter(stadt)
    elif intent == "erinnerung":
        return erinnerung_hinzufügen(benutzer_id, entitäten["text"], entitäten["zeit"])
    elif intent == "zeige_erinnerungen":
        return zeige_erinnerungen(benutzer_id)
    return await ki_konversation(benutzereingabe)

# Asynchrone Hauptschleife des Chatbots
async def chatbot():
    print("🧠 Brian: Hallo! Ich bin Brian – dein persönlicher Brain-Chatbot!")
    print("🌟 Tipp: Mein Name ist ein Anagramm für 'Brain'. Frag mich nach einem Witz! 😉")
    benutzer_id = input("🔑 Brian: Bitte gib deine Benutzer-ID ein (z.B. deinen Namen): ")
    
    konversation: List[Tuple[str, str]] = []  # Speichert alle Fragen und Antworten

    while True:
        benutzereingabe = input("👤 Du: ")
        if benutzereingabe.lower() == "exit":
            print("🚀 Brian: Tschüss! Meine Neuronen ruhen sich jetzt aus.")
            break
        
        intent, entitäten = verstehe_eingabe(benutzereingabe)
        stimmung = erkenne_stimmung(benutzereingabe)
        antwort = await generiere_antwort(intent, benutzer_id, stimmung, benutzereingabe, entitäten)
        print(f"🧠 Brian: {antwort}")
        
        # Speichere die Frage und Antwort für die spätere Bewertung
        konversation.append((benutzereingabe, antwort))

    # Bewertung am Ende der Konversation
    print("\n📝 Brian: Danke für das Gespräch! Bitte bewerten Sie meine Antworten:")
    for i, (frage, antwort) in enumerate(konversation, 1):
        print(f"\nFrage {i}: {frage}")
        print(f"Brian: {antwort}")
        feedback = input("War die Antwort gut, schlecht oder neutral? (gut/schlecht/neutral): ")
        verarbeite_feedback(antwort, feedback, benutzer_id)

# Starte den Chatbot
if __name__ == "__main__":
    asyncio.run(chatbot())
