import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import sys

# --- CONFIGURATION ---
SERIAL_PORT = '/dev/ttyACM0' 
BAUD_RATE = 115200
MAX_VOLTAGE = 3.3
ADC_RESOLUTION = 65535

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
fig.canvas.manager.set_window_title('Pico Scope (Dynamic Axis)')
ax.set_facecolor('#1e1e1e')
ax.grid(True, color='#444444', linestyle='--')
ax.set_ylabel("Voltage (V)")
ax.set_xlabel("Sample Index")

# Note: We DO NOT set static limits here anymore!
line, = ax.plot([], [], color='#00ff00', linewidth=1.5)

# Text elements
status_text = ax.text(0.5, 1.05, "WAITING...", transform=ax.transAxes,
                      fontsize=14, color='yellow', ha='center', weight='bold')

def update(frame):
    try:
        if ser.in_waiting > 0:
            raw_line = ser.readline()
            try:
                decoded_line = raw_line.decode('utf-8').strip()
            except UnicodeDecodeError:
                return line, status_text

            if decoded_line.startswith("MSG:"):
                msg = decoded_line.replace("MSG:", "")
                status_text.set_text(msg)
                return line, status_text

            if decoded_line.startswith("METRICS:"):
                parts = decoded_line.split("|DATA:")
                if len(parts) < 2: return line, status_text
                
                # 1. Parse Tag
                tag = "RUN"
                if "|TAG:" in parts[1]:
                    d_part, t_part = parts[1].split("|TAG:")
                    data_str = d_part
                    tag = t_part
                else:
                    data_str = parts[1]

                # 2. Parse Data
                y_data = []
                for x in data_str.split(','):
                    try:
                        val = int(x) * (MAX_VOLTAGE / ADC_RESOLUTION)
                        y_data.append(val)
                    except ValueError:
                        pass
                
                # 3. DYNAMIC SCALING (The Fix)
                if len(y_data) > 0:
                    # Update Line
                    x_data = range(len(y_data))
                    line.set_data(x_data, y_data)
                    
                    # Auto-Scale Axes
                    ax.set_xlim(0, len(y_data)) # Fit X to exact sample count
                    
                    # Fit Y with a small margin (padding)
                    ymin = min(y_data)
                    ymax = max(y_data)
                    
                    # If signal is flat, give it some room so it doesn't look weird
                    if ymax - ymin < 0.1:
                        cy = (ymax + ymin) / 2
                        ax.set_ylim(cy - 0.1, cy + 0.1)
                    else:
                        # Add 10% padding top and bottom
                        margin = (ymax - ymin) * 0.1
                        ax.set_ylim(ymin - margin, ymax + margin)

                # 4. Update Status
                if tag == "RUN":
                    status_text.set_text("CONTINUOUS RUNNING")
                    status_text.set_color('#00ff00')
                elif tag == "SINGLE":
                    status_text.set_text("SINGLE SHOT CAPTURED")
                    status_text.set_color('#ff0000')

    except Exception as e:
        print(f"Error: {e}")

    return line, status_text

ani = animation.FuncAnimation(fig, update, interval=20, blit=False, cache_frame_data=False)
plt.show()