# ME461 – Raspberry Pi Pico W Communication Experiments

### MQTT (Mosquitto) • UDP Multicast • WiFi Web Server • Distributed Bouncing Ball Game

This repository contains multiple communication prototypes for Raspberry Pi Pico W boards, developed as part of **ME461 – Mechatronic Components & Instrumentation**.
Each folder represents a distinct communication method between two or more Picos, as well as a distributed multi-screen game project.

---

# Folder Structure Overview

project-root/
│
├── task_6_bouncing_ball/
│   └── Distributed multi-Pico bouncing ball game
│
├── mosquito/
│   ├── micropython-umqtt.simple-1.3.4/   → MQTT library for MicroPython
│   ├── main.py                            		    → combined experiments
│   ├── publisher.py                      		    → basic MQTT publisher
│   ├── subscriber.py                     	    → basic MQTT subscriber
│   ├── publisher_subscriber_a.py            → Pico A two-way
│   ├── publisher_subscriber_b.py            → Pico B two-way
│   │
│   └── udp_multicasting/
│       └── main.py                       		    → (deprecated) multicast experiment
│
└── web_server/
    ├── ap_server.py                                   → Pico as WiFi Access Point
    ├── sta_client.py                                    → Pico as WiFi Station (HTTP)
    └── related assets




# 1. Mosquitto MQTT Communication (`/mosquito`)

These scripts demonstrate reliable Pico-to-Pico communication using MQTT with a Mosquitto broker.

## Included Scripts

### `publisher_subscriber_a.py` & `publisher_subscriber_b.py`

Two Pico scripts used to verify two-way communication.

- Pico A publishes → Pico B receives
- Pico B publishes → Pico A receives

### `publisher.py`

Simple MQTT publisher example.

### `subscriber.py`

Basic MQTT subscriber example.

### `main.py`

A combined experimental script for testing multiple behaviors.

### `micropython-umqtt.simple-1.3.4/`

MicroPython MQTT client library (`umqtt.simple` and `umqtt.robust`).
This folder must be copied to the Pico filesystem.

# 2. UDP Multicasting (`/mosquito/udp_multicasting`)

An early attempt at communication using UDP multicast.

**Note:**MicroPython on Pico W does *not* fully support multicast features such as:

- `inet_aton`
- IGMP membership
- multicast TTL

This code is included only for reference and is not used in the final system.

---

# 3. Web Server Communication (`/web_server`)

Scripts for HTTP communication using Pico W as Access Point or Station.

### Files

- `ap_server.py` – Pico runs a WiFi Access Point and serves an HTML page
- `sta_client.py` – Pico connects to existing WiFi and performs HTTP requests

---

# 4. Distributed Bouncing Ball Game (`/task_6_bouncing_ball`)

A multi-device distributed game in which:

- Picos elect a leader (main physics engine)
- Each Pico sends heartbeat signals
- Multiple OLED screens combine into one large virtual display
- A ball bounces across all screens

Each Pico controls a slice of the screen.
The system handles dynamic Pico online/offline changes automatically.

---

# Required Hardware

- Raspberry Pi Pico W (one or more)
- SSD1306 OLED display (I2C, 128×64)
- Jumper wires & breadboard
- Wi-Fi network or laptop hotspot
- Laptop running Mosquitto MQTT broker

---

# Pico W → SSD1306 OLED Wiring (I2C)

Your project uses these exact pins:

- SDA → GP10
- SCL → GP11

## Wiring Table

| SSD1306 Pin | Pico W Pin | Notes         |
| ----------- | ---------- | ------------- |
| VCC         | 3.3V       | Do not use 5V |
| GND         | GND        | Common ground |
| SDA         | GP10       | I2C Data      |
| SCL         | GP11       | I2C Clock     |

---

# Raspberry Pi Pico W Pinout Diagram (Simplified)

    ┌────────────────────────────────┐
 3V3    ───│●                                     					    ●│─── VBUS (5V)
 GP0   ───│●                                     					    ●│─── VSYS
 GP1   ───│●   RASPBERRY PI PICO W PINOUT        	    ●│─── GND
 GND  ───│●                                      					    ●│─── GP26 (ADC0)
 GP2   ───│●                                     					    ●│─── GP27 (ADC1)
 GP3   ───│●                                     					    ●│─── GP28 (ADC2)
 GP4   ───│●                                    					    ●│─── ADC REF
 GP5   ───│●                                     					    ●│─── 3V3_EN
 GND  ───│●                                     					    ●│─── RUN (reset)
 GP6   ───│●                                     					    ●│─── GP22
 GP7   ───│●                                     					    ●│─── GND
 GP8   ───│●                                     					    ●│─── GP21
 GP9   ───│●                                     					    ●│─── GP20
 GP10 ───│●  ← SDA (SSD1306)                    			    ●│─── GP19
 GP11 ───│●  ← SCL (SSD1306)                     			    ●│─── GP18
 GP12 ───│●                                     					    ●│─── GP17
 GP13 ───│●                                     					    ●│─── GP16
 GND  ───│●                                     					    ●│─── GND
 GP14 ───│●                                     					    ●│─── GP15
         	  └────────────────────────────────┘


# Running MQTT Communication

## 1. Install Mosquitto on your computer (Ubuntu example)

```bash
sudo apt install mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

## 2. Test the broker

```bash
mosquitto_sub -t test
mosquitto_pub -t test -m "hello"
```

## 3. Flash scripts to Picos

- Flash `publisher_subscriber_a.py` to Pico A
- Flash `publisher_subscriber_b.py` to Pico B
- Set:
  - `MY_ID = 0` for Pico A
  - `MY_ID = 1` for Pico B

## 4. Communication should start

Each Pico should print the other's messages through MQTT.

---

# Running the Distributed Bouncing Ball Game

1. Start your Mosquitto broker
2. Connect all Picos to the same Wi-Fi network
3. Flash the game script to each Pico
4. Assign each Pico a unique `MY_ID`
5. OLED screens together form one large display
6. The ball moves across all screens continuously
7. Leader Pico runs physics; followers only draw

---

# Summary

| Folder                    | Purpose                                  |
| ------------------------- | ---------------------------------------- |
| `mosquito/`             | MQTT communication (stable, recommended) |
| `udp_multicasting/`     | Experimental multicast (unsupported)     |
| `web_server/`           | AP/STA WiFi + HTTP communication         |
| `task_6_bouncing_ball/` | Distributed multi-Pico game              |

---

If you want, I can generate:

- A PDF tutorial
- A more graphical README with images
- Block diagrams or architecture charts
- A demonstration script for ME461 presentation
