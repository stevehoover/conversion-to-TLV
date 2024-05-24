# A script for refactoring a Verilog module, then converting it to TL-Verilog.
# The refactoring steps are performed by an LLM such as ChatGPT-4 via its API.
# Manual refactoring is also possible. All refactoring steps are formally verified using SymbiYosys.

# Usage:
# python3 convert.py
#   This begins or continues the conversion process for the only *.v file in the current directory.

# This script works with these files:
#  - <module_name>_orig.v: The trusted Verilog module to convert. This is the original file for the current conversion step.
#  - <module_name>.v: The current WIP refactored/modified Verilog module, against which FEV will be run.
#  - prompt_id.txt: A file containing the ID number of the prompt for this step. (The actual prompt may have been modified by the human.)
#  - messages.json: The messages to be sent to the LLM API (as in the ChatGPT API).
# Additionally, these files may be created and captured in the process:
#  - tmp/fev.sby: The FEV script for this conversion job.
#  - <module_name>_prep.v: The file sent to the LLM API.
#  - <module_name>_llm.v: The LLM output file.
#  - llm_response.txt: The LLM response file.
#
# A history of all refactoring steps is stored in history/#, where "#" is the "refactoring step", starting with history/1.
# This directory is initialized when the step is begun, and fully populated when the refactoring change is accepted.
# Contents includes:
#   - history/#/prompt_id.txt: (on init) The ID of the prompt used for this refactoring step. (The actual prompt may have been modified by the human.)
#   - history/#/<module_name>.v: The refactored file at each step.
#   - history/#/messages.json: The messages sent to the LLM API for each step.
# Although Git naturally captures a history, it may be desirable to capture this folder in Git, simply for convenience, since it may be desirable to
# easily examine file differences or to rework the conversion steps after the fact.
#
# Each refactoring step may involve a number of individual code modifications, recorded in a modification history within the refactoring step directory.
# Each modification is captured, whether accepted, rejected, or reverted.
#
# A modification is stored in history/#/mod_#/ (where # are sequential numbers).
# Contents include:
#   - history/#/mod_#/<module_name>.v: The modified Verilog file.
#   - history/#/mod_#/messages.json: The messages sent to the LLM API (for LLM modifications only).
#   - history/#/mod_#/status.json: Metadata about the modification, as below, written after testing.
#
# history/#/mod_0 are checkpoints of the initial code for each refactoring step. Thus, history/1/mod_0/<module_name>.v is the initial
# code for the entire conversion.
#
# history/#/mod_# can also be a symlink to a prior history/#/mod_#, recording a code reversion. A reversion will not reference
# another reversion.
#
# The status.json file reflects the status of the modification, updated as fields become known:
#   {
#     "by": "human"|"llm",
#     "compile": "passed"|"failed" (or non-existent if not compiled),
#     "fev": "passed"|"failed" (or non-existent if not run),
#     "incomplete": true|false A sticky field (held for each checkpoint of the refactoring step) assigned or updated by each LLM run,
#                              indicating whether the LLM response was incomplete.
#     "modified": true|false (or non-existent if not run) Indicates whether the code from the LLM was actually modified.
#     "accepted": true|non-existent Exists as true for the final modification of a refactoring step that was accepted.
#   }
#
# With each rejected refactoring step, a new candidate is captured under a new candidate number under the next history number directory.
#
# <repo>/prompts.json contains the default prompts used for refactoring steps as a JSON array of objects with the following fields:
#   - desc: a brief description of the refactoring step
#   - prompt: prompt string
#
# When launched, this script first determines the current state of the conversions process. This state is:
#   - The current candidate:
#     - The current refactoring step, which is the latest history/#.
#     - The next candidate number, which is the next history/#/mod_#
#     - The next prompt ID, which is the ID of the prompt for the current refactoring step. This is the next prompt ID following the
#       most recent that can be found in history/#/.
#   Note that history/#/mod_#/ can be traced backward to determine what has been done so far.

#
# This is a command-line utility which prompts the user for input. Edits to <module_name>.v and/or prompt.txt can be made while input is pending.
# It is suggested to have <module_name>.v and prompt.txt open in an editor and in a diff utility, such as meld, while running this script. Users
# must be careful to save files before responding to prompts.
#
# To begin each step, the user is given instructions and prompted for input.
# The user makes edits and enters commands until a candidate is accepted or rejected, and the process repeats.

import os
import subprocess
from openai import OpenAI
import sys
import termios
import tty
import atexit
import signal
from select import select
from abc import ABC, abstractmethod
import json
import re

###################################
# Abstract Base Class for LLM API #
###################################

class LLM_API(ABC):
  name = "LLM"
  model = None

  def __init__(self):
    pass

  def setModel(self, model):
    self.model = model

  # Run the LLM API on the prompt file, producing a (TL-)Verilog file.
  @abstractmethod
  def run(self):
    pass

# A class responsible for bundling messages objects into text and visa versa.
# This class isolates the format of LLM messages from the functionality and enables message formats to be used
# that are optimized for the LLM.
class MessageBundler:
  # Convert the given object to text.
  # The object format is:
  #   {
  #     "desc": "This is a description.",
  #     "prompt": "This is a prompt.\n\nIt has multiple lines."
  #   }
  @abstractmethod
  def obj_to_content(self, json):
    pass

  # Convert the given LLM response text into an object of the form:
  #   {
  #     "overview": "This is an overview.",
  #     "verilog": "This is the Verilog code.",
  #     "notes": "These are notes.",
  #     "issues": "These are issues.",
  #     "modified": true,
  #     "incomplete": true
  #   }
  @abstractmethod
  def content_to_obj(self, content):
    pass

  # Add Verilog to last message to be sent to the API.
  # messages: The messages.json object in OpenAI format.
  # verilog: The current Verilog file contents.
  @abstractmethod
  def add_verilog(self, messages, verilog):
    pass

