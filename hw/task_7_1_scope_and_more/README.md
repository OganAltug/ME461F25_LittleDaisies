# 🔬 ME489: Pico 4 Pico Oscilloscope & Signal Generator

## 🎯 Project Overview

This project implements a low-cost, high-speed digital **oscilloscope** and **signal generator** utilizing the **Raspberry Pi Pico**. [cite_start]All Analog-to-Digital (AD) conversions occur on the Pico, while signal processing and visualization are handled by a dedicated GUI running on a PC

The core aim is to create a functional instrument that prioritizes a **creative and intuitive user interface** over replicating the look and feel of classical scopes.

## ⚙️ Technical Specifications

### I. Scope (Input)

| Feature                         | Specification                                                                                                                                                                                      |
| :------------------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Input Voltage Range**   | 0V to 3.3V                                                                                                                                                                                         |
| **Channels**              | Minimum of 2 simultaneous channels                                                                                                                                                                 |
| **Measurement Stability** | Highest frequency stably and accurately displayed determines baseline performance                                                                                                                  |
| **Triggering**            | Must enable stable display of periodic signals.<br />Essential for testing single sweep captures (e.g., button bouncing, RC circuits)                                                              |
| **Auto-Measurements**     | Peak-to-Peak values ($V_{pp})$always available. Frequency and Period automatically displayed for periodic signals. <br /> Duty Cycle (DC) automatically displayed for square waves[cite: 572]. |

### II. Signal Generator (Output)

*(Technical specifications for the signal generator output must be defined by the group as only the scope specifications were detailed in the brief.)*

## ✨ Bonuses

* **XY Plotting:** Implement plotting Channel A vs. Channel B[cite: 574].
* **Creative Interface:** Simple, intuitive GUI additions[cite: 576].
* **Performance:** Fast GUI response to changes in settings.

## 💻 Hardware & Software Stack

| Component                       | Responsibility                                      | Technology                                            |
| :------------------------------ | :-------------------------------------------------- | :---------------------------------------------------- |
| **Microcontroller (MCU)** | Fast AD conversion, DMA management, USB data stream | Raspberry Pi Pico (RP2040)                            |
| **Firmware**              | High-speed data acquisition                         | C/C++ (Pico SDK)                                      |
| **Host PC**               | Signal processing, visualization, control input     | Python (PyQtGraph, pyserial) or similar GUI framework |

## 🚀 Getting Started

1. **Preparation:** Watch tutorials on oscilloscope basics to understand scope usage and screen capabilities.
2. **Clone:** Clone this repository to your local machine.
3. **Setup:** Install Pico SDK dependencies and the required PC host libraries (e.g., Python environment, pyserial).
4. **Implement:** Begin with the technical roadmap defined in the project documentation.
