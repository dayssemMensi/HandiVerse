from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import cv2
import mediapipe as mp
import pygame
import speech_recognition as sr
import threading
import serial
import time
import logging
from sys import exit

# ===== Flask & SocketIO =====
app = Flask(__name__)
socketio = SocketIO(app)

@app.route('/')
def index():
    return render_template('index.html')

# ===== Config =====
logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
finger_states = ['0'] * 5
voice_listening = False
heart_rate = 0

# ===== Arduino Init =====
try:
    arduino = serial.Serial('COM5', 9600, timeout=1)
    time.sleep(2)
    logging.info("Arduino connecté sur COM5")
except Exception as e:
    logging.error(f"Erreur Arduino: {e}")
    exit(1)

# ======== MODE CAMÉRA ======== #
def main_camera_mode():
    global heart_rate
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)
    mp_draw = mp.solutions.drawing_utils
    finger_tips = [4, 8, 12, 16, 20]
    state_labels = ['Pouce', 'Index', 'Majeur', 'Annulaire', 'Auriculaire']
    cap = cv2.VideoCapture(0)
    last_serial_send = time.time()

    def get_finger_states(hand_landmarks, handedness_label):
        states = []
        # Pouce (horizontal)
        if handedness_label == 'Right':
            states.append(1 if hand_landmarks.landmark[finger_tips[0]].x < hand_landmarks.landmark[finger_tips[0] - 1].x else 0)
        else:
            states.append(1 if hand_landmarks.landmark[finger_tips[0]].x > hand_landmarks.landmark[finger_tips[0] - 1].x else 0)
        # Autres doigts (vertical)
        for tip_id in finger_tips[1:]:
            states.append(1 if hand_landmarks.landmark[tip_id].y < hand_landmarks.landmark[tip_id - 2].y else 0)
        return states

    while True:
        success, frame = cap.read()
        if not success:
            break

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)

        if result.multi_hand_landmarks and result.multi_handedness:
            for hand_landmarks, handedness in zip(result.multi_hand_landmarks, result.multi_handedness):
                mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                hand_label = handedness.classification[0].label  # 'Left' ou 'Right'
                states = get_finger_states(hand_landmarks, hand_label)

                # Afficher libellé de la main
                cv2.putText(frame, f"Main : {hand_label}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

                # Afficher l'état des doigts
                y = 60
                for i, (label, state) in enumerate(zip(state_labels, states)):
                    cv2.putText(frame, f"{label}: {state}", (10, y),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    y += 30

                # Envoi série et WebSocket
                if time.time() - last_serial_send > 0.1:
                    data = "$" + "".join(str(bit) for bit in states)
                    try:
                        arduino.write(data.encode())
                        socketio.emit('update', {'fingers': ''.join(str(bit) for bit in states), 'bpm': heart_rate})
                        last_serial_send = time.time()
                    except Exception as e:
                        logging.error(f"Erreur série: {e}")

        cv2.imshow("Mode Caméra", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        time.sleep(0.02)

    cap.release()
    cv2.destroyAllWindows()


# ======== MODE VOCAL ======== #
def chiffre_to_command(text):
    text = text.lower()
    command = ['0'] * 5
    
    if "ouvre" in text or "open" in text or "6" in text or "six" in text:
        command = ['1'] * 5
    elif "ferme" in text or "close" in text or "7" in text or "sept" in text:
        command = ['0'] * 5
    else:
        if "pouce" in text or "thumb" in text or "1" in text or "un" in text:
            command[0] = '1'
        if "index" in text or "2" in text or "deux" in text:
            command[1] = '1'
        if "majeur" in text or "middle" in text or "3" in text or "trois" in text:
            command[2] = '1'
        if "annulaire" in text or "ring" in text or "4" in text or "quatre" in text:
            command[3] = '1'
        if "auriculaire" in text or "petit doigt" in text or "little" in text or "5" in text or "cinq" in text:
            command[4] = '1'

    return ''.join(command)

def voice_thread():
    global finger_states
    recognizer = sr.Recognizer()
    mic = sr.Microphone()
    while True:
        try:
            with mic as source:
                print("🎤 Parlez maintenant...")
                audio = recognizer.listen(source, timeout=3, phrase_time_limit=5)
            text = recognizer.recognize_google(audio, language='fr-FR')
            print(f"Vous avez dit : {text}")
            if "stop" in text: break

            cmd = chiffre_to_command(text)
            finger_states = list(cmd)
            serial_cmd = f"${cmd}"
            arduino.write(serial_cmd.encode())
            socketio.emit('update', {'fingers': cmd, 'bpm': heart_rate})
        except:
            continue

def main_voice_mode():
    pygame.init()
    screen = pygame.display.set_mode((500, 400))
    pygame.display.set_caption("Main Robotique - Mode Vocal")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont('Arial', 24)
    base_x, base_y = 250, 350
    finger_length, finger_gap = 100, 40
    threading.Thread(target=voice_thread, daemon=True).start()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.fill((255, 255, 255))
        for i, state in enumerate(finger_states):
            x = base_x + (i - 2) * finger_gap
            if state == '1':
                pygame.draw.line(screen, (0, 128, 255), (x, base_y), (x, base_y - finger_length), 12)
                pygame.draw.circle(screen, (0, 128, 255), (x, base_y - finger_length), 18)
            else:
                pygame.draw.line(screen, (100, 100, 100), (x, base_y), (x, base_y - finger_length // 3), 12)
                pygame.draw.circle(screen, (100, 100, 100), (x, base_y - finger_length // 3), 18)
        pygame.display.flip()
        clock.tick(30)

    pygame.quit()

# ====== Thread de lecture série pour le BPM Arduino ======
def arduino_reader():
    global heart_rate
    while True:
        try:
            line = arduino.readline().decode().strip()
            if line.startswith("#DATA:"):
                parts = line.split(":")[1].split(",")
                if len(parts) == 2:
                    _, bpm = parts
                    heart_rate = int(bpm)
        except:
            continue

# ======= Menu principal =======
def menu_principal():
    print("=== MENU ===")
    print("1. Mode Caméra")
    print("2. Mode Vocal")
    choix = input("Choix (1/2) : ").strip()
    if choix == '1':
        main_camera_mode()
    elif choix == '2':
        main_voice_mode()
    else:
        print("Choix invalide.")
        menu_principal()

# ======= MAIN =======
if __name__ == '__main__':
    threading.Thread(target=arduino_reader, daemon=True).start()
    threading.Thread(target=lambda: socketio.run(app, host='0.0.0.0', port=5000), daemon=True).start()
    try:
        menu_principal()
    except KeyboardInterrupt:
        logging.info("Arrêt manuel")
    finally:
        arduino.close()
        exit(0)
