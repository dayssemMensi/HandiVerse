#include <Servo.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

#define NumberOfValsRec 5
#define digitalsPerValRec 1

Servo servoThumb;
Servo servoThumb2; // Second thumb servo
Servo servoIndex;
Servo servoMiddle;
Servo servoRing;
Servo servoPinky;

LiquidCrystal_I2C lcd(0x27, 16, 2); // I2C address 0x27, 16x2 LCD

int valsRec[NumberOfValsRec];
int stringLength = (NumberOfValsRec * digitalsPerValRec); // 5
int counter = 0;
bool counterStart = false;
String receivedString;

int rawValue;

#define KY039_PIN A0
int ledPin = 13;

String previousStatus = "";

const int delayMsec = 60;
int beatMsec = 0;
int heartRateBPM = 0;

void setup() {
  Serial.begin(9600);
  lcd.init();
  lcd.backlight();

  pinMode(KY039_PIN, INPUT);
  pinMode(ledPin, OUTPUT);

  lcd.setCursor(0, 0);
  lcd.print("  RoboVision");
  delay(2000);
  lcd.clear();

  // Attach all servos
  servoThumb.attach(10);
  servoThumb2.attach(11); // Attach second thumb servo to pin 11
  servoIndex.attach(5);
  servoMiddle.attach(9);
  servoRing.attach(3);
  servoPinky.attach(6);
}

bool heartbeatDetected(int IRSensorPin, int delayVal) {
  static int maxValue = 0;
  static bool isPeak = false;
  bool result = false;

  rawValue = analogRead(IRSensorPin);
  rawValue = rawValue * (1000 / delayVal);

  if (rawValue * 4L < maxValue) maxValue = rawValue * 0.8;

  if (rawValue > maxValue - (1000 / delayVal)) {
    if (rawValue > maxValue) {
      maxValue = rawValue;
    }
    if (isPeak == false) {
      result = true;
    }
    isPeak = true;
  }
  else if (rawValue < maxValue - (3000 / delayVal)) {
    isPeak = false;
    maxValue -= (1000 / delayVal);
  }
  return result;
}

void receiveData() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '$') {
      counterStart = true;
      receivedString = "";
      counter = 0;
      continue;
    }
    if (counterStart) {
      if (c == '0' || c == '1') {
        receivedString += c;
        counter++;
      }
      if (counter >= stringLength) {
        for (int i = 0; i < NumberOfValsRec; i++) {
          valsRec[i] = receivedString.charAt(i) - '0';
        }
        counterStart = false;
      }
    }
  }
}

void updateServos() {
  // Control both thumb servos together
  if (valsRec[0] == 0) {
    servoThumb.write(180);
    servoThumb2.write(62);
  } else {
    servoThumb.write(0);
    servoThumb2.write(180);
  }

  // Other fingers
  servoIndex.write(valsRec[1] == 0 ? 0 : 180);
  servoMiddle.write(valsRec[2] == 0 ? 180 : 0);
  servoRing.write(valsRec[3] == 0 ? 0 : 180);
  servoPinky.write(valsRec[4] == 0 ? 0 : 180);
}

void displayFingerStatus() {
  int inactiveCount = 0;
  String status = "";

  if (valsRec[1] == 0) { status += "Ind-"; inactiveCount++; }
  if (valsRec[2] == 0) { status += "Maj-"; inactiveCount++; }
  if (valsRec[3] == 0) { status += "Ann-"; inactiveCount++; }
  if (valsRec[4] == 0) { status += "Aur-"; inactiveCount++; }
  if (valsRec[0] == 0) { status += "Pou-"; inactiveCount++; }

  if (inactiveCount == 0) status = "OUVRE";
  else if (inactiveCount == 5) status = "FERMER";
  else status.remove(status.length() - 1); // remove last '-'

  if (status != previousStatus) {
     lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(status);
  Serial.print("DOIGTS: ");
  Serial.println(status);
  previousStatus = status;
  }
}

void displayHeartRate() {
  if (heartbeatDetected(KY039_PIN, delayMsec)) {
    if (beatMsec != 0) {
      heartRateBPM = 60000 / beatMsec;

      if (heartRateBPM > 30 && heartRateBPM < 200) {
        Serial.print("Pulse detected: ");
        Serial.println(heartRateBPM);
      }
    }
    digitalWrite(ledPin, HIGH);
    beatMsec = 0;
  } else {
    digitalWrite(ledPin, LOW);
  }

  lcd.setCursor(0, 1);
  if (heartRateBPM > 0) {
    lcd.print("BPM: ");
    lcd.print(heartRateBPM);
    lcd.print("    ");
  } else {
    lcd.print("Measuring...    ");
  }

  delay(delayMsec);
  beatMsec += delayMsec;
}

void loop() {
  receiveData();
  updateServos();
  displayFingerStatus();
  displayHeartRate();
  // Nouvelle ligne à ajouter pour envoyer données combinées
  Serial.print("#DATA:");
  for (int i = 0; i < 5; i++) {
    Serial.print(valsRec[i]);
  }
  Serial.print(",");
  Serial.println(heartRateBPM);  // exemple: #DATA:01101,78
}