class OpenAI_API(LLM_API):
  name = "OpenAI"
  model = "gpt-3.5-turbo"

  def __init__(self):
    super().__init__()

    # if OPENAI_API_KEY env var does not exist, get it from ~/.openai/key.txt or input prompt.
    if not os.getenv("OPENAI_API_KEY"):
      key_file_name = os.path.expanduser("~/.openai/key.txt")
      if os.path.exists(key_file_name):
        with open(key_file_name) as file:
          os.environ["OPENAI_API_KEY"] = file.read()
      else:
        os.environ["OPENAI_API_KEY"] = input("Enter your OpenAI API key: ")
    
    # Use an organization in the request if one is provided, either in the OPENAI_ORG_ID env var or in ~/.openai/org_id.txt.
    self.org_id = os.getenv("OPENAI_ORG_ID")
    if not self.org_id:
      org_file_name = os.path.expanduser("~/.openai/org_id.txt")
      if os.path.exists(org_file_name):
        with open(org_file_name) as file:
          self.org_id = file.read()
    
    # Init OpenAI.
    self.client = OpenAI() if self.org_id is None else OpenAI(organization=self.org_id)
    #self.models = self.client.models.list()
  
  def setModel(self, model):
    # TODO:...
    #if model not in self.models.data...:
    #  print("Error: Model " + model + " not found.")
    #  sys.exit(1)
    self.model = model

  # Set up the initial messages object for the current refactoring step based on the given system message and prompt
  # (from this step's prompt.txt).
  def initPrompt(self, system, message):
    return [
      {"role": "system", "content": system},
      {"role": "user", "content": message}
    ]


  # Run the LLM API on the messages.json file appended with the verilog code, returning the response string from the LLM.
  def run(self, messages, verilog):
    # Add verilog to the last message.
    message_bundler.add_verilog(messages, verilog)

    # Call the API.
    print("Calling " + self.model + "...")
    # TODO: Not supported in ChatGPT-3.5: response_format = {"type": "json_object"}
    api_response = self.client.chat.completions.create(model=self.model, messages=messages, max_tokens=500, temperature=0.0)
    print("Response received from " + self.model)

    # Parse the response.
    try:
      response_str = api_response.choices[0].message.content
      finish_reason = api_response.choices[0].finish_reason
      completion_tokens = api_response.usage.completion_tokens
      print("API response finish reason: " + finish_reason)
      print("API response completion tokens: " + str(completion_tokens))
    except Exception as e:
      print("Error: API response is invalid.")
      print(str(e))
      sys.exit(1)
    return response_str

# Response fields.
sticky_response_fields = {"clock", "reset", "assertion"}    # ("incomplete" is also sticky, but only between LLM runs, so it has special treatment.)
legal_response_fields = sticky_response_fields | {"overview", "verilog", "modified", "incomplete", "issues", "notes", "plan"}
class PseudoMarkdownMessageBundler(MessageBundler):
  # Convert the given object to a pseudo-Markdown format. Markdown syntax is familiar to the LLM, and fields can be
  # provided without any awkward escaping and other formatting, as described in default_system_message.txt.
  # Example JSON:
  #   {"instructions": "These are instructions.", "verilog": "module...\nendmodule"}
  # Example output:
  #   ## Instructions
  #   
  #   These are instructions.
  #   
  #   ## Verilog
  #   
  #   ```
  #   module...
  #   endmodule
  #   ```
  def obj_to_request(self, obj):
    content = "# Request\n\n"
    separator = ""
    for key in obj:
      # Convert (single-word) key to title case.
      name = key[0].upper() + key[1:]
      content += separator + "## " + name + "\n\n" + obj[key]
      separator = "\n\n"
    return content

  # Convert the given LLM API response string from the pseudo-Markdown format requested into an object, as described
  # in default_system_message.txt.
  def response_to_obj(self, response):
    # Parse the response, line by line, looking for second-level Markdown header lines.
    lines = response.split("\n")
    # Parse "# Response" header.
    if not re.match(r"^# Response$", lines[0]):
      print("Warning: API response is missing \"# Response\" header.")
    else:
      lines = lines[1:]
      if not re.match(r"^\s*$", lines[0]):
        print("Warning: API response is missing blank line after \"# Response\" header.")
      else:
        lines = lines[1:]
    
    l = 0
    fields = {}
    field = None
    while l < len(lines):
      # Parse body lines until the next field header or end of message.
      body = ""
      separator = ""
      while l < len(lines) and not lines[l].startswith("## "):
        if (body != "") or (re.match(r"^\s*$", lines[l]) is None):    # Ignore leading blank lines.
          body += separator + lines[l]
          separator = "\n"
        l += 1
      # Found header line or EOM.

      # Process the body field that ended.
      
      # Strip trailing whitespace.
      body = re.sub(r"\s*$", "", body)
      if field is None:
        if body != "":
          print("Error: The following body text was found before the first header and will be ignored:")
          print(body)
      else:
        # "verilog" field should be in block quotes. Confirm, and remove them.
        if field == "verilog":
          body, n = re.subn(r"^```\n(.*)\n+```$", r"\1\n", body, flags=re.DOTALL)
          if n != 1:
            print("Warning: The \"Verilog\" field of the response was not contained in block quotes and may be malformed.")

        # Capture the previous field.
        # Boolean responses.
        if body == "true" or body == "false":
          body = body == "true"
        fields[field] = body
        
      if l < len(lines):
        # Parse the header line with a regular expression.
        field = re.match(r"## +(\w+)", lines[l]).group(1)

        # The field name should be a single upper-case word.
        if not re.match(r"[A-Z][a-z]*", field):
          print("Error: The following non-standard field was found in the response:")
          print(field)

        # Convert field name to lower case.
        field = field.lower()
          
        # Check for legal field name.
        if field not in legal_response_fields:
          print("Warning: The following non-standard field was found in the response:")
          print(field)

        # Done with this header line.
        l += 1
    
    return fields

  # Add Verilog to last message to be sent to the API.
  # messages: The messages.json object in OpenAI format.
  # verilog: The current Verilog file contents.
  def add_verilog(self, messages, verilog):
    # Add verilog to the last message.
    messages[-1]["content"] += "\n\n## Verilog\n\n```" + verilog + "```"


