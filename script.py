import os
import signal
import sys
import termios
import atexit
import subprocess
import shutil
import re

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
def cleanup():
    print("Exiting cleanly.")
    # Perform cleanup operations here
    if os.path.exists("eqy_configuration_updated"):
        shutil.rmtree("eqy_configuration_updated")  # Recursively remove the 'eqy_configuration_updated' directory and its contents

def signal_handler(signum, frame):
    print(f"Caught signal {signum}, exiting...")
    sys.exit(1)

# Register cleanup function and signal handler
atexit.register(cleanup)
for sig in [signal.SIGABRT, signal.SIGINT, signal.SIGTERM]:
    signal.signal(sig, signal_handler)

# Function to execute EQY commands
def execute_eqy_commands(verilog1_file, verilog2_file, module_name1, module_name2, eqy_config_file):
    # Copy Verilog files to a temporary directory to avoid modifying the original files
    tmp_dir = "tmp"
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)
    shutil.copy(verilog1_file, tmp_dir)
    shutil.copy(verilog2_file, tmp_dir)

    # Update the EQY configuration file to use the copied Verilog files and module names
    with open(eqy_config_file, "r") as f:
        eqy_config_content = f.read()
    eqy_config_content = eqy_config_content.replace("{MODULE_NAME1}", module_name1)
    eqy_config_content = eqy_config_content.replace("{MODULE_NAME2}", module_name2)
    eqy_config_content = eqy_config_content.replace("<ORIGINAL_VERILOG_FILE>", f"{tmp_dir}/{os.path.basename(verilog1_file)}")
    eqy_config_content = eqy_config_content.replace("<MODIFIED_VERILOG_FILE>", f"{tmp_dir}/{os.path.basename(verilog2_file)}")
    # Write the updated EQY configuration file
    updated_eqy_config_file = f"{tmp_dir}/eqy_configuration_updated.eqy"
    with open(updated_eqy_config_file, "w") as f:
        f.write(eqy_config_content)

    # Execute equivalence checking using EQY
    try:
        subprocess.run(["eqy", updated_eqy_config_file], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing EQY command: {e}")
        sys.exit(1)
    finally:
        # Clean up temporary directory
        shutil.rmtree(tmp_dir)

# Function to extract module name from a Verilog file


def extract_module_name(verilog_file):
    module_pattern = re.compile(r"^\s*module\s+(\w+)\s*\(")
    with open(verilog_file, "r") as f:
        for line in f:
            match = module_pattern.match(line)
            if match:
                module_name = match.group(1)
                print(f"Module Name: {module_name}")  # Debug print statement
                return module_name  # Return the module name once found

# Main entry point
def main():
    # Get all Verilog files in the current directory
    verilog_files = [f for f in os.listdir() if f.endswith(".v")]

    # Check if there are at least two Verilog files
    if len(verilog_files) < 2:
        print("Error: At least two Verilog files are required in the current directory.")
        sys.exit(1)

    # Take the first two Verilog files found
    verilog1_file = verilog_files[0]
    verilog2_file = verilog_files[1]

    # Extract module names from the Verilog files
    module_name1 = extract_module_name(verilog1_file)
    module_name2 = extract_module_name(verilog2_file)
    
    print(f"Module Name 1: {module_name1}")
    print(f"Module Name 2: {module_name2}")

    # Define the path to the EQY configuration file
    eqy_config_file = "/home/syedowais/conversion-to-TLV/equivalence.eqy"

    # Execute equivalence checking using EQY
    execute_eqy_commands(verilog1_file, verilog2_file, module_name1, module_name2, eqy_config_file)
    execute_eqy_commands(verilog2_file, verilog1_file, module_name2, module_name1, eqy_config_file)  # For bidirectional equivalence checking

if __name__ == "__main__":
    main()
