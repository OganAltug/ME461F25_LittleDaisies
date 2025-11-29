# 📟 Embedded Systems Assignment – Hardware Demonstration

### Raspberry Pi Pico Based Sensor & Display Integration

This project demonstrates the functionality of all required hardware components soldered onto our custom board.
Each component is tested in a meaningful and interactive theme to verify correct operation.

--> Until mechaboards arrive, you can acces to the wokwi project we have made from the link: https://wokwi.com/projects/447998027500974081

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
│── mechaboard/
│    ├── main.py
│    ├── imu.py
│    ├── ssd1306.py.py
│    ├── vector3d.py
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

|  |
| - |

| Component                      | Signal | Pico Pin                | Notes                                 |
| ------------------------------ | ------ | ----------------------- | ------------------------------------- |
| **Button LEFT**          | BTN1   | **GP0**           | Digital input                         |
| **Button UP**            | BTN2   | **GP1**           | Digital input                         |
| **Button DOWN**          | BTN3   | **GP6**           | Digital input                         |
| **Button RIGHT**         | BTN4   | **GP7**           | Digital input                         |
| **Rotary Encoder**       | CLK    | **GP14**          | Encoder A                             |
|                                | DT     | **GP15**          | Encoder B                             |
|                                | SW     | **GP4**           | Push button                           |
| **Potentiometer**        | OUT    | **GP26 (ADC0)**   | 0–3.3V analog                        |
|                                | VCC    | 3V3                     |                                       |
|                                | GND    | GND                     |                                       |
| **I2C Bus (OLED + IMU)** | SDA    | **GP12**          | I2C0 SDA                              |
|                                | SCL    | **GP13**          | I2C0 SCL                              |
|                                | VCC    | 3V3                     |                                       |
|                                | GND    | GND                     |                                       |
| **Buzzer (PWM)**         | SIG    | **GP20**          | PWM audio                             |
| **MAX7219 Dot Matrix**   | DIN    | **GP3**           | SPI0 MOSI                             |
|                                | CLK    | **GP2**           | SPI0 SCK                              |
|                                | CS     | **GP5**           | Chip Select                           |
|                                | VCC    | 5V                      |                                       |
|                                | GND    | GND                     |                                       |
| **HC-SR04 Ultrasonic**   | TRIG   | **GP19**          | Output                                |
|                                | ECHO   | **GP18**          | Input (must include 5V→3.3V divider) |
|                                | VCC    | 5V                      |                                       |
|                                | GND    | GND                     |                                       |
| **External LED 1**       | LED1   | **GP16**          | Output                                |
| **External LED 2**       | LED2   | **GP17**          | Output                                |
| **External LED 3**       | LED3   | **GP21**          | Output                                |
| **External LED 4**       | LED4   | **GP22**          | Output                                |
| **Built-in LED**         | LED    | **Pico internal** | Always available                      |

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
                           ┌───────────────────────────────────────────┐
 3V3 ──────────────────────│●                                         ●│─── VBUS (5V)
 GP0  ← Button LEFT        │●                                         ●│─── VSYS
 GP1  ← Button UP          │●                                         ●│─── GND
 GND ──────────────────────│●                                         ●│─── GP26 (ADC0) ← Potentiometer OUT
 GP2  ← MAX7219 CLK        │●                                         ●│─── GP27 (ADC1)
 GP3  ← MAX7219 DIN        │●                                         ●│─── GP28 (ADC2)
 GP4  ← Encoder Button SW  │●                                         ●│─── ADC_REF
 GP5  ← MAX7219 CS         │●                                         ●│─── 3V3_EN
 GND ──────────────────────│●                                         ●│─── RUN
 GP6  ← Button DOWN        │●                                         ●│─── GP22 → External LED4
 GP7  ← Button RIGHT       │●                                         ●│─── GND
 GP8                       │●                                         ●│─── GP21 → External LED3
 GP9                       │●                                         ●│─── GP20 → Buzzer (PWM)
 GP10                      │●                                         ●│─── GP19 → HC-SR04 TRIG
 GP11                      │●                                         ●│─── GP18 → HC-SR04 ECHO (w/ divider)
 GP12 ← I2C SDA (OLED+IMU) │●                                         ●│─── GP17 → External LED2
 GP13 ← I2C SCL (OLED+IMU) │●                                         ●│─── GP16 → External LED1
 GND ──────────────────────│●                                         ●│─── GND
 GP14 ← Encoder CLK        │●                                         ●│─── GP15 ← Encoder DT
                           └───────────────────────────────────────────┘

 Built-in LED is always available as: machine.Pin("LED", OUT)

```