def changes_pending():
  return os.path.exists(mod_path() + "/" + working_verilog_file_name) and diff(working_verilog_file_name, mod_path() + "/" + working_verilog_file_name)

# See if there were any manual edits to the Verilog file and capture them in the history if so.
def checkpoint_if_pending():
  # if latest mod file exists and is different from working file, checkpoint it.
  if changes_pending():
    print("Manual edits were made and are being checkpointed.")
    checkpoint({ "by": "human" })

# Checkpoint any manual edits, run LLM, and checkpoint the result if successful. Return nothing.
# messages: The messages.json object in OpenAI format.
# verilog: The current Verilog file contents.
def run_llm(messages, verilog):
  checkpoint_if_pending()

  # Run the LLM, passing the messages.json and verilog file contents.

  # Confirm.
  print("")
  print("The following prompt will be sent to the API together with the Verilog and prior messages:")
  print("")
  print(messages[-1]["content"])
  print("")
  press_any_key()

  # If there is already a response, prompt the user about possibly reusing it.
  ch = "n"
  if os.path.exists("llm_response.txt"):
    print("There is already a response to this prompt. Would you like to reuse it [y/N]?")
    print("> ", end="")
    ch = getch()
    print("")
  if ch == "y":
    # Use llm_response.txt.
    with open("llm_response.txt") as file:
      response_str = file.read()
  else:
    # Call the API.
    response_str = llm_api.run(messages, verilog)
    # Write llm_response.txt.
    with open("llm_response.txt", "w") as file:
      file.write(response_str)
  
  response_obj = message_bundler.response_to_obj(response_str)


  # Commented code here is for requesting a JSON object response from the API, which is not the current approach.
  #
  ## LLM tends to respond with multi-line strings, which are not valid JSON. Fix this.
  #response_json = response_json.replace("\n", "\\n")

  #try:
  #  response = json.loads(response_json)
  #except:
  #  print("Error: API response was invalid JSON:")
  #  print(response_json)
  #  sys.exit(1)

  # Response should include "modified", but if it is missing and "verilog" is present, assume "modified" is True.
  if "modified" not in response_obj and "verilog" in response_obj:
    response_obj["modified"] = True
    print("Warning: API response is missing \"modified\" field. Assuming \"modified\" is True.")

  if (response_obj.get("modified", False) and "verilog" not in response_obj) or "modified" not in response_obj:
    print("Error: API response fields are incomplete or inconsistent.")
    sys.exit(1)

  # Confirm.
  print("")
  print("The following response was received from the API, to replace the Verilog file:")
  print("")
  # Reformat the JSON into multiple lines and extract the verilog for cleaner printing.
  code = response_obj.get("verilog")
  if code:
    del response_obj["verilog"]
  print(json.dumps(response_obj, indent=4))
  if code:
    print("-------------")
    print(code)
    print("-------------")
    # Repare the response.
    response_obj["verilog"] = code
  print("")
  press_any_key()

  if "notes" in response_obj:
    print("Notes:\n   " + response_obj["notes"].replace("\n", "\n   ") + "\n")

  modified = response_obj["modified"]  # As reported by the LLM, and updated to reflect reality.
  if modified:
    code = response_obj["verilog"]
    # Get working code.
    with open(working_verilog_file_name) as file:
      working_code = file.read()

    # Write the resulting Verilog file.
    with open(working_verilog_file_name, "w") as file:
      file.write(code)
    
    # Confirm that there were in fact changes.
    if code == working_code:
      print("Note: No changes were made, though the API response indicates otherwise. (Checkpointing anyway.)")
      modified = False
    else:
      print("Checkpointing changes.")
  else:
    # LLM says no changes.
    print("No changes were made for this refactoring step. (Checkpointing anyway.)")
  
  # Checkpoint, whether modified or not.
  orig_status = readStatus()
  status = { "by": "llm", "incomplete": response_obj.get("incomplete", False), "modified": modified }
  if not modified:
    # Reflect FEV and compile status from prior checkpoint.
    status["compile"] = orig_status.get("compile")
    status["fev"] = orig_status.get("fev")
  # Apply sticky fields to status.
  for field in sticky_response_fields:
    if field in response_obj:
      status[field] = response_obj[field]
  checkpoint(status)


  # Response accepted, so delete llm_response.txt.
  os.remove("llm_response.txt")
  if "issues" in response_obj:
    print(llm_api.model + " reports the following issues:")
    print("   " + response_obj["issues"].replace("\n", "\n   ") + "\n")
  
  return response_obj


