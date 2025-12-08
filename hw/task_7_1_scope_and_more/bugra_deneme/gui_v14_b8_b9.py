import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Button, CheckButtons
from matplotlib.patches import Rectangle
import sys
import numpy as np # Used for cleaner array handling if desired, but sticking to list for compatibility

# --- CONFIGURATION ---
SERIAL_PORT = '/dev/ttyACM0' # <--- CHECK THIS
BAUD_RATE = 115200
MAX_VOLTAGE = 3.3
ADC_RESOLUTION = 65535
TOTAL_SAMPLES = 1200 

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
fig, ax = plt.subplots(figsize=(12, 8))
plt.subplots_adjust(left=0.25, bottom=0.25) 

fig.canvas.manager.set_window_title('Pico Triple Scope')
ax.set_facecolor('#1e1e1e')
ax.grid(True, color='#444444', linestyle='--')
ax.set_ylim(-0.1, MAX_VOLTAGE + 0.2)
ax.set_ylabel("Voltage (V)")
ax.set_xlabel("Sample Index")

# Lines
line1, = ax.plot([], [], color='#00ff00', linewidth=1.5, label='CH1')
line2, = ax.plot([], [], color='#00ffff', linewidth=1.5, label='CH2')
line3, = ax.plot([], [], color='#ff3333', linewidth=1.5, label='CH3')
ax.legend(loc='upper right')

# --- STATS BOXES ---
box_left = 0.02
box_width = 0.16   
box_height = 0.18 
box_bg_color = '#d9d9d9' 

# CH1
rect1 = Rectangle((box_left, 0.72), box_width, box_height, transform=fig.transFigure, 
                  facecolor=box_bg_color, edgecolor='#00aa00', linewidth=2)
fig.patches.append(rect1)
fig.text(box_left + 0.01, 0.86, "CH1 STATS", transform=fig.transFigure, 
         color='#009900', weight='bold', fontsize=11)
text_ch1 = fig.text(box_left + 0.01, 0.74, "Waiting...", transform=fig.transFigure,
                    color='black', family='monospace', fontsize=9, verticalalignment='bottom')

# CH2
rect2 = Rectangle((box_left, 0.47), box_width, box_height, transform=fig.transFigure, 
                  facecolor=box_bg_color, edgecolor='#00aaaa', linewidth=2)
fig.patches.append(rect2)
fig.text(box_left + 0.01, 0.61, "CH2 STATS", transform=fig.transFigure, 
         color='#008888', weight='bold', fontsize=11)
text_ch2 = fig.text(box_left + 0.01, 0.49, "Waiting...", transform=fig.transFigure,
                    color='black', family='monospace', fontsize=9, verticalalignment='bottom')

# CH3
rect3 = Rectangle((box_left, 0.22), box_width, box_height, transform=fig.transFigure, 
                  facecolor=box_bg_color, edgecolor='#cc0000', linewidth=2)
fig.patches.append(rect3)
fig.text(box_left + 0.01, 0.36, "CH3 STATS", transform=fig.transFigure, 
         color='#cc0000', weight='bold', fontsize=11)
text_ch3 = fig.text(box_left + 0.01, 0.24, "Waiting...", transform=fig.transFigure,
                    color='black', family='monospace', fontsize=9, verticalalignment='bottom')

status_text = ax.text(0.5, 1.05, "WAITING", transform=ax.transAxes,
                      fontsize=14, color='yellow', ha='center', weight='bold')

# --- CONTROLS ---
def send_command(cmd):
    try: ser.write(cmd.encode())
    except: pass

def callback_run(event): send_command('R')
def callback_single(event): send_command('S')
def callback_stop(event): send_command('H')

ax_run = plt.axes([0.3, 0.05, 0.15, 0.075])
btn_run = Button(ax_run, 'Run', color='#008800', hovercolor='#00ff00')
btn_run.on_clicked(callback_run)

ax_single = plt.axes([0.47, 0.05, 0.15, 0.075])
btn_single = Button(ax_single, 'Single', color='#aa8800', hovercolor='#ffff00')
btn_single.on_clicked(callback_single)

ax_stop = plt.axes([0.64, 0.05, 0.15, 0.075])
btn_stop = Button(ax_stop, 'Stop', color='#880000', hovercolor='#ff0000')
btn_stop.on_clicked(callback_stop)

