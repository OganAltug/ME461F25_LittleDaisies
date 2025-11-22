import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import sys

# --- CONFIGURATION ---
# CHANGE THIS TO YOUR PORT
SERIAL_PORT = '/dev/ttyACM0' 
BAUD_RATE = 115200
MAX_VOLTAGE = 3.3
ADC_RESOLUTION = 4095
SAMPLES = 1000

# --- CONNECTION ---
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    # LINUX FIX: Assert DTR/RTS to wake up the CDC interface
    ser.dtr = True 
    ser.rts = True
    print(f"Connected to {SERIAL_PORT}...")
except Exception as e:
    print(f"Error connecting to {SERIAL_PORT}: {e}")
    print("Check permissions (try 'sudo') or correct port name.")
    sys.exit()

# --- PLOT SETUP ---
fig, ax = plt.subplots(figsize=(10, 6))
fig.canvas.manager.set_window_title('Pico Oscilloscope')
ax.set_facecolor('#1e1e1e')
ax.grid(True, color='#444444', linestyle='--')
ax.set_ylim(-0.1, MAX_VOLTAGE + 0.2)
ax.set_xlim(0, SAMPLES)
ax.set_ylabel("Voltage (V)")
ax.set_xlabel("Sample Index")

line, = ax.plot([], [], color='#00ff00', linewidth=1.2)

info_text = ax.text(0.02, 0.95, "Waiting for Data...", transform=ax.transAxes,
                    fontsize=11, color='#00ff00', verticalalignment='top',
                    bbox=dict(boxstyle="round", facecolor='#111111', alpha=0.8))

def update(frame):
    try:
        # Only read if data is actually waiting
        if ser.in_waiting > 0:
            raw_line = ser.readline()
            
            try:
                decoded_line = raw_line.decode('utf-8').strip()
            except UnicodeDecodeError:
                return line, info_text

            if decoded_line.startswith("METRICS:"):
                parts = decoded_line.split("|DATA:")
                if len(parts) != 2: return line, info_text
                
                metrics_str, data_str = parts
                
                # 1. Parse Metrics
                m_vals = metrics_str.replace("METRICS:", "").split(',')
                vpp = float(m_vals[0])
                freq = float(m_vals[1])
                duty = float(m_vals[2])
                vavg = float(m_vals[3])
                
                # 2. Parse Data (0-4095 -> 0-3.3V)
                y_data = [int(val) * (MAX_VOLTAGE / ADC_RESOLUTION) for val in data_str.split(',')]
                
                # 3. Update GUI
                line.set_data(range(len(y_data)), y_data)
                
                status_str = (
                    f"Freq: {freq:.1f} Hz\n"
                    f"Duty: {duty:.1f} %\n"
                    f"Vpp:  {vpp:.2f} V\n"
                    f"Avg:  {vavg:.2f} V"
                )
                info_text.set_text(status_str)
                
    except Exception as e:
        print(f"Error: {e}")

    return line, info_text

ani = animation.FuncAnimation(fig, update, interval=10, blit=True, cache_frame_data=False)
plt.show()
ser.close()