#############
# Constants #
#############

llm_api = OpenAI_API()
message_bundler = PseudoMarkdownMessageBundler()

# Get the directory of this script.
repo_dir = os.path.dirname(os.path.realpath(__file__))

#
# Find FEV script.
#

fev_script = repo_dir + "/" + "fev.sby"
if not os.path.exists(fev_script):
  print("Error: Conversion repository does not contain " + fev_script + ".")
  usage()

# Read prompts.json.
# prompts.json is a slight extension to JSON to support newlines in strings. Lines beginning with "+" continue a string with an implied newline.
with open(repo_dir + "/prompts.json") as file:
  raw_contents = file.read()
json_str = raw_contents.replace("\n+", "\\n")
prompts = json.loads(json_str)


####################
# Helper functions #
####################

# Report a usage message.
def usage():
  print("Usage: python3 .../convert.py")
  print("  Call from a directory containing a single Verilog file to convert or a \"history\" directory.")
  sys.exit(0)

# Determine if a filename has a Verilog/SystemVerilog extension.
def is_verilog(filename):
  return filename.endswith(".v") or filename.endswith(".sv")

# Run SymbiYosys.
def run_sby():
  subprocess.run(["sby", "-f", "tmp/fev.sby"])

# Run FEV using Yosys on the given top-level module name and orig and modified files.
# Return the subprocess.CompletedProcess of the FEV command.
def run_yosys_fev(module_name, orig_file_name, modified_file_name):
  env = {"TOP_MODULE": module_name, "ORIGINAL_VERILOG_FILE": orig_file_name, "MODIFIED_VERILOG_FILE": modified_file_name}
  return subprocess.run(["/home/owais/yosys/yosys", repo_dir + "/fev.tcl"], env=env)

# Functions that determine the state of the refactoring step based on the state of the files.
# TODO: replace?
def llm_passed():
  return os.path.exists(llm_verilog_file_name)

def llm_finished():
  return not readStatus().get("incomplete", True)

def fev_passed():
  return os.path.exists("fev/PASS") and os.system("diff " + module_name + ".v fev/src/" + module_name + ".v") == 0

def diff(file1, file2):
  return os.system("diff -q '" + file1 + "' '" + file2 + "' > /dev/null") != 0

# Capture Verilog file in a new history/#/mod_#/, and if this was an LLM modification, capture messages.json.
#  status: The status to save with the checkpoint.
# Sticky status is applied from current status. Status["incomplete"] will be carried over from the prior checkpoint for non-LLM updates.
def checkpoint(status):
  global mod_num
  # Carry over sticky status from the prior checkpoint.
  for field in sticky_response_fields:
    if field not in status and field in readStatus():
      status[field] = readStatus()[field]
  if status.get("by") != "llm" and not (readStatus().get("incomplete") is None):
    status["incomplete"] = readStatus()["incomplete"]
  
  # Capture the current Verilog file.
  mod_num += 1
  os.mkdir(mod_path())
  os.system("cp " + working_verilog_file_name + " history/" + str(refactoring_step) + "/mod_" + str(mod_num) + "/")

  # Capture messages.json if this was an LLM modification.
  if status.get("by") == "llm":
    os.system("cp messages.json history/" + str(refactoring_step) + "/mod_" + str(mod_num) + "/")
  
  # Write status.json.
  writeStatus(status)

  # Create a reversion checkpoint as a symlink, or if the previous change was a reversion, update its symlink.
def checkpoint_reversion(prev_mod):
  global mod_num
  if os.path.islink(mod_path()):
    os.remove(mod_path())
  else:
    mod_num += 1
  os.symlink("mod_" + str(prev_mod), mod_path())

def readStatus(mod = None):
  # Default mod to mod_num
  if mod is None:
    mod = mod_num
  # Read status from latest history change directory.
  try:
    with open(mod_path(mod) + "/status.json") as file:
      return json.load(file)
  except:
    return {}

def writeStatus(status):
  # Write status to latest history change directory.
  with open(mod_path() + "/status.json", "w") as file:
    json.dump(status, file)


