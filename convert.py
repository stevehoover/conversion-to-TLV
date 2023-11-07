# A script for refactoring a Verilog module, then converting it to TL-Verilog.
# The refactoring steps are performed by an LLM such as ChatGPT-4 via its API.
# Manual refactoring is also possible. All refactoring steps are formally verified using SymbiYosys.

# Usage:
# python3 convert.py
#   This begins or continues the conversion process for the only *.v file in the current directory.

# This script works with these files:
#  - <module_name>_orig.v: The trusted Verilog module to convert. This is the original file for the current conversion step.
#  - <module_name>.v: The current refactored/modified candidate Verilog module, against which FEV will be run. This is updated by the LLM.
#                     and/or human-modified.
#  - prompt.md: The prompt to be sent to the LLM API.
# Additionally, these files may be created in the process:
#  - prompt_id.txt: A file containing the ID number of the prompt for this step. (The actual prompt may have been modified by the human.)
#  - <module_name>_prep.v: The file sent to the LLM API.
#  - <module_name>_[gpt4|claude2].v: The LLM output file.
#
# Additionally, a history of all refactoring steps is stored in history/#, where "#" is the "change number". This includes:
#   - history/#/<module_name>.v: The refactored file at each step.
#   - history/#/prompt.json: The prompt and metadata sent to the LLM API for each step.
#   - history/#/prompt_id.txt: The ID of the prompt used for this refactoring step. (The actual prompt may have been modified by the human.)
# Although Git naturally captures a history, it may be desirable to capture this folder in Git, simply for convenience, since it may be desirable to
# easily examine file differences or to rework the conversion steps after the fact.
#
# The history may also contain candidate modifications that were rejected. These include candidates that were:
#   - Abandoned: A file modified by a human, but never tested by FEV.
#   - Failed: A file modified by ChatGPT-4, but failed FEV.
#   - Passed: A file that passed FEV, but was not accepted.
# These are captured as:
#   - history/#/reject_#/<module_name>_prep.v: (opt) Captures modifications made by a human, if any, prior to LLM modifications.
#   - history/#/reject_#/<module_name>_[gpt4|claude2].v: (opt) Captures modifications made by the LLM, if any.
#   - history/#?/reject_#/<module_name>.v: The final candidate, which may be a symlink to the LLM .v file if the LLM provides the candidate directly
#                                   without human modifications.
#   - history/#/#_prompt.json: The prompt and metadata sent to the LLM API.
#   - history/#/reject_#/[abandoned|failed|passed]
# The "reject_#" directory provides a sequential "candidate number" for each rejected candidate.
#
# With each successful and accepted refactoring step, the modified module is copied to the original
# module and into the history along with the prompt (if any). The modified module is not deleted, so that it may be subsequently modified by a human.
#
# With each rejected refactoring step, a new candidate is captured under a new candidate number under the next history number directory.
#
# prompts/ contains the default prompts used for refactoring steps as:
#   - prompts/#.md: The prompt text.
#   - prompts/#_README.md: A description of the refactoring step.
#
# When launched, this script first determines the current state of the conversions process. This state is:
#   - The current/next change number, which is the number of the current refactoring step. This is the next history/# or the latest one if
#     it does not contain a <module_name>.v.
#   - The current/next candidate number, which is the next history/#/#.
#   - The current/next prompt ID, which is the ID of the prompt for the current refactoring step. This is the next prompt ID following the
#     most recent that can be found in history/#/.
#
# This is a command-line utility which prompts the user for input. Edits to <module_name>.v and/or prompt.md can be made while input is pending.
# It is suggested to have <module_name>.v and prompt.md open in an editor and in a diff utility, such as meld, while running this script. Users
# must be careful to save files before responding to prompts.
#
# To begin each step, the user is given instructions and prompted for input.
# The user makes edits and enters commands until a candidate is accepted or rejected, and the process repeats.

import os
import subprocess
from pynput import keyboard


#############
# Constants #
#############

