import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Button, CheckButtons, RadioButtons
from matplotlib.patches import Rectangle
import sys

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
fig = plt.figure(figsize=(16, 9)) # Increased height slightly
fig.canvas.manager.set_window_title('Pico Triple Scope + XY Analyzer')
fig.patch.set_facecolor('#333333') 

# --- STATUS TEXT (Global Top) ---
# Placed at the very top center of the window
status_text = fig.text(0.5, 0.96, "WAITING", fontsize=16, color='yellow', 
                       ha='center', va='top', weight='bold')

# --- 1. MAIN TIME DOMAIN PLOT (Center) ---
# Reduced height slightly to 0.65 to make room at the top
ax_main = fig.add_axes([0.22, 0.25, 0.45, 0.65]) 
ax_main.set_facecolor('#1e1e1e')
ax_main.grid(True, color='#444444', linestyle='--')
ax_main.set_ylim(-0.1, MAX_VOLTAGE + 0.2)
ax_main.set_xlim(0,50)
ax_main.set_ylabel("Voltage (V)", color='white')
ax_main.set_xlabel("Sample Index", color='white')
ax_main.set_title("Time Domain", color='white', weight='bold')
ax_main.tick_params(colors='white')

# Lines
line1, = ax_main.plot([], [], color='#00ff00', linewidth=1.5, label='CH1')
line2, = ax_main.plot([], [], color='#00ffff', linewidth=1.5, label='CH2')
line3, = ax_main.plot([], [], color='#ff3333', linewidth=1.5, label='CH3')
ax_main.legend(loc='upper right')

# --- 2. XY PLOT (Right) ---
# Adjusted position to align with new main plot height
ax_xy = fig.add_axes([0.72, 0.50, 0.25, 0.40]) 
ax_xy.set_facecolor('#1e1e1e')
ax_xy.grid(True, color='#444444', linestyle='--')
ax_xy.set_xlim(-0.1, MAX_VOLTAGE + 0.1)
ax_xy.set_ylim(-0.1, MAX_VOLTAGE + 0.1)
ax_xy.set_xlabel("X Input (V)", color='white')
ax_xy.set_ylabel("Y Input (V)", color='white')
ax_xy.set_title("XY Plot (Lissajous)", color='white', weight='bold')
ax_xy.tick_params(colors='white')

line_xy, = ax_xy.plot([], [], color='#ff00ff', linewidth=1.5, alpha=0.8)

# --- 3. XY CONTROLS (Right Bottom) ---
rect_ctrl = Rectangle((0.72, 0.15), 0.25, 0.28, transform=fig.transFigure, 
                      facecolor='white', edgecolor='#555555')
fig.patches.append(rect_ctrl)

fig.text(0.73, 0.38, "X-Axis Source:", color='black', weight='bold', fontsize=11)
fig.text(0.85, 0.38, "Y-Axis Source:", color='black', weight='bold', fontsize=11)

# Radio Buttons
ax_radio_x = fig.add_axes([0.73, 0.20, 0.15, 0.15], facecolor='white')
radio_x = RadioButtons(ax_radio_x, ('Channel 1', 'Channel 2', 'Channel 3'), activecolor='black')

ax_radio_y = fig.add_axes([0.86, 0.20, 0.15, 0.15], facecolor='white')
radio_y = RadioButtons(ax_radio_y, ('Channel 1', 'Channel 2', 'Channel 3'), activecolor='black')

# Force text visibility
for label in radio_x.labels: 
    label.set_color('black')
    label.set_fontsize(10)
    label.set_fontweight('normal')
    label.set_clip_on(False) 

for label in radio_y.labels: 
    label.set_color('black')
    label.set_fontsize(10)
    label.set_fontweight('normal')
    label.set_clip_on(False) 

xy_sel = {'x': 0, 'y': 1} 

def change_x(label):
    if label == 'Channel 1': xy_sel['x'] = 0
    elif label == 'Channel 2': xy_sel['x'] = 1
    elif label == 'Channel 3': xy_sel['x'] = 2

def change_y(label):
    if label == 'Channel 1': xy_sel['y'] = 0
    elif label == 'Channel 2': xy_sel['y'] = 1
    elif label == 'Channel 3': xy_sel['y'] = 2

radio_x.on_clicked(change_x)
radio_y.on_clicked(change_y)
radio_y.set_active(1) 

# --- 4. STATISTICS PANEL (Left) ---
box_left = 0.02
box_width = 0.16   
box_height = 0.18 
box_bg_color = '#d9d9d9' 

# CH1 Stats
rect1 = Rectangle((box_left, 0.72), box_width, box_height, transform=fig.transFigure, 
                  facecolor=box_bg_color, edgecolor='#00aa00', linewidth=2)
fig.patches.append(rect1)
fig.text(box_left + 0.01, 0.86, "CH1 STATS", transform=fig.transFigure, 
         color='#009900', weight='bold', fontsize=11)
text_ch1 = fig.text(box_left + 0.01, 0.73, "Waiting...", transform=fig.transFigure,
                    color='black', family='monospace', fontsize=8, verticalalignment='bottom')

