# 📟 Embedded Systems Assignment – Hardware Demonstration

### Raspberry Pi Pico Based Sensor & Display Integration

This project demonstrates the functionality of all required hardware components soldered onto our custom board.
Each component is tested in a meaningful and interactive theme to verify correct operation.

---

## ✅ Demonstrated Hardware Components

### 1️⃣ Potentiometer (POT)

- Used as an **analog absolute input**.
- Mapped to ADC range (0–4095).
- Controls:
  - Brightness
  - Menu selection
  - Parameter adjustment
- Demonstrated stable and noise-free readings.

---

### 2️⃣ Rotary Encoder + Push Button

- Fully working with:
  - **CW/CCW rotation detection**
  - **Increment/decrement counter**
  - **Button press detection**
- Used for **menu navigation & selection**.

---

### 3️⃣ MPU6050 (IMU – Accelerometer + Gyroscope)

- Successfully initialized via **I2C**.
- Demonstrated:
  - Pitch & roll measurement
  - Motion detection
  - Tilt-controlled interaction
- Can be integrated with the **8×8 Dot Matrix** for dynamic visual feedback.

---

### 4️⃣ 0.96" OLED Display (SSD1306)

Displayed:

- Live sensor values
- System menu
- Status/info screens
- Debug information
  Clear and readable output fully verified.

---

### 5️⃣ Buzzer

- Used responsibly (non-annoying).
- Provides:
  - Menu click sounds
  - Error alerts
  - Simple tones
- Duty cycle tuned for minimal disturbance.

---

### 6️⃣ Ultrasonic Sensor (HC-SR04)

- Real-time distance measurement.
- Threshold-based event triggers.
- Stable echo timing verified.

---

### 7️⃣ 8×8 LED Dot Matrix (MAX7219)

Displayed:

- Scrolling text
- Icons
- IMU-reactive animations
- Brightness control (linked to POT)

---

## 🧩 Integration Theme

### **“Multi-Sensor Control Dashboard”**

All components are integrated into a unified, interactive system:

- POT → controls brightness / settings
- Encoder → navigates menu
- OLED → displays menus & sensor outputs
- IMU → controls directional graphics on dot-matrix
- Ultrasonic → proximity detection triggers buzzer
- Buzzer → feedback sounds
- Dot Matrix → animations & indicators

This validates full sensor–actuator integration.

---

## 📁 Project Structure

```
/project
│── src/
│    ├── main.py
│    ├── imu.py
│    ├── encoder.py
│    ├── oled.py
│    ├── buzzer.py
│    ├── ultrasonic.py
│    ├── dotmatrix.py
│── lib/
│    ├── mpu6050.py
│    ├── ssd1306.py
│    ├── max7219.py
│── README.md

```

## 🔧 Hardware Used

- Raspberry Pi Pico
- Potentiometer
- Rotary Encoder + Button
- MPU6050 IMU
- SSD1306 OLED (I2C)
- HC-SR04 Ultrasonic Sensor
- MAX7219 LED Matrix (SPI)
- Piezo Buzzer

## 📌 Assignment Requirements

All 7 required components were demonstrated.
Components previously shown in the *scope assignment* were not repeated.
Remaining components were showcased individually and as part of the integrated system.

✔ Inputs
✔ Outputs
✔ Displays
✔ Sensors
✔ Actuators
✔ Multi-device integration

All working as required.

---


# 🪛 Raspberry Pi Pico Wiring Diagram

Below is the complete wiring map for all components used in the project.

---

## 📌 Pinout Summary

| Component                               | Pico Pin    | Signal | Notes                                     |
| --------------------------------------- | ----------- | ------ | ----------------------------------------- |
| **Potentiometer**                 | GP26 (ADC0) | AOUT   | Analog input                              |
|                                         | 3V3         | VCC    | 3.3V                                      |
|                                         | GND         | GND    | Ground                                    |
| **Rotary Encoder**                | GP14        | CLK    | Encoder rotation                          |
|                                         | GP15        | DT     | Encoder rotation                          |
|                                         | GP13        | SW     | Pushbutton                                |
|                                         | 3V3         | VCC    |                                           |
|                                         | GND         | GND    |                                           |
| **MPU6050 (IMU)**                 | GP4         | SDA    | I2C1 SDA                                  |
|                                         | GP5         | SCL    | I2C1 SCL                                  |
|                                         | 3V3         | VCC    | Do NOT use 5V                             |
|                                         | GND         | GND    |                                           |
| **SSD1306 OLED**                  | GP4         | SDA    | Shared I2C bus with IMU                   |
|                                         | GP5         | SCL    | Shared I2C bus with IMU                   |
|                                         | 3V3         | VCC    |                                           |
|                                         | GND         | GND    |                                           |
| **HC-SR04 Ultrasonic**            | GP2         | TRIG   | Output from Pico                          |
|                                         | GP3         | ECHO   | INPUT → use voltage divider (5V to 3.3V) |
|                                         | 5V          | VCC    | Requires 5V                               |
|                                         | GND         | GND    |                                           |
| **Piezo Buzzer**                  | GP10        | SIG    | PWM sound output                          |
|                                         | GND         | GND    |                                           |
| **8×8 LED Dot Matrix (MAX7219)** | GP18        | DIN    | SPI MOSI                                  |
|                                         | GP19        | CLK    | SPI SCK                                   |
|                                         | GP17        | CS     | Chip Select                               |
|                                         | 5V          | VCC    | MAX7219 needs 5V                          |
|                                         | GND         | GND    |                                           |

---

## 🖼️ Block Wiring Diagram (ASCII Style)

```
            ┌───────────────────┐
            │   Raspberry Pi    │
            │       Pico        │
            └───────────────────┘
               │   │   │   │
               │   │   │   └────────────── Pot (ADC)
               │   │   └────────────────── Encoder
               │   └────────────────────── IMU + OLED (I2C)
               └────────────────────────── Ultrasonic / Buzzer / Matrix

```


```
       ┌───────────────────────────────────────┐
3V3 ───│● 				      ●│─── VBUS (5V)
GP0 ───│● 				      ●│─── VSYS
GP1 ───│● 				      ●│─── GND
GND ───│● 				      ●│─── GP26 (ADC0) ← Potentiometer OUT
GP2 ───│● ← HC-SR04 TRIG 		      ●│─── GP27 (ADC1)
GP3 ───│● ← HC-SR04 ECHO(via voltage divider!)●│─── GP28 (ADC2)
GP4 ───│● ← SDA (MPU6050 + OLED SSD1306)      ●│─── ADC REF
GP5 ───│● ← SCL (MPU6050 + OLED SSD1306)      ●│─── 3V3_EN
GND ───│● 				      ●│─── RUN
GP6 ───│● 				      ●│─── GP22
GP7 ───│● 				      ●│─── GND
GP8 ───│●				      ●│─── GP21
GP9 ───│● 				      ●│─── GP20
GP10───│● ← Buzzer (PWM audio output) 	      ●│─── GP19 ← MAX7219 CLK
GP11───│● 				      ●│─── GP18 ← MAX7219 DIN
GP12───│● 				      ●│─── GP17 ← MAX7219 CS
GP13───│● ← Rotary Encoder SW (button)        ●│─── GP16
GND ───│● 				      ●│─── GND
GP14───│● ← Rotary Encoder CLK 	              ●│─── GP15 ← Rotary Encoder DT
       └───────────────────────────────────────┘
```
