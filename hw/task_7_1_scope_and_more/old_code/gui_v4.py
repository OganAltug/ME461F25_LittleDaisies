import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import sys

# --- CONFIGURATION ---
SERIAL_PORT = '/dev/ttyACM0' # <--- CHECK THIS
BAUD_RATE = 115200
MAX_VOLTAGE = 3.3
ADC_RESOLUTION = 65535
SAMPLES = 1000 

# --- CONNECTION ---
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    ser.dtr = True 
    ser.rts = True
    print(f"Connected to {SERIAL_PORT}...")
except Exception as e:
    print(f"Error: {e}")
    sys.exit()

# --- GUI SETUP ---
fig, ax = plt.subplots(figsize=(10, 7))
fig.canvas.manager.set_window_title('Pico Scope (Hardware Trigger)')
ax.set_facecolor('#1e1e1e')
ax.grid(True, color='#444444', linestyle='--')
ax.set_ylim(-0.1, MAX_VOLTAGE + 0.2)
ax.set_xlim(0, SAMPLES)
ax.set_ylabel("Voltage (V)")
ax.set_xlabel("Sample Index")

line, = ax.plot([], [], color='#00ff00', linewidth=1.2)

# Status Boxes
info_text = ax.text(0.02, 0.95, "Connecting...", transform=ax.transAxes,
                    fontsize=12, color='white', verticalalignment='top',
                    bbox=dict(boxstyle="round", facecolor='#111111', alpha=0.8))

status_text = ax.text(0.5, 1.05, "WAITING FOR DATA", transform=ax.transAxes,
                      fontsize=14, color='yellow', ha='center', weight='bold')

def update(frame):
    try:
        if ser.in_waiting > 0:
            raw_line = ser.readline()
            try:
                decoded_line = raw_line.decode('utf-8').strip()
            except UnicodeDecodeError:
                return line, info_text, status_text

            # Handle Text Messages from Pico (e.g., "MSG:Switching...")
            if decoded_line.startswith("MSG:"):
                msg = decoded_line.replace("MSG:", "")
                status_text.set_text(msg)
                status_text.set_color('cyan')
                return line, info_text, status_text

            # Handle Data Packets
            if decoded_line.startswith("METRICS:"):
                parts = decoded_line.split("|DATA:")
                if len(parts) < 2: return line, info_text, status_text
                
                # Extract Tag if present
                tag = "RUN"
                if "|TAG:" in parts[1]:
                    d_part, t_part = parts[1].split("|TAG:")
                    data_str = d_part
                    tag = t_part
                else:
                    data_str = parts[1]

                metrics_str = parts[0].replace("METRICS:", "")
                m_vals = metrics_str.split(',')
                vpp = float(m_vals[0])

                # Parse Data
                y_data = []
                for x in data_str.split(','):
                    try:
                        val = int(x) * (MAX_VOLTAGE / ADC_RESOLUTION)
                        y_data.append(val)
                    except ValueError:
                        pass
                
                # Update Plot
                line.set_data(range(len(y_data)), y_data)
                
                # Update Status based on TAG
                if tag == "RUN":
                    status_text.set_text("CONTINUOUS RUNNING")
                    status_text.set_color('#00ff00') # Green
                elif tag == "SINGLE":
                    status_text.set_text("SINGLE SHOT CAPTURED")
                    status_text.set_color('#ff0000') # Red (Frozen)

                info_text.set_text(f"Vpp: {vpp:.2f} V")
                
    except Exception as e:
        print(f"Error: {e}")

    return line, info_text, status_text

ani = animation.FuncAnimation(fig, update, interval=10, blit=False, cache_frame_data=False)
plt.show()