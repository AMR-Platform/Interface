#!/usr/bin/env python3
# jetson_serial_bridge.py
#
# Receives UDP commands and forwards them to ATmega32u4 via serial

import socket
import serial
import time
import signal
import sys

# Configuration
UDP_IP = "0.0.0.0"  # Listen on all network interfaces
UDP_PORT = 5005
SERIAL_PORT = "/dev/ttyACM0"  # Default for Arduino/ATmega32u4, adjust if needed
SERIAL_BAUD = 9600  # Set to match your ATmega32u4 baud rate

# Valid commands to forward to serial
VALID_COMMANDS = {'F', 'B', 'L', 'R', 'S'}

# Initialize UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
sock.settimeout(0.1)  # Non-blocking with short timeout

# Initialize serial connection
ser = None
try:
    ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=1)
    print(f"Connected to serial port {SERIAL_PORT} at {SERIAL_BAUD} baud")
    time.sleep(2)  # Give serial connection time to stabilize
except Exception as e:
    print(f"Error opening serial port: {e}")
    sys.exit(1)

# Track last command to avoid sending duplicates
last_command = None

# Handle graceful shutdown
def signal_handler(sig, frame):
    print("\nClosing connections...")
    if ser and ser.is_open:
        # Send stop command before exiting
        ser.write(b'S\n')
        ser.close()
    sock.close()
    print("Exited cleanly")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

print(f"UDP listener started on port {UDP_PORT}")
print("Waiting for commands (F/B/L/R/S)...")

# Main loop
while True:
    try:
        # Try to receive UDP data
        data, addr = sock.recvfrom(1024)
        command = data.decode().strip()
        print(command)
        
        # Only forward valid commands
        if command in VALID_COMMANDS:
            # Only send if it's different from the last command (optional)
            # Comment out this if block if you want to send every command
            ser.write(f"{command}\n".encode())
        else:
            print(f"Ignoring invalid command: {command}")
            
    except socket.timeout:
        # No data received in timeout period, just continue
        pass
    except serial.SerialException as e:
        print(f"Serial error: {e}")
        # Try to reconnect
        try:
            if ser and ser.is_open:
                ser.close()
            time.sleep(1)
            ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=1)
            print("Serial reconnected")
        except:
            print("Failed to reconnect to serial")
    except Exception as e:
        print(f"Error: {e}")