# Print the main user prompt.
def print_prompt():
  print("The next refactoring step (" + str(refactoring_step) + ") for the LLM uses prompt " + str(prompt_id) + ":\n")
  # Output the README for the current prompt ID, indented by 5 spaces.
  print("   | " + prompts[prompt_id]["desc"].replace("\n", "\n   | "))
  print("  ")
  print("  Make edits and enter command characters until a candidate is accepted or rejected. Generally, the sequence is:")
  print("    - (optional) Make any desired manual edits to " + working_verilog_file_name + " and/or prompt.txt.")
  print("    - l: (optional) Run the LLM step. (If this fails or is incomplete, make any further manual edits and try again.)")
  print("    - (optional) Make any desired manual edits to " + working_verilog_file_name + ". (You may use \"f\" to run FEV first.)")
  print("    - f: Run FEV. (If this fails, make further manual Verilog edits and try again.)")
  print("    - y: Accept the current code as the completion of this refactoring step.")
  print("  (At any time: use \"n\" to undo changes; \"h\" for help; \"x\" to exit.)")
  print("  ")
  print("  Enter one of the following commands:")
  print("    l: LLM. Send the current prompt.txt to the LLM....Run this refactoring step in ChatGPT-4/Claude2 (if LLM not already completed).")
  print("    f: Run FEV on the current code.")
  print("    y: Yes. Accept the current code as the completion of this refactoring step (if FEV already run and passed).")
  print("    u: Undo. Revert to a previous version of the code.")
  print("    U: Redo. Reapply a reverted code change (possible until next modification or exit).")
  print("    c: Checkpoint the current human edits in the history.")
  print("    h: History. Show a history of recent changes in this refactoring step.")
  print("    ?: Help. Repeat this message.")
  print("    x: Exit.")

# Function to initialize the conversion directory for the next refactoring step.
def init_refactoring_step():
  global refactoring_step, mod_num, prompt_id

  # Get sticky status from current refactoring step before creating next.
  old_status = {}
  if refactoring_step > 0:
    old_status = readStatus()
    
  refactoring_step += 1
  mod_num = -1

  # Initialize the prompt.
  prompt_id += 1
  with open("prompt_id.txt", "w") as file:
    file.write(str(prompt_id))

  # Make history/# directory and populate it.
  os.mkdir("history/" + str(refactoring_step))
  os.system("cp prompt_id.txt history/" + str(refactoring_step) + "/")
  # Also, create an initial mod_0 directory populated with initial verilog and status.json indicating initial code.
  status = { "initial": True, "fev": "passed" }
  # Apply sticky status from last refactoring step.
  for field in sticky_response_fields:
    if field in old_status:
      status[field] = old_status[field]
  checkpoint(status)
  # (mod_num now 0)

  # Initialize messages.json.
  try:
    # Read the system message from <repo>/default_system_message.txt.
    with open(repo_dir + "/default_system_message.txt") as file:
      system = file.read()
    with open("messages.json", "w") as file:
      message = message_bundler.obj_to_request({'prompt': prompts[prompt_id]["prompt"]})
      json.dump(llm_api.initPrompt(system, message), file, indent=4)
  except Exception as e:
    print("Error: Failed to initialize messages.json due to: " + str(e))
    sys.exit(1)


# Evaluate the given anonymous function, fn(mod), from the most recent modification to the least recent until fn indicates completion.
# fn(mod) returns False to keep iterating or True to terminate.
# Return the terminating mod number or None.
def most_recent(fn, mod=None):
  # Default mod to mod_num
  if mod is None:
    mod = mod_num
  while mod >= 0:
    mod = actual_mod(mod)
    if fn(mod):
      return mod
    mod -= 1
  return None

# Run FEV against the last successfully FEVed code (if not in this refactoring step, the the original code for this step).
# Update status.json.
def run_fev():
  checkpoint_if_pending()

  status = readStatus()
  # Get the most recently FEVed code (mod with status["fev"] == "passed").
  last_fev_mod = most_recent(lambda mn: (readStatus(mn).get("fev") == "passed"))
  assert(last_fev_mod is not None)
  # FEV vs. last successful FEV.
  orig_file_name = mod_path(last_fev_mod) + "/" + working_verilog_file_name
  
  print("Running FEV against " + orig_file_name + ". Diff:")
  print("==================")
  diff_status = os.system("diff " + orig_file_name + " " + working_verilog_file_name)
  print("==================")
  print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
  print(orig_file_name)
  print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
  print(working_verilog_file_name)
  print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
  ret = False
  # Run FEV.
  if diff_status == 0:
    print("No changes to FEV. Choose a different command.")
    ret = True
  else:
    # Run FEV.

    # Create fev.sby.
    # This is done by copying in <repo>/fev.sby and substituting "{MODULE_NAME}", "{ORIGINAL_FILE}", and "{MODIFIED_FILE}" using sed.
    os.system(f"cp {fev_script} tmp/fev.sby")
    os.system(f"sed -i 's/<MODULE_NAME>/{module_name}/g' tmp/fev.sby")
    # These paths must be absolute.
    os.system(f"sed -i 's|<ORIGINAL_FILE>|{os.getcwd()}/{orig_file_name}|g' tmp/fev.sby")
    os.system(f"sed -i 's|<MODIFIED_FILE>|{os.getcwd()}/{working_verilog_file_name}|g' tmp/fev.sby")
    # To run the above manually in bash, as a one-liner from the conversion directory, providing <MODULE_NAME>, <ORIGINAL_FILE>, and <MODIFIED_FILE>:
    #   cp ../fev.sby fev.sby && sed -i 's/<MODULE_NAME>/<module_name>/g' fev.sby && sed -i "s|<ORIGINAL_FILE>|$PWD/<original_file>|g" fev.sby && sed -i "s|<MODIFIED_FILE>|$PWD/<modified_file>|g" fev.sby

    #run_sby()
    proc = run_yosys_fev(module_name, orig_file_name, working_verilog_file_name)
    # Check for success.
    #passed = fev_passed()
    passed = proc.returncode == 0
    if passed:
      print("FEV passed.")
      status["fev"] = "passed"
    else:
      print("Error: FEV failed. Try again.")
      status["fev"] = "failed"
    writeStatus(status)
    # TODO: If failed, bundle failure info for LLM, and call LLM (with approval).
    ret = passed
  return ret

