

# ME 461 - Lab 4: DC Motor Control with Pi Pico & L293D

This repository contains the implementation for Lab 4, focusing on driving DC motors (and inductive loads) using the Raspberry Pi Pico W and the L293D Quadruple Half-H Driver. The project moves from a basic Wokwi simulation to a full hardware implementation with a Python-based PC GUI capable of controlling motors via Serial (USB) and WiFi.

## 📂 Project Structure

The project is organized into four main modules matching the development stages:

```
LAB1/
├── l293d_led_motor/       # Phase 1: Wokwi Simulation & Driver Implementation
│   ├── diagram.json       # Wokwi circuit diagram
│   ├── l293d.chip.c       # Custom L293D chip logic
│   ├── main.py            # MicroPython firmware for simulation
│   └── wokwi-project.txt  # Project configuration
├── serial/                # Phase 2: Serial Communication Implementation
│   ├── pc_client_serial.py      # GUI running on PC (pyserial)
│   └── pico_server_serial.py    # Firmware for Pico (USB Serial)
├── wifi/                  # Phase 3: Wireless Implementation
│   ├── pc_client_wifi.py        # GUI running on PC (socket)
│   └── pico_server_wifi.py      # Firmware for Pico W (TCP Server)
└── wifi_serial/           # Phase 4: Robust Dual-Mode Implementation
    ├── pc_wifi_serial.py        # GUI with auto-failover (WiFi Primary -> Serial Backup)
    └── pico_wifi_serial.py      # Firmware handling concurrent connections
```

## 🔌 Hardware Wiring & Pinout

The system uses an **L293D H-Bridge** to drive two motors (Motor A and Motor B). In the simulation phase, "LED Motors" (bi-color LEDs) are used to visualize direction and duty cycle.

### Pin Mapping (Pico ↔ L293D)

| Signal                 | Pico Pin | L293D Pin | Function                   |
| ---------------------- | -------- | --------- | -------------------------- |
| **Motor A IN1**  | `GP0`  | Pin 2     | Motor A Control 1 (Left)   |
| **Motor A IN2**  | `GP1`  | Pin 7     | Motor A Control 2 (Left)   |
| **Motor B IN3**  | `GP17` | Pin 10    | Motor B Control 1 (Right)  |
| **Motor B IN4**  | `GP16` | Pin 15    | Motor B Control 2 (Right)  |
| **Enable A**     | 5V       | Pin 1     | Enable Motor A (Always On) |
| **Enable B**     | 5V       | Pin 9     | Enable Motor B (Always On) |
| **VCC1 (Logic)** | 5V       | Pin 16    | Logic Power                |
| **VCC2 (Motor)** | VBUS     | Pin 8     | Motor Power                |

### Raspberry Pi Pico W pinout diagram

```
	                   ┌────────────────────────────────────────────┐
     L293D IN1 (Left)  <---|● GP0                            VBUS (5V) ●|--- L293D Pin 16
     L293D IN2 (Left)  <---|● GP1                            VSYS      ●|--- L293D Pin 8
                           |● GND                            GND       ●|--- Common Ground
       Button FORWARD  --->|● GP2                            GP28      ●|
      Button BACKWARD  --->|● GP3                            GP27      ●|
                           |● GP4                            GP26      ●|
                           |● GP5                            RUN       ●|
                           |● GND                            GP22      ●|
                           |● GP6                            GND       ●|
                           |● GP7                            GP21      ●|
                           |● GP8                            GP20      ●|
                           |● GP9                            GP19      ●|
                           |● GP10                           GP18      ●|
                           |● GP11                           GP17      ●|---> L293D IN3 (Right)
                           |● GP12                           GP16      ●|---> L293D IN4 (Right)
                           |● GP13                           GP15      ●|
                           |● GP14                           GND       ●|
                           └────────────────────────────────────────────┘
```

### L293D pinout diagram

```
                       ┌───────────────────U───────────────────┐
      VCC / 5V       ---|● 1  EN1                     VCC1 16 ●|--- VBUS (5V)
      Pico GP0 (IN1) ---|● 2  IN1                     IN4  15 ●|--- Pico GP16 (IN4)
  [Left LEDs/Motor]  ---|● 3  OUT1                    OUT4 14 ●|--- [Right LEDs/Motor]
             GND     ---|● 4  GND                     GND  13 ●|------- GND
             GND     ---|● 5  GND                     GND  12 ●|------- GND
  [Left LEDs/Motor]  ---|● 6  OUT2                    OUT3 11 ●|--- [Right LEDs/Motor]
      Pico GP1 (IN2) ---|● 7  IN2                     IN3  10 ●|--- Pico GP17 (IN3)
      VBUS / Battery ---|● 8  VCC2 (Power)            EN2   9 ●|--- VCC / 5V
                        └───────────────────────────────────────┘

```

### Physical Inputs (Manual Control)

* **Button Forward:** Connected to `GP2`
* **Button Backward:** Connected to `GP3`

## 🛠 Features

### 1. Wokwi Simulation (`l293d_led_motor`)

* Custom C-implementation of the L293D chip for Wokwi.
* Simulates "LED Motors" to safely visualize H-Bridge polarity switching without external hardware.
* Verifies logic for Forward, Backward, and Stop states before deploying to the real Pico.

### 2. PC GUI Controller

A Python-based GUI (Tkinter) was developed to replace manual button presses. It supports:

* **Direction Control:** Forward (CW) and Backward (CCW).
* **Speed Control:** 0%, 25%, 50%, 75%, 100% duty cycles via PWM.
* **Motor Selection:** Independent control of Motor A, Motor B, or Both synchronously.
* **Visualization:** Real-time canvas drawing of the approximate PWM waveform.

### 3. Connectivity Modes

* **Serial Mode:** Uses UART over USB (`/dev/ttyACM0` or `COMx`). Low latency, requires cable.
* **WiFi Mode:** Uses TCP/IP sockets. Allows remote control of the robot/motors.
* **Dual Mode:** The ultimate solution. It attempts to connect via WiFi first. If the network is down or connection is lost, it automatically fails over to the Serial connection without crashing the application.

## 🚀 How to Run

### Prerequisites

* Python 3.x installed on PC.
* Required libraries: `tkinter`, `pyserial`.
* Raspberry Pi Pico W with MicroPython firmware installed.

### Running the Dual Mode (Recommended)

1. **Pico Setup:**
   * Open `wifi_serial/pico_wifi_serial.py` in Thonny.
   * Update `SSID` and `PASSWORD` with your credentials.
   * Save as `main.py` on the Pico W and reset.
2. **PC Setup:**
   * Run the client script:
     ```
     python wifi_serial/pc_wifi_serial.py
     ```
   * Enter the Pico's IP address (displayed in Thonny console) or select the COM port.
   * Click  **Auto Connect** .

## 📚 Lab Reference

* **Assignment:** `ME461-Lab4-DC-Motors-PiPico.pdf`
* **Driver Datasheet:** `l293_datasheet.pdf`
