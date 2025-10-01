import os
import psycopg2
from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
from google.cloud import dialogflow
from datetime import datetime, timedelta

# --- Credentials ---
DB_HOST = "db.lzqmvfueyiugigqrwhhx.supabase.co"
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASS = "Nqn7LbKSm8wUOOWS"
DB_PORT = "5432"

TWILIO_ACCOUNT_SID = "ACecdb9f6cbd2c0b8e0b2b2591fd130ff9"
TWILIO_AUTH_TOKEN = "fdf5cbcfc266b4d6636a201408525ac4"

PROJECT_ID = "guesthousebot--tn9c"
# --------------------

app = Flask(__name__)

def get_db_connection():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS, port=DB_PORT)
    return conn

def setup_database():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS rooms (id SERIAL PRIMARY KEY, room_type TEXT NOT NULL, capacity INTEGER NOT NULL, price_per_night REAL NOT NULL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS bookings (id SERIAL PRIMARY KEY, room_id INTEGER REFERENCES rooms(id), guest_name TEXT, check_in_date DATE NOT NULL, check_out_date DATE NOT NULL)")
        cursor.execute("SELECT count(*) FROM rooms")
        if cursor.fetchone()[0] == 0:
            print("Adding initial rooms to the database...")
            rooms_to_add = [('Standard', 2, 1200.00), ('Deluxe', 2, 2000.00), ('Family Suite', 4, 3500.00)]
            cursor.executemany('INSERT INTO rooms (room_type, capacity, price_per_night) VALUES (%s, %s, %s)', rooms_to_add)
        conn.commit()
        cursor.close()
        conn.close()
        print("Database setup checked/completed.")
    except Exception as e:
        print(f"Database setup failed: {e}")

def detect_intent_with_parameters(project_id, session_id, text, language_code):
    session_client = dialogflow.SessionsClient()
    session = session_client.session_path(project_id, session_id)
    text_input = dialogflow.TextInput(text=text, language_code=language_code)
    query_input = dialogflow.QueryInput(text=text_input)
    response = session_client.detect_intent(request={"session": session, "query_input": query_input})
    return response.query_result

def check_availability(people_count, date_str):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        check_in_date = datetime.fromisoformat(date_str.split('T')[0]).date()
        check_out_date = check_in_date + timedelta(days=1)
        query = "SELECT * FROM rooms WHERE capacity >= %s AND id NOT IN (SELECT room_id FROM bookings WHERE NOT (check_out_date <= %s OR check_in_date >= %s))"
        cursor.execute(query, (people_count, check_in_date, check_out_date))
        available_rooms = cursor.fetchall()
        cursor.close()
        conn.close()
        if available_rooms:
            return f"Yes, rooms are available for {people_count} people on {check_in_date.strftime('%d %B, %Y')}."
        else:
            return f"Sorry, no rooms are available for that date and capacity."
    except Exception as e:
        return f"An error occurred while checking the database."

@app.route("/voice", methods=['GET', 'POST'])
def voice():
    response = VoiceResponse()
    gather = Gather(input='speech', action='/gather', language='en-US, hi-IN, gu-IN', speechTimeout='auto')
    gather.say('Welcome to ISKCON Rajkot Guesthouse booking. How can I help you?')
    response.append(gather)
    response.redirect('/voice')
    return str(response)

@app.route('/gather', methods=['GET', 'POST'])
def gather():
    response = VoiceResponse()
    speech_result = request.values.get('SpeechResult', '')
    call_sid = request.values.get('CallSid', 'default-session')
    if speech_result:
        dialogflow_result = detect_intent_with_parameters(PROJECT_ID, call_sid, speech_result, 'en-US')
        bot_response = ""
        if dialogflow_result.intent.display_name == 'BookRoom':
            params = dialogflow_result.parameters
            people = params.get('number')
            date = params.get('date')
            if people and date:
                date_iso = date.isoformat() if hasattr(date, 'isoformat') else str(date)
                bot_response = check_availability(int(people), date_iso) 
            else:
                bot_response = "For when and for how many people would you like to book?"
        else:
            bot_response = dialogflow_result.fulfillment_text
        response.say(bot_response)
        response.redirect('/voice')
    else:
        response.say("Sorry, I didn't hear anything. Please try again.")
        response.redirect('/voice')
    return str(response)

# --- સુધારેલો ભાગ અહીં છે ---
# આ કોડ gunicorn દ્વારા સર્વર શરૂ થાય ત્યારે આપમેળે ડેટાબેઝ ટેબલ્સ બનાવે છે
with app.app_context():
    setup_database()

if __name__ == "__main__":
    if 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ:
        print("Error: GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
    else:
        print(">>> Voice Bot Server is running locally...")
        app.run(host='0.0.0.0', port=5000)