# CH2 Stats
rect2 = Rectangle((box_left, 0.47), box_width, box_height, transform=fig.transFigure, 
                  facecolor=box_bg_color, edgecolor='#00aaaa', linewidth=2)
fig.patches.append(rect2)
fig.text(box_left + 0.01, 0.61, "CH2 STATS", transform=fig.transFigure, 
         color='#008888', weight='bold', fontsize=11)
text_ch2 = fig.text(box_left + 0.01, 0.48, "Waiting...", transform=fig.transFigure,
                    color='black', family='monospace', fontsize=8, verticalalignment='bottom')

# CH3 Stats
rect3 = Rectangle((box_left, 0.22), box_width, box_height, transform=fig.transFigure, 
                  facecolor=box_bg_color, edgecolor='#cc0000', linewidth=2)
fig.patches.append(rect3)
fig.text(box_left + 0.01, 0.36, "CH3 STATS", transform=fig.transFigure, 
         color='#cc0000', weight='bold', fontsize=11)
text_ch3 = fig.text(box_left + 0.01, 0.23, "Waiting...", transform=fig.transFigure,
                    color='black', family='monospace', fontsize=8, verticalalignment='bottom')

# --- 5. BOTTOM CONTROLS ---
def send_command(cmd):
    try: ser.write(cmd.encode())
    except: pass

def callback_run(event): send_command('R')
def callback_single(event): send_command('S')
def callback_stop(event): send_command('H')

ax_run = plt.axes([0.25, 0.05, 0.1, 0.075])
btn_run = Button(ax_run, 'Run', color='#008800', hovercolor='#00ff00')
btn_run.on_clicked(callback_run)

ax_single = plt.axes([0.37, 0.05, 0.1, 0.075])
btn_single = Button(ax_single, 'Single', color='#aa8800', hovercolor='#ffff00')
btn_single.on_clicked(callback_single)

ax_stop = plt.axes([0.49, 0.05, 0.1, 0.075])
btn_stop = Button(ax_stop, 'Stop', color='#880000', hovercolor='#ff0000')
btn_stop.on_clicked(callback_stop)

ax_check = plt.axes([0.62, 0.05, 0.1, 0.1]) 
visibility = [True, True, True] 
labels = ['CH1', 'CH2', 'CH3']
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
    return (f"Vmax:   {vals[0]:.2f} V\n"
            f"Vmin:   {vals[1]:.2f} V\n"
            f"Vpp:    {vals[2]:.2f} V\n"
            f"DC:     {vals[5]:.2f} V\n"
            f"Freq:   {vals[3]:.1f} Hz\n"
            f"Period: {vals[4]:.2f} ms\n"
            f"Duty:   {vals[6]:.1f} %")

# --- SOFTWARE ALIGNMENT ---
def align_trace_independent(data):
    if not data: return data
    v_min = min(data)
    v_max = max(data)
    if (v_max - v_min) < 0.2: return data
    mid = (v_min + v_max) / 2
    shift_index = 0
    for i in range(len(data) - 1):
        if data[i] < mid and data[i+1] >= mid:
            shift_index = i
            break
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
                return line1, line2, line3, line_xy

            if decoded_line.startswith("MSG:"):
                msg = decoded_line.replace("MSG:", "")
                status_text.set_text(msg)
                
                # Dynamic Color for Status
                if "RUN" in msg: status_text.set_color('#00ff00')
                elif "SINGLE" in msg: status_text.set_color('#ff0000')
                elif "STOPPED" in msg: status_text.set_color('yellow')
                elif "ARMED" in msg: status_text.set_color('cyan')
                
                return line1, line2, line3, line_xy

            if decoded_line.startswith("METRICS:"):
                parts = decoded_line.split("|DATA:")
                if len(parts) < 2: return line1, line2, line3, line_xy
                
                # Stats
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
                
                # Update Time Domain
                ch1_aligned = align_trace_independent(ch1_y)
                ch2_aligned = align_trace_independent(ch2_y)
                ch3_aligned = align_trace_independent(ch3_y)
                
                samples = len(ch1_aligned)
                x_data = range(samples)
                
                line1.set_data(x_data, ch1_aligned)
                line2.set_data(x_data, ch2_aligned)
                line3.set_data(x_data, ch3_aligned)
                ax_main.set_xlim(0, samples)

                # Update XY Plot
                data_map = [ch1_y, ch2_y, ch3_y]
                x_idx = xy_sel['x']
                y_idx = xy_sel['y']
                if len(data_map[x_idx]) > 0 and len(data_map[y_idx]) > 0:
                    line_xy.set_data(data_map[x_idx], data_map[y_idx])

                # Status Check
                if tag == "RUN":
                    status_text.set_text("RUNNING")
                    status_text.set_color('#00ff00')
                elif tag == "SINGLE":
                    status_text.set_text("SINGLE CAPTURED")
                    status_text.set_color('#ff0000')

    except Exception as e:
        print(f"Error: {e}")

    return line1, line2, line3, line_xy

ani = animation.FuncAnimation(fig, update, interval=10, blit=False, cache_frame_data=False)
plt.show()