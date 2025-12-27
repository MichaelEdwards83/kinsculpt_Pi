/*
 * 8-Channel Linear Actuator Controller (Serial Slave Edition)
 * Platform: Arduino Mega 2560 + PCA9685
 * Communication: Serial USB @ 115200 baud
 * Protocol: <CMD, VAL1, VAL2>
 *
 * Commands:
 * <SET, motorIdx, targetPos>  Example: <SET,0,1023> -> Moves Motor 1 to Max
 * <CFG, motorIdx, min, max>   Example: <CFG,0,50,900> -> Sets soft limits
 *
 * Feedback (Sent every 100ms):
 * <STA, pos0, pos1, pos2, pos3, pos4, pos5, pos6, pos7>
 */

#include <Adafruit_PWMServoDriver.h>
#include <Wire.h>

// --- Configuration ---
const int NUM_ACTUATORS = 8;
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver(0x40);

// --- Settings ---
const int DEADBAND = 10;
const int SLOW_ZONE = 150;
const int PWM_MIN_DEFAULT = 800;
const int PWM_MAX = 4095;

// --- Class: Linear Actuator ---
class LinearActuator {
public:
  int _chFWD, _chREV, _pinPot;
  int _targetPos, _currentPos, _currentSpeed;
  int _limitMin, _limitMax; // Soft Limits

  LinearActuator(int chFWD, int chREV, int pinPot)
      : _chFWD(chFWD), _chREV(chREV), _pinPot(pinPot), _targetPos(0),
        _currentPos(0), _currentSpeed(0), _limitMin(10), _limitMax(1013) {}

  void setTarget(int val) {
    // Constraint target to safe hardware limits
    if (val < _limitMin)
      val = _limitMin;
    if (val > _limitMax)
      val = _limitMax;
    _targetPos = val;
  }

  void setLimits(int minVal, int maxVal) {
    _limitMin = minVal;
    _limitMax = maxVal;
  }

  void update() {
    _currentPos = analogRead(_pinPot);

    // Safety: Disconnected Sensor (<5 or >1018 is likely broken wire)
    if (_currentPos < 5 || _currentPos > 1018) {
      stop();
      return;
    }

    int error = _targetPos - _currentPos;
    int absError = abs(error);

    if (absError <= DEADBAND) {
      stop();
      _currentSpeed = 0;
    } else {
      int targetSpeed = (absError > SLOW_ZONE) ? PWM_MAX
                                               : map(absError, 0, SLOW_ZONE,
                                                     PWM_MIN_DEFAULT, PWM_MAX);

      // Soft Start Ramp
      if (_currentSpeed < targetSpeed) {
        _currentSpeed += 100;
        if (_currentSpeed > targetSpeed)
          _currentSpeed = targetSpeed;
      } else {
        _currentSpeed = targetSpeed;
      }

      if (error > 0)
        drive(_currentSpeed, 0);
      else
        drive(0, _currentSpeed);
    }
  }

  void drive(int pwmFWD, int pwmREV) {
    pwm.setPWM(_chFWD, 0, pwmFWD);
    pwm.setPWM(_chREV, 0, pwmREV);
  }

  void stop() {
    pwm.setPWM(_chFWD, 0, 0);
    pwm.setPWM(_chREV, 0, 0);
  }
};

// --- Actuator Array ---
LinearActuator actuators[NUM_ACTUATORS] = {
    LinearActuator(0, 1, A0),   LinearActuator(2, 3, A1),
    LinearActuator(4, 5, A2),   LinearActuator(6, 7, A3),
    LinearActuator(8, 9, A4),   LinearActuator(10, 11, A5),
    LinearActuator(12, 13, A6), LinearActuator(14, 15, A7)};

// --- Serial Buffer ---
const byte numChars = 32;
char receivedChars[numChars];
boolean newData = false;

void setup() {
  Serial.begin(115200); // Fast Serial

  pwm.begin();
  pwm.setOscillatorFrequency(27000000);
  pwm.setPWMFreq(60);

  Serial.println("<READY>");
}

void loop() {
  recvWithStartEndMarkers();
  if (newData) {
    parseData();
    newData = false;
  }

  // Update Motors
  for (int i = 0; i < NUM_ACTUATORS; i++) {
    actuators[i].update();
  }

  // Send Feedback (10Hz)
  static unsigned long lastReport = 0;
  if (millis() - lastReport > 100) {
    reportStatus();
    lastReport = millis();
  }
}

// --- Serial Handlers ---

// Read "<...>" non-blocking
void recvWithStartEndMarkers() {
  static boolean recvInProgress = false;
  static byte ndx = 0;
  char startMarker = '<';
  char endMarker = '>';
  char rc;

  while (Serial.available() > 0 && newData == false) {
    rc = Serial.read();

    if (recvInProgress == true) {
      if (rc != endMarker) {
        receivedChars[ndx] = rc;
        ndx++;
        if (ndx >= numChars)
          ndx = numChars - 1;
      } else {
        receivedChars[ndx] = '\0'; // terminate string
        recvInProgress = false;
        ndx = 0;
        newData = true;
      }
    } else if (rc == startMarker) {
      recvInProgress = true;
    }
  }
}

// Parse Command "CMD, arg1, arg2"
void parseData() {
  char *strtokIndx;

  strtokIndx = strtok(receivedChars, ","); // Get Command
  if (strcmp(strtokIndx, "SET") == 0) {
    strtokIndx = strtok(NULL, ",");
    int id = atoi(strtokIndx); // Motor ID (0-7)
    strtokIndx = strtok(NULL, ",");
    int val = atoi(strtokIndx); // Target (0-1023)

    if (id >= 0 && id < NUM_ACTUATORS) {
      actuators[id].setTarget(val);
    }
  } else if (strcmp(strtokIndx, "CFG") == 0) {
    // <CFG, id, min, max>
    strtokIndx = strtok(NULL, ",");
    int id = atoi(strtokIndx);
    strtokIndx = strtok(NULL, ",");
    int minVal = atoi(strtokIndx);
    strtokIndx = strtok(NULL, ",");
    int maxVal = atoi(strtokIndx);

    if (id >= 0 && id < NUM_ACTUATORS) {
      actuators[id].setLimits(minVal, maxVal);
    }
  }
}

void reportStatus() {
  // Format: <STA,pos0,pos1,pos2,pos3,pos4,pos5,pos6,pos7>
  Serial.print("<STA");
  for (int i = 0; i < NUM_ACTUATORS; i++) {
    Serial.print(",");
    Serial.print(actuators[i]._currentPos);
  }
  Serial.println(">");
}