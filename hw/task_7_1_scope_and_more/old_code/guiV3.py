import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Button
import sys

# --- CONFIGURATION ---
SERIAL_PORT = '/dev/ttyACM0' # Check your port!
BAUD_RATE = 115200
MAX_VOLTAGE = 3.3
ADC_RESOLUTION = 65535
SAMPLES = 300 

# --- STATE MANAGEMENT ---
# Modes: 'RUN', 'STOP', 'SINGLE_ARMED'
current_state = 'RUN'

# --- CONNECTION ---
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    ser.dtr = True 
    ser.rts = True
    print(f"Connected to {SERIAL_PORT}...")
except Exception as e:
    print(f"Error connecting: {e}")
    sys.exit()

# --- GUI SETUP ---
fig, ax = plt.subplots(figsize=(10, 7))
plt.subplots_adjust(bottom=0.2) # Make room for buttons at the bottom
fig.canvas.manager.set_window_title('Pico Scope Final')

# Styling
ax.set_facecolor('#1e1e1e')
ax.grid(True, color='#444444', linestyle='--')
ax.set_ylim(-0.1, MAX_VOLTAGE + 0.2)
ax.set_xlim(0, SAMPLES)
ax.set_ylabel("Voltage (V)")
ax.set_xlabel("Sample Index")

# Plot Lines
line1, = ax.plot([], [], color='#00ff00', linewidth=1.2, label='CH1')
line2, = ax.plot([], [], color='#00ffff', linewidth=1.2, label='CH2')
ax.legend(loc='upper right', facecolor='#111111', edgecolor='white', labelcolor='white')

# Info Box
info_text = ax.text(0.02, 0.95, "Mode: RUN", transform=ax.transAxes,
                    fontsize=11, color='white', verticalalignment='top',
                    bbox=dict(boxstyle="round", facecolor='#111111', alpha=0.8))

# --- BUTTON CALLBACKS ---
def set_run(event):
    global current_state
    current_state = 'RUN'
    info_text.set_text("Mode: RUN")
    print("State: RUN")

def set_stop(event):
    global current_state
    current_state = 'STOP'
    info_text.set_text("Mode: STOPPED")
    print("State: STOPPED")

def set_single(event):
    global current_state
    current_state = 'SINGLE_ARMED'
    info_text.set_text("Mode: SINGLE (Waiting for signal...)")
    print("State: ARMED (Waiting for Vpp > 0.5V)")

# --- DRAW BUTTONS ---
# Button positions: [left, bottom, width, height]
ax_run = plt.axes([0.15, 0.05, 0.2, 0.075])
btn_run = Button(ax_run, 'Run', color='#00aa00', hovercolor='#00ff00')
btn_run.on_clicked(set_run)

ax_stop = plt.axes([0.4, 0.05, 0.2, 0.075])
btn_stop = Button(ax_stop, 'Stop', color='#aa0000', hovercolor='#ff0000')
btn_stop.on_clicked(set_stop)

ax_single = plt.axes([0.65, 0.05, 0.2, 0.075])
btn_single = Button(ax_single, 'Single', color='#aa8800', hovercolor='#ffee00')
btn_single.on_clicked(set_single)

def update(frame):
    global current_state
    
    try:
        # Always clear buffer to keep latency low, unless we are stopped (save CPU)
        if current_state == 'STOP':
             # Read and discard to prevent buffer overflow, but don't parse
            if ser.in_waiting > 1000: ser.reset_input_buffer()
            return line1, line2, info_text

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
                
                # Metrics parsing
                m_vals = metrics_str.replace("METRICS:", "").split(',')
                vpp = float(m_vals[0])
                freq = float(m_vals[1])
                duty = float(m_vals[2])
                
                # Logic for SINGLE SWEEP
                if current_state == 'SINGLE_ARMED':
                    # Trigger Condition: Is the signal "interesting"?
                    # e.g., Vpp > 0.5V means something is happening.
                    # If signal is just noise (<0.5V), ignore this frame and keep waiting.
                    if vpp < 0.5:
                        return line1, line2, info_text
                    else:
                        # Trigger found! Update state to STOP after plotting this frame
                        current_state = 'STOP'
                        info_text.set_text("Mode: SINGLE (Captured!)")

                # Parse Data and Plot
                raw_vals = data_str.split(',')
                ch1_vals = []
                ch2_vals = []
                
                for i in range(0, len(raw_vals)-1, 2):
                    try:
                        v1 = int(raw_vals[i]) * (MAX_VOLTAGE / ADC_RESOLUTION)
                        v2 = int(raw_vals[i+1]) * (MAX_VOLTAGE / ADC_RESOLUTION)
                        ch1_vals.append(v1)
                        ch2_vals.append(v2)
                    except ValueError:
                        continue
                
                x_axis = range(len(ch1_vals))
                line1.set_data(x_axis, ch1_vals)
                line2.set_data(x_axis, ch2_vals)
                
                # Only update text if we are running (don't overwrite "Captured!" text)
                if current_state == 'RUN':
                    status_str = f"RUNNING | CH1 Vpp: {vpp:.2f}V | Freq: {freq:.0f}Hz"
                    info_text.set_text(status_str)
                
    except Exception as e:
        print(f"Error: {e}")

    return line1, line2, info_text

ani = animation.FuncAnimation(fig, update, interval=10, blit=False, cache_frame_data=False)
plt.show()