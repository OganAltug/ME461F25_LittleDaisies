# ME461 – Task 5 Tetris

### Raspberry Pi Pico W • MAX7219 LED Display • USB / WiFi / Web Server Communication

Fully Interactive 2-Player Tetris System

This repository contains all implementations of **Task 5 – Tetris on Raspberry Pi Pico W**, presented using three different communication methods:

1. USB Serial Mode
2. WiFi TCP Socket Mode
3. Web Server (HTTP Canvas Game)
4. WiFİ and USB Unified Mode

The project supports real-time two-player gameplay, a Pygame-based high-resolution PC client, a Pico-controlled MAX7219 LED matrix display (128×32 px), and JSON-based synchronization between PC and Pico.

---

# Folder Structure

# System Architecture

## Pico W (Game Server)

- Runs full Tetris logic
- Generates next tetromino
- Handles movement, rotation, collision, gravity
- Sends game state (JSON) to PC
- Receives keyboard input
- Draws current state on MAX7219 LED display

## PC (Game Client)

- High-resolution 60 FPS Pygame renderer
- Uses socket or serial communication
- Displays grid, score, next pieces
- Sends inputs to Pico

# MAX7219 LED Matrix Display (128×32)

8 chained MAX7219 modules → 128×32 grid.

## Wiring Table

| MAX7219 Pin | Pico W Pin  |
| ----------- | ----------- |
| VCC         | 5V          |
| GND         | GND         |
| DIN         | GP11 (MOSI) |
| CS          | GP9         |
| CLK         | GP10        |



# Raspberry Pi Pico W Pinout Diagram (Simplified)

```bash
         ┌───────────────────────────────────────┐
 3V3  ───│●                                     ●│─── VBUS (5V)
 GP0  ───│●                                     ●│─── VSYS
 GP1  ───│●   RASPBERRY PI PICO W PINOUT        ●│─── GND
 GND  ───│●                                     ●│─── GP26 (ADC0)
 GP2  ───│●                                     ●│─── GP27 (ADC1)
 GP3  ───│●                                     ●│─── GP28 (ADC2)
 GP4  ───│●                                     ●│─── ADC REF
 GP5  ───│●                                     ●│─── 3V3_EN
 GND  ───│●                                     ●│─── RUN (reset)
 GP6  ───│●                                     ●│─── GP22
 GP7  ───│●                                     ●│─── GND
 GP8  ───│●                                     ●│─── GP21
 GP9  ───│●   ←   CS                            ●│─── GP20
 GP10 ───│●   ←	  CLK                           ●│─── GP19
 GP11 ───│●   ←	  DIN                           ●│─── GP18
 GP12 ───│●                                     ●│─── GP17
 GP13 ───│●                                     ●│─── GP16
 GND  ───│●                                     ●│─── GND
 GP14 ───│●                                     ●│─── GP15
         └───────────────────────────────────────┘

```


---

# Communication Modes

## 1. USB Serial

- Simple serial JSON frames
- PC reads from `/dev/ttyACM0`
- No WiFi required

## 2. WiFi TCP Socket

- Pico = TCP server (`port 8080`)
- PC = TCP client
- JSON over sockets

## 3. Web Server

- Pico runs micro web server
- HTML + JS client in browser

---

# Running WiFi Version

## 1. Upload to Pico:

```
pico_tetris_wifi.py
max7219.py
```

## 2. Install Pygame:

```
pip install pygame
```

## 3. Run PC client:

```
python3 pc_client_wifi_naci.py
```

# Controls

| Player   | Action | Keys    |
| -------- | ------ | ------- |
| Player 1 | Move   | A / D   |
|          | Rotate | W       |
|          | Drop   | S       |
| Player 2 | Move   | ← / → |
|          | Rotate | ↑      |
|          | Drop   | ↓      |
| Both     | Pause  | P       |

# Summary

| Version | Communication | Notes            |
| ------- | ------------- | ---------------- |
| USB     | Serial JSON   | Simple & robust  |
| WiFi    | TCP Socket    | Real-time game   |
| Web     | HTTP/JS       | Play via browser |
| Unified | USB + WiFi    | Most flexible    |

---
