import cv2
import face_recognition
import pickle
from cryptography.fernet import Fernet
import RPi.GPIO as GPIO
import time
import logging
from datetime import datetime
import os


dataset_path = "dataset/"
encodings_path = "encrypted_encodings.pkl"
key_path = "encryption_key.key"

os.makedirs(dataset_path, exist_ok=True)

# Generate and save the encryption key securely
key = Fernet.generate_key()
with open(key_path, "wb") as key_file:
    key_file.write(key)
cipher_suite = Fernet(key)

# Function to capture and register face data
def register_face(person_id):
    cap = cv2.VideoCapture(0)
    count = 0
    while count < 20:
        ret, frame = cap.read()
        if not ret:
            break
        cv2.imshow("Registering Face", frame)
        file_path = os.path.join(dataset_path, f"person_{person_id}_{count}.jpg")
        cv2.imwrite(file_path, frame)
        count += 1
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()

# Function to encode faces and save encrypted encodings
def encode_faces():
    known_face_encodings = []
    known_face_ids = []
    for filename in os.listdir(dataset_path):
        if filename.endswith(".jpg"):
            image = face_recognition.load_image_file(os.path.join(dataset_path, filename))
            encodings = face_recognition.face_encodings(image)
            if encodings:
                encoding = encodings[0]
                encrypted_encoding = cipher_suite.encrypt(pickle.dumps(encoding))
                known_face_encodings.append(encrypted_encoding)
                known_face_ids.append(filename.split("_")[1])
    with open(encodings_path, "wb") as f:
        pickle.dump((known_face_encodings, known_face_ids), f)

# Register and encode faces
person_id = input("Enter person ID: ")
register_face(person_id)
encode_faces()


with open(key_path, "rb") as key_file:
    key = key_file.read()
cipher_suite = Fernet(key)

with open(encodings_path, "rb") as f:
    encrypted_encodings, known_face_ids = pickle.load(f)

known_face_encodings = [pickle.loads(cipher_suite.decrypt(enc)) for enc in encrypted_encodings]

# Setup GPIO for the door lock
lock_pin = 18
GPIO.setmode(GPIO.BCM)
GPIO.setup(lock_pin, GPIO.OUT)

# Setup logging
logging.basicConfig(filename='access_log.txt', level=logging.INFO, format='%(asctime)s %(message)s')

# Function to log access attempts
def log_access(person_id=None, access_granted=False):
    status = "Access Granted" if access_granted else "Access Denied"
    if person_id:
        logging.info(f"{status} for person ID: {person_id}")
    else:
        logging.info(status)

# Function to send email
def send_alert_email(subject, body):
    from email.mime.text import MIMEText
    import smtplib

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = 'test@gmail.com'
    msg['To'] = 'admin@gmail.com'

    # Send the email 
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login('test@gmail.com', 'password')
        server.sendmail(msg['From'], [msg['To']], msg.as_string())

cap = cv2.VideoCapture(0)
number_of_failed_attempts = 0
failed_attempt_threshold = 5 

while True:
    ret, frame = cap.read()
    if not ret:
        break
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb_frame)
    face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

    for face_encoding in face_encodings:
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
        if True in matches:
            matched_id = known_face_ids[matches.index(True)]
            print(f"Access granted to person {matched_id}")
            log_access(matched_id, True)
            GPIO.output(lock_pin, GPIO.HIGH)
            time.sleep(5)
            GPIO.output(lock_pin, GPIO.LOW)
        else:
            print("Access denied")
            log_access(access_granted=False)
            number_of_failed_attempts += 1
            if number_of_failed_attempts >= failed_attempt_threshold:
                send_alert_email("Suspicious Activity Detected", "Multiple failed access attempts detected.")
                number_of_failed_attempts = 0 

    cv2.imshow("Facial Recognition", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
GPIO.cleanup()