# Number of the most recent modification (that actually made a change) or None.
def most_recent_mod():
  return most_recent(lambda mod: (readStatus(mod).get("modified", False)))

# The path of the latest modification of this refactoring step.
def mod_path(mod = None):
  # Default mod to mod_num
  if mod is None:
    mod = mod_num
  return "history/" + str(refactoring_step) + "/mod_" + str(mod)

# Show a diff between the given (or current) modification and the previous one.
# Return true is shown, or false if there is no previous modification.
def show_diff(mod = None, prev_mod = None):
  # Default mod to mod_num
  if mod is None:
    mod = mod_num
  mod = actual_mod(mod)
  # Get the previous modification.
  if prev_mod is None:
    prev_mod = most_recent(lambda mn: (mn < mod), mod)
    if prev_mod is None:
      print("There is no previous modification.")
      return False
  # Show the diff.
  print("Diff between mod_" + str(prev_mod) + " and mod_" + str(mod) + ":")
  print("==================")
  os.system("diff " + mod_path(prev_mod) + "/" + working_verilog_file_name + " " + mod_path(mod) + "/" + working_verilog_file_name)
  print("==================")
  return True



##################
# Terminal input #
##################

def set_raw_mode(fd):
    attrs = termios.tcgetattr(fd)  # get current attributes
    attrs[3] = attrs[3] & ~termios.ICANON  # clear ICANON flag
    termios.tcsetattr(fd, termios.TCSANOW, attrs)  # set new attributes

def set_cooked_mode(fd):
    attrs = termios.tcgetattr(fd)  # get current attributes
    attrs[3] = attrs[3] | termios.ICANON # set ICANON flag
    termios.tcsetattr(fd, termios.TCSANOW, attrs)  # set new attributes

# Set to default cooked mode (in case the last run was exited in raw mode).
set_cooked_mode(sys.stdin.fileno())

def getch():
  ## Save the current terminal settings
  #old_settings = termios.tcgetattr(sys.stdin)
  try:
    # Set the terminal to raw mode
    set_raw_mode(sys.stdin.fileno())
    # Wait for input to be available
    [i], _, _ = select([sys.stdin.fileno()], [], [], None)
    # Read a single character
    ch = sys.stdin.read(1)
  finally:
    # Restore the terminal settings
    set_cooked_mode(sys.stdin.fileno())
  return ch

## Capture the current terminal settings before setting raw mode
#default_settings = termios.tcgetattr(sys.stdin)
##old_settings = termios.tcgetattr(sys.stdin)

def cleanup():
  print("Exiting cleanly.")
  # Set the terminal settings to the default settings
  #termios.tcsetattr(sys.stdin, termios.TCSADRAIN, default_settings)
  #set_cooked_mode(sys.stdin.fileno())
# Register the cleanup function
atexit.register(cleanup)

# Accept terminal input command character from among the given list.
def get_command(options):
  while True:
    print("\nPress one of the following command keys: {}".format(", ".join(options)))
    print("> ", end="")
    ch = getch()
    print("")
    if ch not in options:
      print("Error: Invalid key. Try again.")
    else:
      return ch

# Catch signals for proper cleanup.

# Define a handler for signals that will perform cleanup
def signal_handler(signum, frame):
    print(f"Caught signal {signum}, exiting...")
    sys.exit(1)

# Register the signal handler for as many signals as possible.
for sig in [signal.SIGABRT, signal.SIGINT, signal.SIGTERM]:
    signal.signal(sig, signal_handler)

# Pause for a key press.
def press_any_key():
  print("Press any key to continue...\n> ", end="")
  getch()




######################
#                    #
#  Main entry point  #
#                    #
######################

###########################
# Parse command-line args #
###########################
# (None)


##################
# Initialization #
##################

#
# Determine file names.
#

# Find the Verilog file to convert, ending in ".v" or ".sv" as the shortest Verilog file in the directory.
files = [f for f in os.listdir(".") if is_verilog(f)]
if len(files) != 1 and not os.path.exists("history"):
  print("Error: There must be exactly one Verilog file or a \"history\" directory in the current working directory.")
  usage()
# Choose the shortest Verilog file name as the one to convert.
file_name_len = 1000
working_verilog_file_name = None
for file in files:
  if len(file) < file_name_len:
    file_name_len = len(file)
    working_verilog_file_name = file
if not working_verilog_file_name:
  print("Error: No Verilog file found in current working directory.")
  usage()

# Derived file names.
module_name = working_verilog_file_name.split(".")[0]
orig_verilog_file_name = module_name + "_orig.v"
llm_verilog_file_name = module_name + "_llm.v"


####################
# Initialize state #
####################

#
# Determine which refactoring step we are on
#

# Current state variables.
refactoring_step = 0  # The current refactoring step (history/<refactoring_step>).
mod_num = 0  # The current mod number (history/#/mod_<mod_num>).
prompt_id = 0  # The current prompt ID (prompt_id.txt).

if not os.path.exists("history"):
  # Initialize the conversion job.
  os.mkdir("history")
  if not os.path.exists("tmp"):
    os.mkdir("tmp")
  init_refactoring_step()
