# Wiring Guide: 8-Axis ArtNet System (PCA9685 Edition)

## Components
- **Controller**: Arduino Mega 2560 + W5100 Ethernet Shield
- **PWM Driver**: **PCA9685 16-Channel Driver**
- **Motor Drivers**: 8x BTS7960 High Power Modules
- **Power**: 12V/24V PSU (High Amperage)

## 1. PCA9685 I2C Connection
Connect the PCA9685 driver to the Arduino Mega:
- **VCC** -> 5V
- **GND** -> GND
- **SDA** -> **Pin 20** (Mega)
- **SCL** -> **Pin 21** (Mega)
- **OE** -> Not Connected (or GND)

> [!IMPORTANT]
> **External Power**: The PCA9685 has a green terminal block for servo power. Since we are only sending logic signals (PWM) to the BTS7960 drivers, **you DO NOT need to plug power into the PCA9685 terminal block**. Just powering the Logic VCC with 5V is enough.

## 2. Motor Driver Connections (BTS7960 to PCA9685)
The **PCA9685** has 16 sets of 3-pin headers (PWM, V+, GND).
We only care about the **Yellow/Signal (PWM)** pin.
Connect the PCA9685 Channel Signal Pin to the BTS7960 RPWM/LPWM pins.

> **BTS7960 EN PINS**: Connect **R_EN** and **L_EN** on ALL drivers to **Arduino +5V**.

| Actuator | PCA9685 Channel (RPWM) | PCA9685 Channel (LPWM) | Feedback Pot (Mega Pin) |
| :--- | :--- | :--- | :--- |
| **Actuator 1** | Channel **0** | Channel **1** | **A0** |
| **Actuator 2** | Channel **2** | Channel **3** | **A1** |
| **Actuator 3** | Channel **4** | Channel **5** | **A2** |
| **Actuator 4** | Channel **6** | Channel **7** | **A3** |
| **Actuator 5** | Channel **8** | Channel **9** | **A4** |
| **Actuator 6** | Channel **10** | Channel **11** | **A5** |
| **Actuator 7** | Channel **12** | Channel **13** | **A6** |
| **Actuator 8** | Channel **14** | Channel **15** | **A7** |

## 3. Feedback Potentiometers
Connect the wiper (middle pin) of the actuator pots directly to the **Arduino Mega Analog Pins** (A0-A7).
(Do not connect these to the PCA9685).

## 4. Mode Switch
- **Pin 2** on Arduino Mega to **GND** = Demo Mode.
- **Pin 2** Open = ArtNet Mode.