llm = "gpt4"  # The LLM to use. "gpt4", "claude2", etc.


####################
# Helper functions #
####################

# Report a usage message.
def usage():
  print("Usage: python3 convert.py")
  print("  Call from a directory containing a single Verilog file to convert.")
  os.exit(0)

# Determine if a filename has a Verilog/SystemVerilog extension.
def is_verilog(filename):
  return filename.endswith(".v") or filename.endswith(".sv")

# Run SymbiYosys.
def run_sby():
  subprocess.run(["sby", "-f", "fev.sby"])

# Functions that determine the state of the refactoring step based on the state of the files.
def llm_passed():
  return os.path.exists(llm_verilog_file_name)

def fev_passed():
  return os.path.exists("fev_prove/PASS") and os.system("diff " + module_name + ".v fev_prove/src/" + module_name + ".v") == 0

# Are there pending changes?
def pending_changes():
  return os.system("diff " + working_verilog_file_name + " " + orig_verilog_file_name) != 0 or llm_run() or fev_run()

# Print the main user prompt.
def print_prompt():
  print("The next refactoring step (" + change_number + ") for the LLM uses prompt " + prompt_id + ":")
  # Output the README for the current prompt ID, indented by 5 spaces.
  print("     " + open("prompts/" + prompt_id + "_README.md").read().replace("\n", "\n     "))
  print("  ")
  print("  Make edits and enter command characters until a candidate is accepted or rejected. Generally, the sequence is:")
  print("    - Make any desired manual edits to " + working_verilog_file_name + " and/or prompt.md.")
  print("    - l: (optional) Run the LLM step. (If this fails, make further manual edits and try again.)")
  print("    - Make any desired manual edits to " + module_name + "_mod.v. (You may use \"f\" to run FEV first.)")
  print("    - f: Run FEV. (If this fails, make further manual Verilog edits and try again.)")
  print("    - y: Accept this candidate.")
  print("  (At any time: use \"n\" to undo changes; \"h\" for help; \"x\" to exit.)")
  print("  ")
  print("  Enter one of the following commands:")
  print("    l: LLM. Run this refactoring step in ChatGPT-4/Claude2 (if LLM not already run).")
  print("    f: Run FEV on the current candidate.")
  print("    y: Yes. Accept this candidate (if FEV already run and passed).")
  print("    n: No. Reject this candidate; checkpoint your work in /history/#/reject_#/* and revert to the beginning of this step. (Or do nothing if no changes were made.)")
  print("    s: Skip this LLM prompt (no changes are needed for this step) (if FEV not already run).")
  print("    h: Help. Repeat this message.")
  print("    x: Exit.")
  print("> ")

####################
# Main entry point #
####################

# Find the Verilog file to convert, ending in ".v" or ".sv".
files = [f for f in os.listdir(".") if is_verilog(f)]
if len(files) != 1:
  print("Error: There must be exactly one Verilog file in the current directory.")
  usage()
working_verilog_file_name = files[0]
module_name = working_verilog_file_name.split(".")[0]
orig_verilog_file_name = module_name + "_orig.v"
llm_verilog_file_name = module_name + "_" + llm + ".v"
pre_llm_verilog_file_name = module_name + "_prep.v"

# Set the environment variables for FEV.
os.environ['MODULE_NAME'] = module_name
os.environ['ORIGINAL_FILE'] = working_verilog_file_name
os.environ['MODIFIED_FILE'] = orig_verilog_file_name



####################
# Initialize state #
####################

# Initialize the conversion job if the history directory does not exist.
if not os.path.exists("history"):
  os.mkdir("history")
  # Copy the original file into history/0.
  os.mkdir("history/0")
  os.system("cp " + working_verilog_file_name + " history/0/" + working_verilog_file_name)

# Current state variables.
change_number = 0  # The current change number.
candidate_number = 0  # The current candidate number.
prompt_id = 0  # The current prompt ID.

# Determine the current state of the conversion process.
# Find the current change number.
for change in os.listdir("history"):
  change_number = max(change_number, int(change))
