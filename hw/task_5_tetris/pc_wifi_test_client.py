# pc_wifi_test_client.py
# A minimal client to test WiFi connectivity.
# Run this on your PC.

import socket

# --- CONFIGURATION ---
# You will be prompted for this.
# Look at the Thonny console output from the Pico script.
SERVER_PORT = 8080
# ---------------------

def run_client():
    pico_ip = input("Enter the Pico's IP Address: ")
    if not pico_ip:
        print("No IP entered. Exiting.")
        return

    print(f"Attempting to connect to {pico_ip}:{SERVER_PORT}...")

    # Use a try-with-resources block to auto-close the socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # Set a timeout for the connection attempt
            s.settimeout(5.0) 
            
            # 1. Try to connect
            s.connect((pico_ip, SERVER_PORT))
            
            # --- IF YOU GET HERE, IT WORKED! ---
            print("\n*** SUCCESS! Connection established. ***\n")
            print("You can now send messages. Type 'quit' to exit.")
            
            s.settimeout(10.0) # Longer timeout for receiving replies

            while True:
                # 2. Send a message
                message = input("PC > ")
                if message.lower() == 'quit':
                    break
                
                s.sendall(message.encode('utf-8'))
                
                # 3. Wait for the reply
                data = s.recv(1024)
                reply = data.decode('utf-8')
                print(f"Pico > {reply}")

    except socket.timeout:
        print("\n*** TEST FAILED: Connection timed out. ***")
        print("This is the same error as before. It means:")
        print("1. Your PC's firewall is blocking the connection.")
        print("2. Your WiFi router has 'AP Isolation' enabled, blocking devices.")
        print("3. The IP address was wrong.")
        
    except ConnectionRefusedError:
        print("\n*** TEST FAILED: Connection refused. ***")
        print("This means the Pico's IP was correct, but the Pico script")
        print("was NOT running or had already crashed.")
        
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

    print("Connection closed.")

if __name__ == "__main__":
    run_client()