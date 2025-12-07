import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Button, CheckButtons
import sys

# --- CONFIGURATION ---
SERIAL_PORT = '/dev/ttyACM0' # <--- CHECK THIS
BAUD_RATE = 115200
MAX_VOLTAGE = 3.3
ADC_RESOLUTION = 65535
TOTAL_SAMPLES = 1200 # Updated to match Pico (400 per channel)

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
plt.subplots_adjust(bottom=0.25) # More room for controls
fig.canvas.manager.set_window_title('Pico Triple Scope')

ax.set_facecolor('#1e1e1e')
ax.grid(True, color='#444444', linestyle='--')
ax.set_ylim(-0.1, MAX_VOLTAGE + 0.2)
ax.set_ylabel("Voltage (V)")
ax.set_xlabel("Sample Index")

# Lines
line1, = ax.plot([], [], color='#00ff00', linewidth=1.5, label='CH1')
line2, = ax.plot([], [], color='#00ffff', linewidth=1.5, label='CH2')
line3, = ax.plot([], [], color='#ff3333', linewidth=1.5, label='CH3') # New Channel (Red)
ax.legend(loc='upper right')

# Status Text
info_text = ax.text(0.02, 0.95, "Connecting...", transform=ax.transAxes,
                    fontsize=11, color='white', verticalalignment='top',
                    bbox=dict(boxstyle="round", facecolor='#111111', alpha=0.8))

status_text = ax.text(0.5, 1.05, "WAITING", transform=ax.transAxes,
                      fontsize=14, color='yellow', ha='center', weight='bold')

# --- CONTROLS ---
def send_command(cmd):
    try: ser.write(cmd.encode())
    except: pass

def callback_run(event): send_command('R')
def callback_single(event): send_command('S')
def callback_stop(event): send_command('H')

# Buttons [left, bottom, width, height]
ax_run = plt.axes([0.1, 0.05, 0.2, 0.075])
btn_run = Button(ax_run, 'Run', color='#008800', hovercolor='#00ff00')
btn_run.on_clicked(callback_run)

ax_single = plt.axes([0.35, 0.05, 0.2, 0.075])
btn_single = Button(ax_single, 'Single', color='#aa8800', hovercolor='#ffff00')
btn_single.on_clicked(callback_single)

ax_stop = plt.axes([0.6, 0.05, 0.2, 0.075])
btn_stop = Button(ax_stop, 'Stop', color='#880000', hovercolor='#ff0000')
btn_stop.on_clicked(callback_stop)

# --- CHANNEL VISIBILITY CHECKBOXES ---
# Placed to the right
ax_check = plt.axes([0.82, 0.05, 0.15, 0.12]) # [left, bottom, width, height]
# Initial visibility state
visibility = [True, True, True] 
labels = ['Show CH1', 'Show CH2', 'Show CH3']
check = CheckButtons(ax_check, labels, visibility)

def toggle_channels(label):
    index = labels.index(label)
    visibility[index] = not visibility[index]
    
    # Update visibility immediately
    line1.set_visible(visibility[0])
    line2.set_visible(visibility[1])
    line3.set_visible(visibility[2])
    plt.draw()

check.on_clicked(toggle_channels)

def update(frame):
    try:
        if ser.in_waiting > 0:
            raw_line = ser.readline()
            try:
                decoded_line = raw_line.decode('utf-8').strip()
            except UnicodeDecodeError:
                return line1, line2, line3

            if decoded_line.startswith("MSG:"):
                msg = decoded_line.replace("MSG:", "")
                status_text.set_text(msg)
                status_text.set_color('cyan')
                return line1, line2, line3

            if decoded_line.startswith("METRICS:"):
                parts = decoded_line.split("|DATA:")
                if len(parts) < 2: return line1, line2, line3
                
                # Tag parsing
                tag = "RUN"
                if "|TAG:" in parts[1]:
                    data_part, tag_part = parts[1].split("|TAG:")
                    data_str = data_part
                    tag = tag_part
                else:
                    data_str = parts[1]

                # Metrics parsing
                metrics_str = parts[0].replace("METRICS:", "")
                m_vals = metrics_str.split(',')
                # Format: vpp, freq, period, avg, duty
                vpp = float(m_vals[0])
                freq = float(m_vals[1])
                period = float(m_vals[2])
                v_avg = float(m_vals[3])
                duty = 0
                if len(m_vals) > 4: duty = float(m_vals[4])

                # Data Parsing (De-interleave 3 Channels)
                raw_vals = data_str.split(',')
                ch1_y = []
                ch2_y = []
                ch3_y = []
                
                # Step 3 to grab interleaved data (CH1, CH2, CH3, CH1, CH2, CH3...)
                for i in range(0, len(raw_vals)-2, 3):
                    try:
                        v1 = int(raw_vals[i]) * (MAX_VOLTAGE / ADC_RESOLUTION)
                        v2 = int(raw_vals[i+1]) * (MAX_VOLTAGE / ADC_RESOLUTION)
                        v3 = int(raw_vals[i+2]) * (MAX_VOLTAGE / ADC_RESOLUTION)
                        ch1_y.append(v1)
                        ch2_y.append(v2)
                        ch3_y.append(v3)
                    except ValueError: pass
                
                # Update Plots
                samples = len(ch1_y)
                x_data = range(samples)
                
                # Always update data, visibility is handled by plot settings
                line1.set_data(x_data, ch1_y)
                line2.set_data(x_data, ch2_y)
                line3.set_data(x_data, ch3_y)
                
                ax.set_xlim(0, samples)

                # Update Text
                if tag == "RUN":
                    status_text.set_text("RUNNING")
                    status_text.set_color('#00ff00')
                elif tag == "SINGLE":
                    status_text.set_text("SINGLE CAPTURED")
                    status_text.set_color('#ff0000')

                stats = (
                    f"CH1 Vpp:   {vpp:.2f} V\n"
                    f"CH1 DC:    {v_avg:.2f} V\n"
                    f"CH1 Freq:  {freq:.1f} Hz\n"
                    f"CH1 Period:{period:.2f} ms\n"
                    f"CH1 Duty:  {duty:.1f} %"
                )
                info_text.set_text(stats)
                
    except Exception as e:
        print(f"Error: {e}")

    return line1, line2, line3

ani = animation.FuncAnimation(fig, update, interval=10, blit=False, cache_frame_data=False)
plt.show()