# Find the current candidate number.
for file in os.listdir("history/" + change):
  if is_verilog(file):
  candidate_number = max(candidate_number, int(candidate.split("_")[0]))
# Get the prompt ID from the most recent prompt_id.txt file. Look back through the history directories until/if one is found.
cn = change_number
while cn >= 0 and prompt_id == 0:
  if os.path.exists("history/" + str(cn) + "/prompt_id.txt"):
    prompt_id = int(open("history/" + str(cn) + "/prompt_id.txt").read())
  cn -= 1
prompt_id += 1


#############
# Main loop #
#############

# Perform the next refactoring step until the user exits.
while True:
  # Initialize the next refactoring step.
  
  # Next refactoring step.
  change_number += 1
  
  # Make a copy of the original file.
  os.system("cp " + working_verilog_file_name + " " + orig_verilog_file_name)

  # Initialize the prompt.
  prompt_id += 1
  open("prompt_id.txt", "w").write(str(prompt_id))
  os.system("cp prompts/" + str(prompt_id) + ".md prompt.md")

  # Make history/# directory and populate it with the static files above.
  os.mkdir("history/" + change_number)
  os.system("cp " + orig_verilog_file_name + " history/" + change_number + "/")
  os.system("cp prompt_id.txt history/" + change_number + "/")


  # Prompt the user.
  print_prompt()

  # Process user commands until a candidate is accepted or rejected.
  while True:
    # Get the user's command as a single key press (without <Enter>) using pynput library.
    print("Press command key.")
    while True:
      with keyboard.Events() as events:
        # Block for a single key press.
        event = events.get(1e6)
        if event is None:
          print("Timeout. Exiting.")
          exit(1)
        if isinstance(event, keyboard.Events.Press) and event.key in ["l", "f", "y", "n", "s", "h", "x"]:
          key = event.key
          break
        else:
          print("Error: Invalid key. Try again.")

    # Process the user's command.
    if key == "l":
      # Run the LLM (if not already run).
      if llm_passed():
        print("LLM was already run successfully. Choose a different command.")
      else:
        # Take a snapshot of the current code.
        os.system("cp " + module_name + ".v " + pre_llm_verilog_file_name)

        # Run the LLM.
        print("Calling " + llm + "...")

        # TODO:
        print("Pretend that we called the LLM and updated code here.")
        
        # Check for success.
        if llm_passed():
          print("LLM run successful.")
        else:
          print("Error: LLM run failed. Try again.")
    else if key == "f":
      # Run FEV.
      if fev_passed() and os.system("diff " + working_verilog_file_name + " fev_prove/src/" + working_verilog_file_name) == 0:
        print("FEV was already run and passed. Choose a different command.")
      elif os.system("diff " + working_verilog_file_name " + orig_verilog_file_name) == 0:
        print("There are no changes to FEV. Choose a different command.")
      else:
        # Run FEV.
        print("Calling FEV...")
        run_sby()
    
    else if key == "y":
      # Accept the candidate.
      if not fev_passed():
        print("FEV was not run on the current file or did not pass. Choose a different command.")
      elif os.system("diff " + working_verilog_file_name + " " + orig_verilog_file_name) == 0:
        print("There are no changes to accept. Choose a different command.")
      else:
        # Capture working files in history/#/.
        os.system("cp " + working_verilog_file_name + " history/" + change_number + "/")
        os.system("mv " + orig_verilog_file_name + " history/" + change_number + "/")   # Redundant with the previous step, but convenient.
        if os.path.exists(pre_llm_verilog_file_name):
          os.system("mv " + pre_llm_verilog_file_name + " history/" + change_number + "/")
        if os.path.exists(llm_verilog_file_name):
          os.system("mv " + llm_verilog_file_name + " history/" + change_number + "/")
        os.system("mv prompt.md history/" + change_number + "/")
        os.system("mv prompt_id.txt history/" + change_number + "/")  # Redundant, but small and convenient.
        break

    else if key == "n":
      # Reject the candidate.
      if os.system("diff " + working_verilog_file_name + " " + orig_verilog_file_name) == 0:
        print("There are no changes to reject. Choose a different command.")
      else:
        # Prompt the user to ask which code to revert to, the original, the LLM input, or the LLM output, conditionally
        # based on whether there are differences.
        options = ["o"]
        if os.path.exists(pre_llm_verilog_file_name) and os.system("diff " + orig_verilog_file_name + " " + pre_llm_verilog_file_name) != 0:
          options.append("p")
          options.append("m")
        if l_option = os.path.exists(llm_verilog_file_name) and os.system("diff " + orig_verilog_file_name + " " + llm_verilog_file_name) != 0:
          options.append("l")
        revert_to = "o"
        revert_verilog_file = orig_verilog_file_name
        if options["p"] or options["m"] or options["l"]:
          print("Revert to:")
          print("  o: Original code for this refactoring step.")
          if options["m"]:
            print("  m: Manual edits prior to LLM (and disgard LLM prompt).")
            revert_verilog_file = pre_llm_verilog_file_name
          if options["p"]:
            print("  p: LLM input code (and keep LLM prompt).")
            revert_verilog_file = pre_llm_verilog_file_name
          if options["l"]:
            print("  l: LLM output code.")
            revert_verilog_file = llm_verilog_file_name
          print("> ")
          while True:
            with keyboard.Events() as events:
              # Block for a single key press.
              event = events.get(1e6)
              if event is None:
                print("Timeout. Exiting.")
                exit(1)
              if isinstance(event, keyboard.Events.Press) and event.key in options:
                revert_to = event.key
                break
              else:
                print("Error: Invalid key. Try again.")

        # Next candidate number.
        candidate_number += 1
        os.mkdir("history/" + change_number + "/reject_" + candidate_number)

        # Capture working files in history/#/reject_#/ and revert files.

        # Capture working file.
        os.system("cp " + working_verilog_file_name + " history/" + change_number + "/reject_" + candidate_number + "/")
        # Revert Verilog.
        os.system("cp " + revert_verilog_file + " " + working_verilog_file_name)
        # Capture original file.
        os.system("mv " + orig_verilog_file_name + " history/" + change_number + "/reject_" + candidate_number + "/")   # Redundant with the previous step, but convenient.
        # Capture LLM-run files if they exist, keeping them if not reverting over the LLM run.
        mv_or_cp = "cp" if revert_to == "l" else "mv"
        if os.path.exists(pre_llm_verilog_file_name):
          os.system(mv_or_cp + " " + pre_llm_verilog_file_name + " history/" + change_number + "/reject_" + candidate_number + "/")
        if os.path.exists(llm_verilog_file_name):
          os.system(mv_or_cp + " " + llm_verilog_file_name + " history/" + change_number + "/reject_" + candidate_number + "/")
        # Capture prompt and prompt ID and revert prompt conditionally.
        os.system(mv_or_cp + "cp prompt.md history/" + change_number + "/reject_" + candidate_number + "/")
        os.system(mv_or_cp + "cp prompt_id.txt history/" + change_number + "/reject_" + candidate_number + "/")
        if revert_to != "l":
          os.system("cp prompts/" + str(prompt_id) + ".md prompt.md")

        # Exit the loop.
        break
      elif key == "s":
        # Allow skip only if no changes have been made, otherwise prompt the user to reject.
        if pending_changes():
          print("Changes have been made. You must accept or reject this candidate instead.")
        else:
          # Skip this LLM prompt.
          # Increment the prompt ID and start a new change with the same change number.
          prompt_id += 1
          change_number -= 1
          # (There shouldn't be any working files to delete since not llm_run() nor fev_run().)
          break
      elif key == "h":
        print_prompt()
      elif key == "x":
        if pending_changes():
          print("Changes have been made. You must accept or reject this candidate instead.")
        else:
          exit(0)
      else:
        print("Error: Invalid key. Try again.")  # (Shouldn't get here.)