import os
import signal
import sys
import termios
import atexit
import json
from select import select
import subprocess
import shutil

# Define functions for setting terminal modes and getting user input
def set_raw_mode(fd):
    attrs = termios.tcgetattr(fd)  # get current attributes
    attrs[3] = attrs[3] & ~termios.ICANON  # clear ICANON flag
    termios.tcsetattr(fd, termios.TCSANOW, attrs)  # set new attributes

def set_cooked_mode(fd):
    attrs = termios.tcgetattr(fd)  # get current attributes
    attrs[3] = attrs[3] | termios.ICANON  # set ICANON flag
    termios.tcsetattr(fd, termios.TCSANOW, attrs)  # set new attributes

def getch():
    try:
        set_raw_mode(sys.stdin.fileno())  # Set the terminal to raw mode
        [i], _, _ = select([sys.stdin.fileno()], [], [], None)  # Wait for input to be available
        ch = sys.stdin.read(1)  # Read a single character
    finally:
        set_cooked_mode(sys.stdin.fileno())  # Restore the terminal settings
    return ch

# Define functions for cleanup and signal handling


# Define functions for cleanup and signal handling
def cleanup():
    print("Exiting cleanly.")
    # Perform cleanup operations here
    if os.path.exists("aliases"):
        shutil.rmtree("aliases")  # Recursively remove the 'aliases' directory and its contents


def signal_handler(signum, frame):
    print(f"Caught signal {signum}, exiting...")
    sys.exit(1)

# Register cleanup function and signal handler
atexit.register(cleanup)
for sig in [signal.SIGABRT, signal.SIGINT, signal.SIGTERM]:
    signal.signal(sig, signal_handler)

# Function to execute eqy commands
def execute_eqy_commands():
    eqy_config_file = "/home/syedowais/conversion-to-TLV/eqy/aliases.eqy"  # Update this with the path to your eqy configuration file
    try:
        subprocess.run(["eqy", eqy_config_file], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing eqy command: {e}")
        sys.exit(1)

# Main entry point
def main():
    # Initialize state, parse command-line args, etc.

    # Read and prepare the first design
    # Placeholder for executing commands to read and prepare design1.v

    # Read and prepare the second design
    # Placeholder for executing commands to read and prepare design2.v

    # Execute equivalence checking using eqy
    execute_eqy_commands()

if __name__ == "__main__":
    main()