ax_check = plt.axes([0.82, 0.05, 0.15, 0.12]) 
visibility = [True, True, True] 
labels = ['Show CH1', 'Show CH2', 'Show CH3']
check = CheckButtons(ax_check, labels, visibility)

def toggle_channels(label):
    index = labels.index(label)
    visibility[index] = not visibility[index]
    line1.set_visible(visibility[0])
    line2.set_visible(visibility[1])
    line3.set_visible(visibility[2])
    plt.draw()

check.on_clicked(toggle_channels)

def format_stats(vals):
    return (f"Vpp:    {vals[0]:.2f} V\n"
            f"DC:     {vals[3]:.2f} V\n"
            f"Freq:   {vals[1]:.1f} Hz\n"
            f"Period: {vals[2]:.2f} ms\n"
            f"Duty:   {vals[4]:.1f} %")

# --- SOFTWARE ALIGNMENT HELPER ---
def align_trace_independent(data):
    """
    Finds the first rising edge crossing the midpoint and shifts 
    the array so that point is at index 0.
    This makes every channel look stable independently.
    """
    if not data: return data
    v_min = min(data)
    v_max = max(data)
    
    # If signal is too weak (noise), don't shift
    if (v_max - v_min) < 0.2: 
        return data

    mid = (v_min + v_max) / 2
    
    # Find rising edge
    # We look for a transition from below mid to above mid
    shift_index = 0
    for i in range(len(data) - 1):
        if data[i] < mid and data[i+1] >= mid:
            shift_index = i
            break
            
    # Rotate list: move start to shift_index
    # Note: This technically rotates phase, but ensures visual stability
    if shift_index > 0:
        return data[shift_index:] + data[:shift_index]
    return data

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
                return line1, line2, line3

            if decoded_line.startswith("METRICS:"):
                parts = decoded_line.split("|DATA:")
                if len(parts) < 2: return line1, line2, line3
                
                # Metrics
                metrics_str = parts[0].replace("METRICS:", "")
                channels_metrics = metrics_str.split(';')
                
                if len(channels_metrics) == 3:
                    m1 = [float(x) for x in channels_metrics[0].split(',')]
                    text_ch1.set_text(format_stats(m1))
                    m2 = [float(x) for x in channels_metrics[1].split(',')]
                    text_ch2.set_text(format_stats(m2))
                    m3 = [float(x) for x in channels_metrics[2].split(',')]
                    text_ch3.set_text(format_stats(m3))

                # Data
                if "|TAG:" in parts[1]:
                    data_str, tag = parts[1].split("|TAG:")
                else:
                    data_str, tag = parts[1], "RUN"

                raw_vals = data_str.split(',')
                ch1_y = []
                ch2_y = []
                ch3_y = []
                
                for i in range(0, len(raw_vals)-2, 3):
                    try:
                        v1 = int(raw_vals[i]) * (MAX_VOLTAGE / ADC_RESOLUTION)
                        v2 = int(raw_vals[i+1]) * (MAX_VOLTAGE / ADC_RESOLUTION)
                        v3 = int(raw_vals[i+2]) * (MAX_VOLTAGE / ADC_RESOLUTION)
                        ch1_y.append(v1)
                        ch2_y.append(v2)
                        ch3_y.append(v3)
                    except ValueError: pass
                
                # --- APPLY INDEPENDENT ALIGNMENT ---
                # This ensures CH2 doesn't slip even if CH1 triggered the hardware
                ch1_aligned = align_trace_independent(ch1_y)
                ch2_aligned = align_trace_independent(ch2_y)
                ch3_aligned = align_trace_independent(ch3_y)
                
                samples = len(ch1_aligned)
                x_data = range(samples)
                
                line1.set_data(x_data, ch1_aligned)
                line2.set_data(x_data, ch2_aligned)
                line3.set_data(x_data, ch3_aligned)
                ax.set_xlim(0, samples)

                if tag == "RUN":
                    status_text.set_text("RUNNING")
                    status_text.set_color('#00ff00')
                elif tag == "SINGLE":
                    status_text.set_text("SINGLE CAPTURED")
                    status_text.set_color('#ff0000')

    except Exception as e:
        print(f"Error: {e}")

    return line1, line2, line3

ani = animation.FuncAnimation(fig, update, interval=10, blit=False, cache_frame_data=False)
plt.show()