else:
  # Determine the current state of the conversion process.
  # Find the current refactoring step.
  for step in os.listdir("history"):
    refactoring_step = max(refactoring_step, int(step))
  # Find the current modification number.
  for dir in os.listdir("history/" + str(refactoring_step)):
    if dir.startswith("mod_"):
      mod_num = max(mod_num, int(dir.split("_")[1]))

  # Get the prompt ID from the most recent prompt_id.txt file. Look back through the history directories until/if one is found.
  cn = refactoring_step
  while cn >= 0 and prompt_id == 0:
    if os.path.exists("history/" + str(cn) + "/prompt_id.txt"):
      with open("history/" + str(cn) + "/prompt_id.txt") as f:
        prompt_id = int(f.read())
    cn -= 1

# Get the actual modification of the given modification number (or current). In other words, if the given mod is a
# reversion, follow the symlink.
def actual_mod(mod=None):
  if mod is None:
    mod = mod_num
  if os.path.islink(mod_path(mod)):
    tmp1 = os.readlink(mod_path(mod))[4:]
    tmp2 = int(tmp1)
    return tmp2
  else:
    return mod


###############
#             #
#  Main loop  #
#             #
###############

# Perform the next refactoring step until the user exits.
while True:

  # Prompt the user.
  print_prompt()

  # Process user commands until a modification is accepted or rejected.
  while True:
    # Get the user's command as a single key press (without <Enter>) using pynput library.
    key = get_command(["l", "f", "y", "s", "h", "x", "u", "U", "c", "?"])

    # Process the user's command.
    if key == "l":
      # Run the LLM (if not already run).
      do_it = True
      if llm_finished():
        print("LLM was already run and completed reported that the refactoring was complete. Run anyway? [y/N]")
        print("> ", end="")
        ch = getch()
        print("")
        if ch != "y":
          print("Choose a different command.")
          do_it = False
      if do_it:
        with open("messages.json") as message_file:
          with open(working_verilog_file_name) as verilog_file:
            run_llm(json.loads(message_file.read()), verilog_file.read())
    elif key == "f":
      run_fev()
    elif key == "y":
      status = readStatus()
      # Can only accept changes that have been FEVed.
      # There must not be any uncommitted manual edits pending.
      confirm = True
      do_it = False
      last_mod = most_recent_mod()
      if last_mod is None:
        print("There have been no changes for this refactoring step.")
        do_it = True
        confirm = False
      elif diff(working_verilog_file_name, mod_path() + "/" + working_verilog_file_name):
        print("Code edits are pending. You must run FEV (or revert) before accepting the refactoring changes.")
      elif status.get("fev") != "passed":
        print("FEV was not run on the current file or did not pass. Choose a different command.")
      elif status.get("incomplete", False):
        print("LLM reported that the refactoring is incomplete.")
        do_it = True
      else:
        do_it = True
        confirm = False
      
      if do_it and confirm:
        # Are you sure?
        print("Are you sure you want to accept this refactoring step as complete [y/N]?")
        print("> ", end="")
        ch = getch()
        print("")
        do_it = ch == "y"
        if do_it:
          print("Accepting the refactoring step as complete.")
        else:
          print("Choose a different command.")
      
      if do_it:
        # Accept the modification.
        # Capture working files in history/#/.
        status["accepted"] = True
        writeStatus(status)
        # Next refactoring step.
        init_refactoring_step()
        break

      """
      elif key == "n":
        # Reject the modification.
        if not diff(working_verilog_file_name, orig_verilog_file_name):
          print("There are no changes to reject. Choose a different command.")
        else:
          # Prompt the user to ask which code to revert to, the original, the LLM input, or the LLM output, conditionally
          # based on whether there are differences.
          options = ["o"]
          if os.path.exists(pre_llm_verilog_file_name) and diff(orig_verilog_file_name, pre_llm_verilog_file_name):
            options.append("p")
            options.append("m")
          if os.path.exists(llm_verilog_file_name) and diff(orig_verilog_file_name, llm_verilog_file_name):
            options.append("l")
          revert_to = "o"
          revert_verilog_file = orig_verilog_file_name
          if options["p"] or options["m"] or options["l"]:
            print("Revert to:")
            print("  o: Original code for this refactoring step.")
            if options["m"]:
              print("  m: Manual edits prior to LLM (and discard LLM prompt).")
              revert_verilog_file = pre_llm_verilog_file_name
            if options["p"]:
              print("  p: LLM input code (and keep LLM prompt).")
              revert_verilog_file = pre_llm_verilog_file_name
            if options["l"]:
              print("  l: LLM output code.")
              revert_verilog_file = llm_verilog_file_name
            revert_to = get_command(options)

          # Next modification number.
          mod_num += 1
          os.mkdir(mod_path())

          # Capture working files in history/#/mod_#/ and revert files.

          # Capture status.
          open(mod_path() + "/status.json", "w").write(json.dumps(status))
          # Capture working file.
          os.system("cp " + working_verilog_file_name + " history/" + str(refactoring_step) + "/mod_" + str(mod_num) + "/")
          # Revert Verilog.
          os.system("cp " + revert_verilog_file + " " + working_verilog_file_name)
          # Capture original file.
          os.system("mv " + orig_verilog_file_name + " history/" + str(refactoring_step) + "/mod_" + str(mod_num) + "/")   # Redundant with the previous step, but convenient.
          # Capture LLM-run files if they exist, keeping them if not reverting over the LLM run.
          mv_or_cp = "cp" if revert_to == "l" else "mv"
          if os.path.exists(pre_llm_verilog_file_name):
            os.system(mv_or_cp + " " + pre_llm_verilog_file_name + " history/" + str(refactoring_step) + "/mod_" + str(mod_num) + "/")
          if os.path.exists(llm_verilog_file_name):
            os.system(mv_or_cp + " " + llm_verilog_file_name + " history/" + str(refactoring_step) + "/mod_" + str(mod_num) + "/")
          # Capture prompt and prompt ID and revert prompt conditionally.
          os.system(mv_or_cp + "cp prompt.txt history/" + str(refactoring_step) + "/mod_" + str(mod_num) + "/")
          os.system(cp + "cp prompt_id.txt history/" + str(refactoring_step) + "/mod_" + str(mod_num) + "/")
          if revert_to != "l":
            os.system("cp " + prompt_path_prefix + ".txt prompt.txt")
          
          # Clear status.
          status = {}
      """
    elif key == "h":
      # Show a history of recent changes in this refactoring step.
      dist = 9
      print(f"Last <= {dist} changes for this refactoring step:")
      # Print the history of changes for this refactoring step.
      mod = mod_num
      real_mod = actual_mod(mod)
      cnt = 0
      out = []   # Output strings to print in reverse order.
      while cnt < 10:
        # Capture a string to print in reverse order containing the mod number, status, and a forked indication.
        out.append(f" {'v- ' if mod != real_mod else '   '}{real_mod}: {json.dumps(readStatus(real_mod))}")
        # Next
        if real_mod <= 0:
          break
        mod = real_mod - 1
        real_mod = actual_mod(mod)
        cnt += 1
      # Print in reverse order.
      for line in reversed(out):
        print(line)
      print("  ")
      
      # Print a diff of the most recent modification (if there were at least two).
      show_diff()

    elif key == "u":
      checkpoint_if_pending()

      # Revert to the previous modification.
      mod = actual_mod()
      prev_mod = None if mod <= 0 else actual_mod(mod - 1)
      if prev_mod is None:
        print("There is no previous modification.")
      else:
        # Revert to a previous version of the code.
        print("Reverting to the previous version of the code.")
        show_diff(mod, prev_mod)
        # Copy the checkpointed verilog and messages.json.
        os.system("cp " + mod_path(prev_mod) + "/" + working_verilog_file_name + " " + working_verilog_file_name)
        os.system("cp " + mod_path(prev_mod) + "/messages.json messages.json")

        # Create a reversion checkpoint as a symlink, either as a new checkpoint or by updating the existing symlink.
        checkpoint_reversion(prev_mod)

    elif key == "U":
      # Redo a reverted code change.
      if changes_pending() or not os.path.islink(mod_path()):
        print("Error: Changes have been made since the last reversion. Cannot redo.")
        continue
      # Get most recent change.
      mod = actual_mod()
      # Find all symlinks to this change for which the next sequential modification is a non-link directory. Each is a candidate for redoing.
      candidates = []
      for mod_dir in os.listdir("history/" + str(refactoring_step)):
        if os.path.islink("history/" + str(refactoring_step) + "/" + mod_dir) and os.readlink("history/" + str(refactoring_step) + "/" + mod_dir) == "mod_" + str(mod):
          # This is a symlink to the current mod.
          # Check if the next mod is a symlink.
          m = int(mod_dir.split("_")[1])
          if not os.path.islink("history/" + str(refactoring_step) + "/mod_" + str(m + 1)) and os.path.isdir("history/" + str(refactoring_step) + "/mod_" + str(m + 1)):
            candidates.append(m)
      
      # List all candidates.
      if len(candidates) == 0:
        print("There are no reversion candidates to redo.")
        continue
      print("The following reversion candidates are available to redo:")
      # List each with a sequential number for selection.
      for i in range(len(candidates)):
        print("  [" + str(i) + "] mod_" + str(candidates[i]) + ": " + json.dumps(readStatus(m)))
      
      # Prompt the user to choose a candidate.
      print("Enter the [#] number of the reversion to redo:")
      print("> ", end="")
      ch = getch()
      print("")
      if not ch.isdigit() or int(ch) < 0 or int(ch) >= len(candidates):
        print("Error: Invalid selection. Try again.")
        continue
      # Redo the selected reversion.
      mod = candidates[int(ch)]

      # Create a reversion checkpoint as a symlink, either as a new checkpoint or by updating the existing symlink.
      checkpoint_reversion(mod)

      
      print("Reapplied these changes:")
      show_diff()
      print("")
      print("Status of these changes: " + json.dumps(readStatus(mod)))
      
    elif key == "c":
      # Capture the current human edits in the history.
      # ...TODO...
      print("Error: Not implemented yet. Try again.")
      """
      elif key == "s":
        # Allow skip only if no changes have been made, otherwise prompt the user to reject.
        if pending_changes():
          print("Changes have been made. You must accept or reject this modification instead.")
        else:
          # Skip this LLM prompt.
          # Increment the prompt ID and recreate this change.
          prompt_id += 1
          # (There shouldn't be any working files to delete since not llm_passed() nor fev_passed().)
          continue
      """
    elif key == "?":
      print_prompt()
    elif key == "x":
      checkpoint_if_pending()
      exit(0)
    else:
      print("Error: Invalid key. Try again.")  # (Shouldn't get here.)
