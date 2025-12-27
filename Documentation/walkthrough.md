# Verification Walkthrough: 8-Axis ArtNet Actuator System

This guide helps you verify the system works correctly after assembling the hardware.

## 1. Wiring Check
Before powering on reliable current, double-check:
- **Common Ground**: Is the PSU Ground connected to the Arduino GND?
- **Logic Power**: Are all BTS7960 `L_EN` and `R_EN` pins connected to +5V?
- **I2C Bus**: Is the PCA9685 connected to Mega Pins 20 (SDA) and 21 (SCL)?
- **Feedback**: Are all Pot wipers connected to A0-A7?

> [!WARNING]
> **Direction Test**: If you extend an actuator in Manual/Code, but the feedback value **decreases** instead of **increases**, the motor wires are swapped. Reverse the M+ and M- wires for that actuator immediately.

## 2. Test "Demo Mode" First
This tests the full hardware chain (Arduino -> PCA9685 -> Drivers -> Motors) without needing network config.
1. Connect **Pin 2** to **GND** (via a switch or jumper wire).
2. Power on the system.
3. **Expected Result**: All 8 actuators should start moving in a slow sine-wave pattern.
4. **Troubleshooting**:
   - *No movement?* Check 12V Power and `L_EN`/`R_EN` wiring.
   - *Jerky movement?* Wiring noise or "Soft Start" tuning needed.
   - *One motor stuck?* Check its specific connections.

## 3. Test ArtNet Network Control
1. **Disconnect Pin 2** (Open Circuit).
2. Connect Ethernet cable to your router/switch.
3. Configure your ArtNet Controller (Resolume, MadMapper, etc.):
   - Target IP: `192.168.1.201`
   - Universe: `0`
4. **Expected Result**: Changing Channel 1 fader should move Actuator 1.
5. **Ping Test**: Open Terminal on your computer and type:
   `ping 192.168.1.201`
   If you don't get a reply, check your computer's IP settings (must be in 192.168.1.xxx range).

## 4. Tuning
If the motion feels wrong, adjust these values in the code:
- **PWM_MIN**: Increase if motors "whine" but don't move at low speeds.
- **Ramp Speed (+100)**: Decrease this number for softer starts, increase for snappier response.

## 5. Local Verification (Mac/PC)
You can run the control interface on your computer before moving to the Raspberry Pi.

1.  **Connect Arduino**: Plug the Arduino Mega into your computer via USB.
2.  **Open Terminal**: Navigate to the `RaspberryPi_Controller` folder.
    ```bash
    cd "/Users/michael/Documents/Arduino/Actually working/Kinsculpt_Actuator_Artnet/RaspberryPi_Controller"
    ```
3.  **Run the Script**:
    ```bash
    sh run.sh
    ```
4.  **Open Browser**: Go to `http://localhost:8080`.
    - You should see the GUI.
    - Click "Auto-Connect USB" to find the Arduino.
    - Move sliders to test motors.
