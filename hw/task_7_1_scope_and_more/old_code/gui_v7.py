import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Button
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
fig, ax = plt.subplots(figsize=(10, 8))
plt.subplots_adjust(bottom=0.2) # Make room for buttons
fig.canvas.manager.set_window_title('Pico Scope (Remote Control)')

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

# --- CONTROL LOGIC ---
def send_command(cmd):
    """Sends a single character command to the Pico."""
    try:
        ser.write(cmd.encode())
        print(f"Sent command: {cmd}")
    except Exception as e:
        print(f"Serial Write Error: {e}")

def callback_run(event):
    send_command('R') # 'R' for Run

def callback_single(event):
    send_command('S') # 'S' for Single Arm

def callback_stop(event):
    send_command('H') # 'H' for Hold/Stop

# --- BUTTONS ---
# [left, bottom, width, height]
ax_run = plt.axes([0.1, 0.05, 0.2, 0.075])
btn_run = Button(ax_run, 'Run (Cont)', color='#008800', hovercolor='#00ff00')
btn_run.on_clicked(callback_run)

ax_single = plt.axes([0.4, 0.05, 0.2, 0.075])
btn_single = Button(ax_single, 'Single Shot', color='#aa8800', hovercolor='#ffff00')
btn_single.on_clicked(callback_single)

ax_stop = plt.axes([0.7, 0.05, 0.2, 0.075])
btn_stop = Button(ax_stop, 'Stop / Hold', color='#880000', hovercolor='#ff0000')
btn_stop.on_clicked(callback_stop)

def update(frame):
    try:
        if ser.in_waiting > 0:
            raw_line = ser.readline()
            try:
                decoded_line = raw_line.decode('utf-8').strip()
            except UnicodeDecodeError:
                return line, info_text, status_text

            # Handle Text Messages
            if decoded_line.startswith("MSG:"):
                msg = decoded_line.replace("MSG:", "")
                status_text.set_text(msg)
                status_text.set_color('cyan')
                return line, info_text, status_text

            # Handle Data Packets
            if decoded_line.startswith("METRICS:"):
                parts = decoded_line.split("|DATA:")
                if len(parts) < 2: return line, info_text, status_text
                
                # Extract Tag
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
                    status_text.set_color('#00ff00') 
                elif tag == "SINGLE":
                    status_text.set_text("SINGLE SHOT CAPTURED")
                    status_text.set_color('#ff0000') 

                info_text.set_text(f"Vpp: {vpp:.2f} V")
                
    except Exception as e:
        print(f"Error: {e}")

    return line, info_text, status_text

ani = animation.FuncAnimation(fig, update, interval=10, blit=False, cache_frame_data=False)
plt.show()