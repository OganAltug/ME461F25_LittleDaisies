import socket
from machine import Pin
import time

# Ensure Wi-Fi is connected before running this script!
# (Assume boot.py or manual setup has run)

# --- Hardware Setup ---
# We'll use the onboard LED for a simple test response
led = Pin('LED', Pin.OUT) 

# --- Web Server Functions ---

def web_page():
    # HTML content for the minimal "game" interface
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Pico W Game</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial; text-align: center; margin: 50px; background: #f0f0f0; }
            .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
            .button { background-color: #4CAF50; color: white; padding: 15px 32px; text-align: center; text-decoration: none; display: inline-block; font-size: 16px; margin: 4px 2px; cursor: pointer; border: none; border-radius: 8px;}
            .status { margin-top: 20px; font-size: 1.2em; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Pico W Web Game Controller</h1>
            <p class="status" id="status">LED Status: OFF</p>
            
            <button class="button" onclick="sendAction('/?led=on')">TURN ON LED</button>
            <button class="button" onclick="sendAction('/?led=off')" style="background-color: #f44336;">TURN OFF LED</button>
            
            <p>Accessing the Pico W at its core.</p>
        </div>

        <script>
            function sendAction(action) {
                // Use AJAX to send a request to the Pico W server
                var xhr = new XMLHttpRequest();
                xhr.open("GET", action, true);
                xhr.send();
                
                // Update status text instantly (for a quick response feel)
                var statusElement = document.getElementById("status");
                if (action.includes('on')) {
                    statusElement.innerHTML = "LED Status: ON (Request Sent)";
                } else {
                    statusElement.innerHTML = "LED Status: OFF (Request Sent)";
                }
            }
        </script>
    </body>
    </html>"""
    return html

# ----------------------------------------------------
# Main Server Loop
# ----------------------------------------------------

# Set up socket connection
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 80)) # Bind to port 80 (standard HTTP port)
    s.listen(5) # Listen for up to 5 concurrent connections
except Exception as e:
    print(f"Socket error: {e}")

print("Web server started on port 80.")

while True:
    try:
        conn, addr = s.accept() # Wait for client connection
        print('Got connection from %s' % str(addr))
        request = conn.recv(1024) # Receive request data
        request = str(request)
        
        # --- Handle Incoming Request ---
        
        # Check if the request contains an LED command
        led_on = request.find('/?led=on')
        led_off = request.find('/?led=off')
        
        if led_on == 6: # '/?led=on' command received
            led.value(1) # Turn LED ON
            print('-> LED ON command processed')
        elif led_off == 6: # '/?led=off' command received
            led.value(0) # Turn LED OFF
            print('-> LED OFF command processed')

        # --- Send Response ---
        
        response = web_page()
        # Send HTTP headers and HTML content
        conn.send('HTTP/1.1 200 OK\n')
        conn.send('Content-Type: text/html\n')
        conn.send('Connection: close\n\n')
        conn.sendall(response)
        conn.close()
        
    except OSError as e:
        conn.close()
        print('Connection closed:', e)
        time.sleep(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        time.sleep(1)