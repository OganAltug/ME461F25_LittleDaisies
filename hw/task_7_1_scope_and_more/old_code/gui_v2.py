import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import sys

# --- CONFIGURATION ---
SERIAL_PORT = '/dev/ttyACM0' # Check your port!
BAUD_RATE = 115200
MAX_VOLTAGE = 3.3
ADC_RESOLUTION = 65535
SAMPLES = 300 

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    ser.dtr = True 
    ser.rts = True
    print(f"Connected to {SERIAL_PORT}...")
except Exception as e:
    print(f"Error connecting: {e}")
    sys.exit()

# --- GUI SETUP ---
fig, ax = plt.subplots(figsize=(10, 6))
fig.canvas.manager.set_window_title('Pico Scope (Dual Channel)')
ax.set_facecolor('#1e1e1e')
ax.grid(True, color='#444444', linestyle='--')
ax.set_ylim(-0.1, MAX_VOLTAGE + 0.2)
ax.set_xlim(0, SAMPLES)
ax.set_ylabel("Voltage (V)")
ax.set_xlabel("Sample Index")

# Two Lines
line1, = ax.plot([], [], color='#00ff00', linewidth=1.2, label='CH1 (GP26)')
line2, = ax.plot([], [], color='#00ffff', linewidth=1.2, label='CH2 (GP27)')
ax.legend(loc='upper right', facecolor='#111111', edgecolor='white', labelcolor='white')

info_text = ax.text(0.02, 0.95, "Waiting...", transform=ax.transAxes,
                    fontsize=11, color='#00ff00', verticalalignment='top',
                    bbox=dict(boxstyle="round", facecolor='#111111', alpha=0.8))

def update(frame):
    try:
        if ser.in_waiting > 0:
            raw_line = ser.readline()
            try:
                decoded_line = raw_line.decode('utf-8').strip()
            except UnicodeDecodeError:
                return line1, line2, info_text

            if decoded_line.startswith("METRICS:"):
                parts = decoded_line.split("|DATA:")
                if len(parts) != 2: return line1, line2, info_text
                
                metrics_str, data_str = parts
                
                # Metrics (CH1)
                m_vals = metrics_str.replace("METRICS:", "").split(',')
                vpp = float(m_vals[0])
                freq = float(m_vals[1])
                duty = float(m_vals[2])
                vavg = float(m_vals[3])
                
                # Data Parsing
                raw_vals = data_str.split(',')
                ch1_vals = []
                ch2_vals = []
                
                # Interleaved: 0->CH1, 1->CH2, 2->CH1, 3->CH2...
                for i in range(0, len(raw_vals)-1, 2):
                    try:
                        v1 = int(raw_vals[i]) * (MAX_VOLTAGE / ADC_RESOLUTION)
                        v2 = int(raw_vals[i+1]) * (MAX_VOLTAGE / ADC_RESOLUTION)
                        ch1_vals.append(v1)
                        ch2_vals.append(v2)
                    except ValueError:
                        continue
                
                # Update Plots
                x_axis = range(len(ch1_vals))
                line1.set_data(x_axis, ch1_vals)
                line2.set_data(x_axis, ch2_vals)
                
                status_str = (
                    f"CH1 Freq: {freq:.1f} Hz\n"
                    f"CH1 Duty: {duty:.1f} %\n"
                    f"CH1 Vpp:  {vpp:.2f} V"
                )
                info_text.set_text(status_str)
                
    except Exception as e:
        print(f"Error: {e}")

    return line1, line2, info_text

ani = animation.FuncAnimation(fig, update, interval=20, blit=True, cache_frame_data=False)
plt.show()