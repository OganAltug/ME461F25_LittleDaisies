import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import sys

# --- CONFIGURATION ---
SERIAL_PORT = '/dev/ttyACM0' 
BAUD_RATE = 115200
MAX_VOLTAGE = 3.3
ADC_RESOLUTION = 65535

# Fixed limits for RUN mode
FIXED_SAMPLES = 600 

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
fig.canvas.manager.set_window_title('Pico Scope (Smart Axis)')
ax.set_facecolor('#1e1e1e')
ax.grid(True, color='#444444', linestyle='--')
ax.set_ylabel("Voltage (V)")
ax.set_xlabel("Sample Index")

line, = ax.plot([], [], color='#00ff00', linewidth=1.5)

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
                status_text.set_color('cyan')
                return line, status_text

            if decoded_line.startswith("METRICS:"):
                parts = decoded_line.split("|DATA:")
                if len(parts) < 2: return line, status_text
                
                # Parse TAG
                tag = "RUN"
                if "|TAG:" in parts[1]:
                    d_part, t_part = parts[1].split("|TAG:")
                    data_str = d_part
                    tag = t_part
                else:
                    data_str = parts[1]

                # Parse Data
                y_data = []
                for x in data_str.split(','):
                    try:
                        val = int(x) * (MAX_VOLTAGE / ADC_RESOLUTION)
                        y_data.append(val)
                    except ValueError:
                        pass
                
                if len(y_data) > 0:
                    # Update Line
                    line.set_data(range(len(y_data)), y_data)
                    
                    # --- SMART AXIS LOGIC ---
                    if tag == "RUN":
                        # Requirement: Revert to fixed axis for continuous running
                        ax.set_xlim(0, FIXED_SAMPLES)
                        ax.set_ylim(-0.1, MAX_VOLTAGE + 0.1)
                        
                        status_text.set_text("CONTINUOUS (Fixed Axis)")
                        status_text.set_color('#00ff00')
                        
                    elif tag == "SINGLE":
                        # Requirement: Dynamic fit for Single Shot
                        # Fit X to exactly the number of samples captured
                        ax.set_xlim(0, len(y_data))
                        
                        # Fit Y to the specific transient voltage
                        ymin = min(y_data)
                        ymax = max(y_data)
                        padding = (ymax - ymin) * 0.1 if (ymax-ymin) > 0.1 else 0.2
                        ax.set_ylim(ymin - padding, ymax + padding)
                        
                        status_text.set_text(f"SINGLE SHOT (Dynamic: {len(y_data)} samples)")
                        status_text.set_color('#ff0000')

    except Exception as e:
        print(f"Error: {e}")

    return line, status_text

ani = animation.FuncAnimation(fig, update, interval=20, blit=False, cache_frame_data=False)
plt.show()