# A script for refactoring a Verilog module, then converting it to TL-Verilog.
# The refactoring steps are performed by an LLM such as ChatGPT-4 via its API.
# Manual refactoring is also possible. All refactoring steps are formally verified using SymbiYosys.

# Usage:
# python3 convert.py
#   This begins or continues the conversion process for the only *.v file in the current directory.

# This script works with these files:
#  - <module_name>_orig.v: The trusted Verilog module to convert. This is the original file for the current conversion step.
#  - <module_name>.v: The current WIP refactored/modified Verilog module, against which FEV will be run.
#  - prompt_id.txt: A file containing, e.g. {"id": 5, "desc": "Update clocks"}, the ID and desc field of the current prompt.
#                  (Formerly, this was just an ID number.) (Note, the actual prompt may have been modified manually.)
#  - messages.<api>.json: The messages to be sent to the LLM API (as in the ChatGPT API).
#  - current/feved.v: A link to the most-recent successfully FEVed Verilog file.
#  - current/chkpt.v: A link to the last checkpointed Verilog file.
# Additionally, these files may be created and captured in the process:
#  - tmp/fev.sby & tmp/fev.eqy: The FEV script for this conversion job.
#  - tmp/m5/*: Temporary files used for M5 preprocessing of a prompt.
#  - tmp/pre_llm.v: The Verilog file sent to the LLM API.
#  - tmp/llm_resp.v: The Verilog response field from the LLM (if any).
#  - tmp/diff.v: The diff of pre_llm.v and llm_resp.v (if response contained Verilog field).
#  - tmp/diff_mod.v: A modification of diff.v to ignore "..." diffs (if response contained Verilog field).
#  - tmp/llm_upd.v: The updated Verilog file after applying diff_mod.v (if response contained Verilog field).
#  - tmp/llm.v: The updated (or not) Verilog (llm_upd.v or pre_llm.v).
#  - llm_response.txt: The LLM response file.
#
# A history of all refactoring steps is stored in history/#, where "#" is the "refactoring step", starting with history/1.
# This directory is initialized when the step is begun, and fully populated when the refactoring change is accepted.
# Contents includes:
#   - history/#/prompt_id.txt: As above
#   - history/#/<module_name>.v: The refactored file at each step.
#   - history/#/messages.<api>.json: The messages sent to the LLM API for each step.
# Although Git naturally captures a history, it may be desirable to capture this folder in Git, simply for convenience, since it may be desirable to
# easily examine file differences or to rework the conversion steps after the fact.
#
# Each refactoring step may involve a number of individual code modifications, recorded in a modification history within the refactoring step directory.
# Each modification is captured, whether accepted, rejected, or reverted.
#
# A modification is stored in history/#/mod_#/ (where # are sequential numbers).
# Contents include:
#   - history/#/mod_#/<module_name>.v: The modified Verilog file.
#   - history/#/mod_#/messages.<api>.json: The messages sent to the LLM API (for LLM modifications only).
#   - history/#/mod_#/status.json: Metadata about the modification, as below, written after testing.
#
# history/#/mod_0 are checkpoints of the initial code for each refactoring step. Thus, history/1/mod_0/<module_name>.v is the initial
# code for the entire conversion.
#
# history/#/mod_# can also be a symlink to a prior history/#/mod_#, recording a code reversion. A reversion will not reference
# another reversion.
#
# The status.json file reflects the status of the modification, including the following (and others that are sticky):
#   {
#     "by": "human"|"llm",
#     "api": ... if "by" is "llm",
#     "compile": "passed"|"failed" (or non-existent if not compiled),
#     "fev": "passed"|"failed" (or non-existent if not run),
#     "incomplete": true|false A sticky field (held for each checkpoint of the refactoring step) assigned or updated by each LLM run,
#                              indicating whether the LLM response was incomplete.
#     "accepted": true|non-existent Exists as true for the final modification of a refactoring step that was accepted.
#   }
#
# With each rejected refactoring step, a new candidate is captured under a new candidate number under the next history number directory.
#
# <repo>/prompts.json contains the default prompts used for refactoring steps as a JSON array of objects with the following fields:
#   - desc: a brief description of the refactoring step
#   - backgroud: (opt) background information that may be relevant to this refactoring step
#   - prompt: prompt string, preprocess using M5 (if necessary), passing M5 variables from sticky fields
#   - must_produce: (opt) an array of strings representing sticky fields that the LLM must produce in its response
#   TODO: Eliminate "may_produce" (since JSON schema has only required fields).
#   - may_produce: (opt) an array of strings representing sticky fields that the LLM may produce in its response.
#   - if: (opt) an object with fields that represent values of sticky fields; if given and any match, this prompt will be used ("" matches undefined)
#         Each field may have an array value rather than a string, in which case any array value may match.
#   - unless: (opt) an object with fields that represent values of sticky fields; if given, unless all match, this prompt will be used ("" matches undefined)
#             Each field may have an array value rather than a string, in which case any array value may match.
#   - needs: (opt) an array of strings representing sticky fields whose values are to be reported in the prompt
#   - consumes: (opt) an array of strings representing sticky fields that are consumed by this prompt
#   TODO: Is "consumes" implemented? Do not consume if "incomplete". Consume even if skipped.
#
# When launched, this script first determines the current state of the conversions process. This state is:
#   - The current candidate:
#     - The current refactoring step, which is the latest history/#.
#     - The next candidate number, which is the next history/#/mod_#
#     - The next prompt ID, which is the ID of the prompt for the current refactoring step. This is the next prompt ID following the
#       most recent that can be found in history/#/.
#   Note that history/#/mod_#/ can be traced backward to determine what has been done so far.

#
# This is a command-line utility which prompts the user for input. Edits to <module_name>.v can be made manually.
# It is suggested to have <module_name>.v open in an editor and in a diff utility, such as meld (prompted and launched by this script), while running this script.
# Additionally, messages.<api>.json (and the "plan" field of status.json) may be modified manually before running the LLM. Users
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
from dotenv import load_dotenv
import json
import re
import shutil
import stat
import copy
import google.generativeai as genai
import anthropic

# Confirm that we're using Python 3.7 or later (as we rely on dictionaries to be ordered).
if sys.version_info < (3, 7):
  print("Error: This script requires Python 3.7 or later.")
  sys.exit(1)

# Load environment variables from .env file.
load_dotenv()


#############
#           #
#  Classes  #
#           #
#############


# Lock a file to prevent writing, as:
# with FileLocked("file.txt"):
#   # Do stuff with file.txt
class FileLocked:
    def __init__(self, filepath):
        self.filepath = filepath
        self.original_permissions = None

    def __enter__(self):
        # Get the current permissions
        self.original_permissions = os.stat(self.filepath).st_mode
        # Remove write permissions (make file read-only)
        os.chmod(self.filepath, self.original_permissions & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Restore original permissions
        os.chmod(self.filepath, self.original_permissions)



# Abstract Base Class for LLM API.
class LLM_API(ABC):
  name = "LLM"
  model = None

  def __init__(self):
    pass

  def setDefaultModel(self, model):
    self.validateModel(model)
    self.model = model

  def validateModel(self, model):
    print("Error: Model " + model + " not found.")
    fail()

  # Run the LLM API on the prompt file, producing a (TL-)Verilog file.
  @abstractmethod
  def run(self, messages, verilog, model):
    pass



# A class responsible for bundling messages objects into text and visa versa.
# This class isolates the format of LLM messages from the functionality and enables message formats to be used
# that are optimized for the LLM.
class MessageBundler:
  # TODO: Unused. Was this being added, or never needed?
  # Convert the given object to text.
  # The object format is:
  #   {
  #     "desc": "This is a description.",
  #     "background": (optional) "This is background information.",
  #     "prompt": "This is a prompt.\n\nIt has multiple lines."
  #   }
  @abstractmethod
  def obj_to_content(self, json):
    pass

  # TODO: Unused. Was this being added, or never used?
  # Convert the given LLM response text into an object of the form:
  #   {
  #     "overview": "This is an overview.",
  #     "verilog": "This is the Verilog code.",
  #     "notes": "These are notes.",
  #     "issues": "These are issues.",
  #     "incomplete": true,
  #     "plan": "Since changes are incomplete, this is the plan for completing the step."
  #   }
  @abstractmethod
  def content_to_obj(self, content):
    pass

  # Add Verilog to last message to be sent to the API.
  # messages: The messages.<api>.json object in OpenAI format.
  # verilog: The current Verilog file contents.
  @abstractmethod
  def add_verilog(self, messages, verilog):
    pass


# An LLM API class for OpenAI's ChatGPT API.
class OpenAI_API(LLM_API):
  name = "OpenAI"
  model = "gpt-3.5-turbo"   # default model (can be overridden in run(..))
                            # Reasoning models: "o1-preview", "o1-mini"

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
    models = self.client.models
    self.models = self.client.models.list()
  
  def validateModel(self, model):
    # Get the data for the model (or None if not found)
    model_data = next((item for item in self.models.data if hasattr(item, 'id') and item.id == model), None)
    if model_data is None:
      print("Error: Model " + model + " not found.")
      fail()

  # Set up the initial messages object for the current refactoring step based on the given system message and message parameter.
  def initPrompt(self, api, system, message):   
    return [
      {"role": apis[api]['system_role'], "content": system},
      {"role": "user", "content": message}
    ]


  # Run the LLM API on the messages.<api>.json file appended with the verilog code, returning the response string from the LLM.
  def run(self, messages, verilog, model=None):
    if model == None:
      model = self.model
    self.validateModel(model)
    
    # Add verilog to the last message.
    get_message_bundler_for_model(model).add_verilog(messages, verilog)
    api_properties = apis[models[model]["api"]]

    # Call the API.
    # TODO: Consider the new "prediction" parameter (https://platform.openai.com/docs/api-reference/chat/create#chat-create-prediction).
    print("\nCalling " + model + "...")
    desired_max = 8000
    max_completion_tokens = api_properties.get('max_output_tokens')
    if (max_completion_tokens is not None) and max_completion_tokens > desired_max:
      max_completion_tokens = desired_max
    #-api_response = self.client.chat.completions.create(model=model, messages=messages, max_completion_tokens=4096)
    
    my_json_schema = copy.deepcopy(json_schema)
    # Add extra_fields to my_json_schema.
    if "must_produce" in prompts[prompt_id]:
      # Add extra_fields to the schema.
      my_json_schema["schema"]["properties"]["extra_fields"] = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
        "required": []
      }
      my_json_schema["schema"]["required"].append("extra_fields")
      # Add the extra fields to the schema.
      for field in prompts[prompt_id]["must_produce"]:
        my_json_schema["schema"]["properties"]["extra_fields"]["properties"][field] = \
          {"type": "string"}   # (Prompt format does not provide a description.)
        my_json_schema["schema"]["properties"]["extra_fields"]["required"].append(field)

    params = {
        "model": model,
        "messages": messages,
        "max_completion_tokens": max_completion_tokens,
        "response_format": {
          "type": "text"
        }
    }
    if api_properties["format"] == "json":
      if api_properties["structured"]:
        # Use structured JSON.
        params["response_format"] = {
          "type": "json_schema",
          "json_schema": copy.deepcopy(my_json_schema)
        }
      else:
        # Structured Output is not supported.
        params["response_format"] = {
          "type": "json_object"
        }
    api_response = self.client.chat.completions.create(**params)

    print("Response received from " + model)

    # Parse the response.
    try:
      if api_response.choices[0].message.refusal:
        print("Error: LLM refused to provide a complete response with the following message:")
        print("       " + api_response.choices[0].message.content + "\n")
        response_str = ""
      else:
        response_str = api_response.choices[0].message.content
        finish_reason = api_response.choices[0].finish_reason
        completion_tokens = api_response.usage.completion_tokens
        print("API response finish reason: " + finish_reason)
        print("API response completion tokens: " + str(completion_tokens))
    except Exception as e:
      print("Error: API response is invalid.")
      print(str(e))
      fail()
    return response_str


# An LLM API class for Google's Gemini API
class Gemini_API(LLM_API):
  name = "Gemini"
  model = "gemini-2.5-pro-exp-03-25"  # default model (can be overridden in run(..))

  def __init__(self):
    super().__init__()

    # if GOOGLE_API_KEY env var does not exist, get it from ~/.google/key.txt or input prompt.
    if not os.getenv("GOOGLE_API_KEY"):
      key_file_name = os.path.expanduser("~/.google/key.txt")
      if os.path.exists(key_file_name):
        with open(key_file_name) as file:
          os.environ["GOOGLE_API_KEY"] = file.read()
      else:
        os.environ["GOOGLE_API_KEY"] = input("Enter your Google API key: ")

    # Initialize the Gemini client
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    self.models = list(genai.list_models())
    self.model_ids = [m.name.replace("models/", "") for m in self.models]
  
  def validateModel(self, model):
    # Check if model is in available models
    if model not in self.model_ids:
      print(f"Error: Model {model} not found in available Gemini models.")
      fail()

  # Set up the initial messages object for the current refactoring step based on the given system message and message parameter.
  def initPrompt(self, api, system, message):
    # For Gemini, we format differently than OpenAI
    return [
      {"role": "user", "parts": [system + "\n\n" + message]}
    ]

  # Run the LLM API on the messages, returning the response string from the LLM.
  def run(self, messages, verilog, model=None):
    if model == None:
      model = self.model
    self.validateModel(model)
    
    # Add verilog to the last message.
    get_message_bundler_for_model(model).add_verilog(messages, verilog)
    api_properties = apis[models[model]["api"]]
    
    print(f"\nCalling {model}...")
    
    try:
      # Convert OpenAI format messages to Gemini format
      gemini_messages = []
      for msg in messages:
        if msg["role"] == "system":
            gemini_messages.append({"role": "system", "parts": [msg["content"]]})
        elif msg["role"] == "user":
            gemini_messages.append({"role": "user", "parts": [msg["content"]]})
        else:
            gemini_messages.append({"role": "model", "parts": [msg["content"]]})
      
      # Create Gemini model with appropriate parameters
      generation_config = {
        "temperature": 0.0,
        "response_mime_type": "text/plain"
      }
      
      if api_properties["format"] == "json":
        generation_config["response_mime_type"] = "application/json"
      
      # Call the Gemini API
      model_instance = genai.GenerativeModel(
        model_name=model,
        generation_config=generation_config
      )
      
      response = model_instance.generate_content(gemini_messages)
      response_str = response.text
      
      print(f"Response received from {model}")
      print(f"API response length: {len(response_str)}")
      
      return response_str
      
    except Exception as e:
      print("Error: API response is invalid.")
      print(str(e))
      fail()
      return ""

# An LLM API class for Anthropic's Claude API.
class Claude_API(LLM_API):
  name = "Claude"
  model = "claude-sonnet-4-20250514"  # default model (can be overridden in run(..))

  def __init__(self):
    super().__init__()

    # If ANTHROPIC_API_KEY env var does not exist, try ~/.anthropic/key.txt or prompt.
    if not os.getenv("ANTHROPIC_API_KEY"):
      key_file = os.path.expanduser("~/.anthropic/key.txt")
      if os.path.exists(key_file):
        with open(key_file) as file:
          os.environ["ANTHROPIC_API_KEY"] = file.read().strip()
      else:
        os.environ["ANTHROPIC_API_KEY"] = input("Enter your Claude API key: ")

    # Init Anthropic client.
    self.client = anthropic.Anthropic()

    # Get available models from API
    try:
      self.models = [m.id for m in self.client.models.list()]
    except Exception as e:
      print("Error retrieving Claude models from API:")
      print(e)
      self.models = []


  def validateModel(self, model):
    if model not in [m for m in self.models]:
      print("Error: Model " + model + " not found.")
      fail()

  def initPrompt(self, api, system, message):
    return [
      {"role": apis[api]["system_role"], "content": system},
      {"role": "user", "content": message}
    ]

  def run(self, messages, verilog, model=None):
    if model is None:
        model = self.model
    self.validateModel(model)

    get_message_bundler_for_model(model).add_verilog(messages, verilog)
    api_props = apis[models[model]["api"]]

    system_prompt = ""
    claude_messages = []
    for m in messages:
        if m["role"] == "system":
            system_prompt = m["content"]
        else:
            claude_messages.append({
                "role": m["role"],
                "content": m["content"]
            })

    max_tokens = api_props.get("max_output_tokens", 4096)
    if max_tokens > 8000:
        max_tokens = 8000

    print("\nCalling " + model + "...")
    try:
        response = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=claude_messages
        )
        print("Response received from " + model)

        raw = response.content[0].text

        # Remove ```json ... ``` wrapper if present
        if raw.strip().startswith("```json"):
            raw = raw.strip()
            raw = raw[len("```json"):].strip()
            if raw.endswith("```"):
                raw = raw[:-3].strip()

        return raw  

    except Exception as e:
        print("Error during Claude API call:")
        print(e)
        fail()


# A message bundler that converts messages to and from the pseudo-Markdown format used in LLM messages.
class PseudoMarkdownMessageBundler(MessageBundler):
  # Convert the given object to a pseudo-Markdown format. Markdown syntax is familiar to the LLM, and fields can be
  # provided without any awkward escaping and other formatting, as described in default_system_message.txt.
  # Example JSON:
  #   {"prompt": "Do this...", "verilog": "module...\nendmodule"}
  # Example output:
  #   ## prompt
  #   
  #   Do this...
  #   
  #   ## verilog
  #   
  #   module...
  #   endmodule
  def obj_to_request(self, obj):
    content = ""
    separator = ""
    for key in obj:
      content += separator + "## " + key + "\n\n" + obj[key]
      separator = "\n\n"
    return content

  """
  # TODO: Maybe this notion of sections should be replaced with an option for responses to
  # use "\n...\n" to omit portions of code. Yes... do this!
  #
  # Split a Verilog file into sections delimited by "// LLM: [Omitted ]Section: <name>"
  # (as described in default_system_message.txt).
  # body: The Verilog code from a "verilog" field of an LLM request or response.
  # response: A boolean indicating whether the body is a response (vs. request).
  def split_sections(self, body, response):
    # Match sections, delimited by "// LLM: Section: <name>".
    sections = re.split(r"\/\/ LLM:\s*(Omitted)?\s*Section:\s*([^\n]+)\n", body)
    # Give the first section a name if it is missing.
    if (sections[0] == ""):
      # Delete the first empty string.
      del sections[0]
    else:
      # Add an empty name and not-omitted to the first section.
      sections.insert(0, "")  # Name
      sections.insert(0, "")  # Not omitted
    # List should contain an even number of elements.
    if len(sections) % 3 != 0:
      print("Bug: Section splitting failed.")
      fail()
    
    # Convert the list to dictionaries of code and omitted.
    ret_code = {}
    ret_omitted = {}
    for i in range(0, len(sections), 3):
      omitted = sections[i] == "Omitted"
      name = sections[i + 1]
      code = sections[i + 2]
      ret_code[name] = code
      ret_omitted[name] = omitted
      # Requests cannot have Omitted sections. Omitted sections cannot contain code.
      if omitted:
        if response:
          if code != "":
            print("Warning: Verilog of response has an omitted section with code.")
        else:
          print("Warning: Verilog of request has an omitted section.")
    
    return [ret_code, ret_omitted]
  """
    
  # Convert the given LLM API response string from the pseudo-Markdown format requested into an object, as described
  # in default_system_message.txt.
  # response: The response string from the LLM API.
  # verilog: The original Verilog code, needed to reconstruct sections that are omitted in the response.
  def response_to_obj(self, response, verilog):
    # Parse the response, line by line, looking for second-level Markdown header lines.
    lines = response.split("\n")

    # No trailing newline.
    if lines[-1] == "":
      del lines[-1]

    # o1-mini likes to put the entire response in block quotes or "-------". Fine. Strip them.
    if len(lines) > 2 and lines[0] == lines[-1] and re.match(r"^(```|---+)$", lines[0]):
      lines = lines[1:-1]

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
        # "verilog" field should not be in block quotes, but it's hard to convince the LLM, so strip them if present.
        if field == "verilog":
          body, n = re.subn(r"^```(verilog)?\n(.*)\n+```\n?$", r"\2\n", body, flags=re.DOTALL)
          if n != 0:
            print("Warning: The \"verilog\" field of the response was contained in block quotes. They were stripped.")
          
          """
          # Split the request and response Verilog into sections.
          [response_sections, response_omitted] = self.split_sections(body, True)
          [orig_sections, orig_omitted] = self.split_sections(verilog, False)
          
          # Reconstruct the full response Verilog, adding omitted sections from the original Verilog.
          body = ""
          for name, code in response_sections.items():
            if name:
              body += "// LLM: Section: " + name + "\n"
            omitted = response_omitted[name]
            # Add the section from the original Verilog if it was omitted.
            if omitted:
              body += orig_sections[name]
            else:
              body += code
          """
          body = ChangeMerger.merge_verilog_changes(body, verilog)

        # Boolean responses.
        if body == "true" or body == "false":
          body = body == "true"
        # Capture the field body.
        fields[field] = body
        
      if l < len(lines):
        # Parse the header line with a regular expression.
        field = re.match(r"## +(\w+)", lines[l]).group(1)

        field = self.validate_field_name(field)

        # Done with this header line.
        l += 1
    
    return fields
  

  # Validate/correct field name.
  # field: The field name to validate.
  # return: The corrected field name.
  # TODO: Checking is automatic with Open API Structured Output.
  def validate_field_name(self, field):
    # The field name should be a lower-case words with underscore delimitation.
    if not re.match(r"[a-z_]*", field):
      print("Warning: The following malformed field name was found in the response:")
      print(field)

    # Convert field name to lower case.
    field = field.lower()
      
    # Check for legal field name.
    if field not in response_fields | set(prompts[prompt_id].get("must_produce", [])) | set(prompts[prompt_id].get("may_produce", [])):
      print("Warning: The following non-standard field was found in the response:")
      print(field)
    
    return field


  # Add Verilog to last message to be sent to the API.
  # messages: The messages.<api>.json object in OpenAI format.
  # verilog: The current Verilog file contents.
  def add_verilog(self, messages, verilog):
    # Add verilog to the last message.
    messages[-1]["content"] += "\n\n## verilog\n\n" + verilog


# A message bundler for Open AI APIs that support JSON ("Structured Outputs").
# Requests use the same format. Only responses are JSON.
class JsonMessageBundler(PseudoMarkdownMessageBundler):

  # Convert the given LLM API response to JSON.
  # And, in this case, it already is JSON.
  # Parameters:
  #   response: The response string from the LLM API.
  #   verilog: The original Verilog code, needed to reconstruct sections that are omitted in the response.
  def response_to_obj(self, response, verilog):
    try:
      response = json.loads(response)
    except Exception as e:
      print("Error: API response is not valid JSON.")
      print(str(e))
      fail()

    # Process the "verilog" field (expanding "..." lines).
    if (response.get("verilog") is not None):
      response["verilog"] = ChangeMerger.merge_verilog_changes(response["verilog"], verilog)
    
    # Validate field names.
    for field in response:
      self.validate_field_name(field)
    
    return response


# A class for incorporating changes from the LLM into the Verilog file.
#
# Request to the LLM include Verilog file contents.
# Responses from the LLM include updated Verilog. This Verilog need not be provided in its entirety. "..." lines
# can be used by the LLM to represent unchanged portions of the file.
# We rely of diff and patch to reconstruct the full updated Verilog file as follows:
#   1) We use diff to identify the changes, including the replacement of sections of code with "..." lines.
#   2) We modify the diff file to remove the "..." substitutions.
#   3) We apply the modified diff file to the original Verilog file to produce the updated Verilog file.
class ChangeMerger:
  hunk_header_re = re.compile(r'^@@ -(\d+),(\d+) \+(\d+),(\d+) @@')
  
  # Helper for adjust_diff (below) to write a hunk to the output file after adjusting its header.
  def write_hunk(hunk, outfile, orig_offset):
    # This is now handled by skip_hunk.
    #if not any(line.startswith(('+', '-')) for line in hunk[1:]):  # Check if hunk has changes
    #  return  # Skip empty hunks

    # Adjust the hunk header
    match = ChangeMerger.hunk_header_re.match(hunk[0])
    if match:
      orig_start, orig_orig_len, mod_start, orig_mod_len = map(int, match.groups())
      # Adjust starting line numbers and lengths
      orig_start += orig_offset
      #mod_start += mod_offset
      new_orig_len = sum(1 for line in hunk[1:] if line.startswith(('-', ' ')))
      new_mod_len = sum(1 for line in hunk[1:] if line.startswith(('+', ' ')))
      # mod_len should not change
      if new_mod_len != orig_mod_len:
        print("Bug: Hunk header length mismatch.")
        fail()
      hunk[0] = f"@@ -{orig_start},{new_orig_len} +{mod_start},{new_mod_len} @@\n"
    outfile.writelines(hunk)
    return new_orig_len - orig_orig_len
  

  # Create a modified diff file, removing "..." deltas.
  # Note that the diff is created in reverse, so that the "..." lines will come first,
  # for easier processing.
  #
  # Deltas are modified as in the following example:
  #  -...
  #  +// omitted
  #  +// code
  #  +// block
  # becomes:
  #   // omitted
  #   // code
  #   // block
  #
  # Hunk header lines are formatted as:
  #  @@ -orig_start,orig_len +mod_start,mod_len @@
  # The modifications reflect a change in the original (LLM response) file that affect
  # headers as follows:
  #   - Orig_len is recalculated for each hunk.
  #   - Subsequent hunks are adjusted as follows:
  #  3-1 is added to this and all subsequent hunk header's original (LLM response) line
  #  number and length.
  #
  # Parameters:
  #   input_diff: The original diff file path.
  #   output_diff: The modified diff file path.
  # Returns:
  #   Success (True) or failure (False).
  def adjust_diff(input_diff, output_diff):
    success = True
    hunk = []  # Lines of the current hunk before writing it out with adjusted header
    skip_hunk = True  # Skip hunks with no deltas
    llm_line_offset = 0  # Tracks offset adjustments for the original (LLM response) file
    #-pre_llm_line_offset = 0  # Tracks offset adjustments for the modified (pre-LLM) file

    with open(input_diff, 'r') as infile, open(output_diff, 'w') as outfile:
      line_type = "file_header"
      for line in infile:
        if ChangeMerger.hunk_header_re.match(line):
          # Handle the previous hunk
          if not skip_hunk:
            llm_line_offset += ChangeMerger.write_hunk(hunk, outfile, llm_line_offset)
          hunk = []  # Start a new hunk
          skip_hunk = True  # Reset skip flag
          line_type = "keep"
        elif line_type == "file_header":
          # Haven't reached the first hunk yet.
          outfile.write(line)
          # line_type remains "file_header".
        #elif line.startswith('-...'):
        elif re.match(r'^-\s*\.\.\.', line):  # LLMs like to indent, so allow whitespace.
          if line_type != "keep":
            print("Error: Failed to reconstruct '...' line from LLM Verilog response.")
            print("       (The LLM didn't provide enough context before omitted text.)")
            success = False
            break
          # Update offsets when skipping removed lines
          #llm_line_offset -= 1
          line_type = "..."
        elif line.startswith('+'):
          if line_type == "..." or line_type == "omitted":
            # Change line from "+" prefix to " " prefix.
            line = line.replace('+', ' ', 1)
            # This line was omitted from original (LLM response) and we're adding it back.
            #llm_line_offset += 1
            line_type = "omitted"
          else:
            skip_hunk = False
            line_type = "+"
        elif line.startswith('-'):
          if line_type == "...":
            print("Error: Failed to reconstruct '...' line from LLM Verilog response.")
            print("       (The LLM didn't provide enough context after omitted text.)")
            success = False
            break
          else:
            skip_hunk = False
            line_type = "-"
        else:
          # No delta (context) line.
          line_type = "keep"
        if line_type != "..." and line_type != "file_header":
          hunk.append(line)

      # Handle the final hunk
      if not skip_hunk:
        ChangeMerger.write_hunk(hunk, outfile, llm_line_offset)

    return success
  # Parameters:
  #   orig_file: The original file path.
  #   modified_file: The modified file path (including "..." lines).
  #   diff_file: The path for the diff file.
  #   modified_diff_file: The path for the modified diff file.
  #   output_file: The output file path.
  # Returns:
  #   Success
  def merge_changes(orig_file, modified_file, diff_file, modified_diff_file, output_file):
    # Create a diff file between the original and modified files.
    status = os.system(f"diff -u {modified_file} {orig_file} > {diff_file}")
    if status != 0:
      # Adjust the diff file to remove "..." substitutions.
      if ChangeMerger.adjust_diff(diff_file, modified_diff_file):
        # Apply the modified diff file to the original file to produce the output file.
        rslt = run_command(['patch', '-R', '-o', output_file, orig_file, modified_diff_file])
        if rslt.returncode == 0:
          return True
    else:
      # No diff.
      shutil.copyfile(orig_file, output_file)
    return False
  
  # Merge updated Verilog changes.
  # Parameters:
  #   body: The updated Verilog file contents with "..." lines.
  #   verilog: The original Verilog file contents.
  # Return:
  #   The updated Verilog file contents, or False on error.
  def merge_verilog_changes(body, verilog):
    # Make sure the Verilog code ends with a newline (because we pattern match lines ending in newline).
    if body != "" and body[-1] != "\n":
      body += "\n"

    with open("tmp/llm_resp.v", "w") as f:
      f.write(body)
    if body == "...\n":
      # Won't use intermediate files. Delete them (if they exist) to avoid confusion.
      if os.path.exists("tmp/diff.txt"):
        os.remove("tmp/diff.txt")
      if os.path.exists("tmp/diff_mod.txt"):
        os.remove("tmp/diff_mod.txt")
      if os.path.exists("tmp/llm_upd.v"):
        os.remove("tmp/llm_upd.v")
      body = verilog
    else:
      if ChangeMerger.merge_changes("tmp/pre_llm.v", "tmp/llm_resp.v", "tmp/diff.txt", "tmp/diff_mod.txt", "tmp/llm_upd.v"):
        with open("tmp/llm_upd.v") as f:
          body = f.read()
      else:
        body = False
    return body




###############
#             #
#  Functions  #
#             #
###############


###########
# Generic #
###########


# Run a system command, reporting the error if it fails and produces stderr output.
# Return the same structure as subprocess.run.
def run_command(cmd):
  rslt = subprocess.run(cmd, capture_output=True, text=True)
  if (rslt.returncode != 0) and rslt.stderr:
    print("Error: Command failed.")
    print("       '" + " ".join(cmd) + "' failed as follows:")
    print(rslt.stderr)
  return rslt



##################
# Usage and Exit #
##################


# Report a usage message.
def usage():
  print("Usage: python3 .../convert.py")
  print("  Call from a directory containing a single Verilog file to convert or a \"history\" directory.")
  fail()


def fail():
  sys.exit(1)

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


# Catch signals for proper cleanup.

# Define a handler for signals that will perform cleanup
def signal_handler(signum, frame):
    print(f"Caught signal {signum}, exiting...")
    sys.exit(1)

# Register the signal handler for as many signals as possible.
for sig in [signal.SIGABRT, signal.SIGINT, signal.SIGTERM]:
    signal.signal(sig, signal_handler)


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


# Prompt the user for a single char input (single keypress).
def prompt_user(prompt, options=None, default=None):
  p = prompt
  if options:
    p += " [" + "/".join(options) + "]"
    if default:
      p += " (default: " + default + ")"
  print(p)
  while True:
    again = False
    print("> ", end="")
    ch = getch()
    print("")
    # if ch isn't among the options, use default if there is one.
    if options and ch not in options:
      if default:
        ch = default
      else:
        print("Error: Invalid input. Try again.")
        again = True
    if not again:
      return ch


# Accept terminal input command character from among the given list.
def get_command(options):
  while True:
    print("")
    ch = prompt_user("Press one of the following command keys: " + ", ".join(options))
    if ch not in options:
      print("Error: Invalid key. Try again.")
    else:
      return ch

# Pause for a key press.
def press_any_key(note=""):
  print("Press any key to continue...%s\n>" % note, end="")
  getch()
  print("")



###################
# File Operations #
###################

# Determine if a filename has a Verilog/SystemVerilog extension.
def is_verilog(filename):
  return filename.endswith(".v") or filename.endswith(".sv")

def diff(file1, file2):
  return os.system("diff -q '" + file1 + "' '" + file2 + "' > /dev/null") != 0

def copy_if_different(src, dest):
  if diff(src, dest):
    shutil.copyfile(src, dest)

# Read the prompt ID from the given file.
def read_prompt_id(file):
  prompt_id = json.loads(f.read())
  # Two formats are supported. This is either a number or {"id": number, "desc": "description"}.
  if type(prompt_id) == dict:
    # Verify that the description matches the prompt.
    desc = prompt_id["desc"]
    id = prompt_id["id"]
    if prompts[id]["desc"] != desc:
      # Prompts have changed. See if we can identify the proper ID by looking up the description in prompts_by_desc.
      prompt_id_str = "{" + str(prompt_id["id"]) + ", " + prompt_id["desc"] + "}"
      if desc in prompts_by_desc:
        id = prompts_by_desc[desc]["index"]
        # Report the correction.
        print("Warning: Prompts have been changed. Corrected ID " + prompt_id_str + " to " + str(id) + " for current prompt: \"" + desc + "\".")
      else:
        print("\nError: The description in \"prompt_id.txt\" does not match any prompt description in prompts.json.")
        print("       The description in \"prompt_id.txt\" is: \"" + desc + "\".")
        print("       The descriptions for ID " + prompt_id_str + " in prompts.json is:" + prompts[prompt_id]["desc"] + "\".")
        # Continue?
        ch = prompt_user("Continue with the current prompt ID?", {"y", "n"}, "n")
        if ch == "n":
          fail()
    # Correct the prompt ID.
    prompt_id = id
  return prompt_id



###################################
# Working with Status and History #
###################################

def changes_pending():
  return os.path.exists(mod_path() + "/" + working_verilog_file_name) and diff(working_verilog_file_name, mod_path() + "/" + working_verilog_file_name)


# See if there were any manual edits to the Verilog file and capture them in the history if so.
def checkpoint_if_pending():
  # if latest mod file exists and is different from working file, checkpoint working file.
  if changes_pending():
    print("Manual edits were made and are being checkpointed.")
    checkpoint({ "by": "human" })

# Functions that determine the state of the refactoring step based on the state of the files.
# TODO: replace?
#def llm_passed():
#  return os.path.exists(llm_verilog_file_name)

def llm_finished():
  return not readStatus().get("incomplete", True)

def fev_passed():
  return os.path.exists("fev/PASS") and os.system("diff " + module_name + ".v fev/src/" + module_name + ".v") == 0

def update_chkpt():
  os.system("ln -sf ../" + mod_path() + "/" + working_verilog_file_name + " current/chkpt.v")

def update_feved():
  os.system("ln -sf ../" + most_recently_feved_verilog_file() + " current/feved.v")

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

def most_recently_feved_verilog_file():
  last_fev_mod = most_recent(lambda mn: (readStatus(mn).get("fev") == "passed"))
  assert(last_fev_mod is not None)
  return mod_path(last_fev_mod) + "/" + working_verilog_file_name

# Number of the most recent modification (that actually made a change) or None.
def most_recent_mod():
  return most_recent(lambda mod: (readStatus(mod).get("modified", False)))

# The path of the latest modification of this refactoring step.
def mod_path(mod = None):
  # Default mod to mod_num
  if mod is None:
    mod = mod_num
  return "history/" + str(refactoring_step) + "/mod_" + str(mod)


# Set mod_num to the maximum for the current refactoring step.
def set_mod_num():
  global mod_num
  mod_num = -1
  while os.path.exists(mod_path(mod_num + 1)):
    mod_num += 1


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


# Capture Verilog file in a new history/#/mod_#/, and if this was an LLM modification, capture messages.<api>.json and llm_response.txt.
#  status: The status to save with the checkpoint, updated as new status.
#  old_status: For use only for the first checkpoint of a refactoring step. This is the status from the prior refactoring step.
#  verilog_file: The verilog file to capture (defaulted to working_verilog_file_name and checkpointed as working_verilog_file_name regardless).
# Sticky status is applied from current status. Status["incomplete"] will be carried over from the prior checkpoint for non-LLM updates.
def checkpoint(status, old_status = None, verilog_file = None):
  if verilog_file is None:
    verilog_file = working_verilog_file_name
  global mod_num
  # Carry over sticky status from the prior checkpoint. (Fields not in status_fields are sticky.)
  # Also, carry over "plan" within the refactoring step excluding "llm" checkpoints.
  if mod_num >= 0:
    old_status = readStatus()
  for field in old_status:
    # Some fields are provided by the LLM and are sticky only within the refactoring step.
    if field in llm_status_fields:
      if mod_num >= 0 and status.get("by") != "llm":
        status[field] = old_status[field]
    elif field not in status and field not in status_fields:
      status[field] = old_status[field]
  
  # Capture the current Verilog file in new mod dir and update current/chkpt.v.
  mod_num += 1
  mod_dir = mod_path()
  os.mkdir(mod_dir)
  os.system("cp " + verilog_file + " " + mod_dir + "/" + working_verilog_file_name)

  # Capture messages.<api>.json and llm_response.txt if this was an LLM modification.
  if status.get("by") == "llm":
    api = status.get("api")
    os.system("cp messages." + api + ".json llm_response.txt " + mod_dir)
  
  # Write status.json.
  writeStatus(status)

  # Update current/chkpt.v and current/feved.v links to reflect this new checkpoint.
  update_chkpt()
  update_feved()

  # Make Verilog file read-only (to prevent inadvertent modification, esp. in meld).
  # ("status.json" may still be updated with FEV status.)
  os.system("chmod a-w " + mod_dir + "/" + working_verilog_file_name)


# Create a reversion checkpoint as a symlink, or if the previous change was a reversion, update its symlink.
def checkpoint_reversion(prev_mod):
  global mod_num
  # Prepare to create a new reversion checkpoint.
  if os.path.islink(mod_path()):
    # Remove old reversion symlink.
    os.remove(mod_path())
  else:
    # Must create a new reversion checkpoint.
    mod_num += 1
  # Create reversion symlink.
  os.symlink("mod_" + str(prev_mod), mod_path())
  # Update current/chkpt.v and current/feved.v links to reflect this reversion.
  update_chkpt()
  update_feved()



######################
# Formatting/Parsing #
######################

# Process JSON with newlines in strings into proper JSON.
def from_extended_json(ejson):
  # Iterate over the characters of raw_contents, keeping track of whether we are within a string, and replacing newlines with '\n'.
  # For backward-compatibility with an old syntax, we replace "\n+" as well as "\n" with '\n'.
  json_str = ""
  in_string = False
  after_newline = False
  for c in ejson:
    if after_newline:
      if c == '+':
        after_newline = False
        continue
      after_newline = False
    if c == '"':
      in_string = not in_string
    if c == '\n' and in_string:
      c = '\\n'
      after_newline = True
    json_str += c
  return json_str

# Convert a JSON string into a more readable version with newlines in strings.
def to_extended_json(json_str):
  # Iterate over the characters of the JSON string, keeping track of whether we are within a string, and replacing '\n' with newlines.
  ejson = ""
  in_string = False
  prev_c = None
  for c in json_str:
    if c == '"':
      in_string = not in_string
    if prev_c == '\\' and c == 'n' and in_string:
      prev_c = None
      c = '\n'
    if prev_c != None:
      ejson += prev_c
    prev_c = c
  if prev_c != None:
    ejson += prev_c
  return ejson



##################
# Initialization #
##################


# Initialize messages.<api>.json.
# This is specific to the API, but we do this when initializing the refactoring step (before we know the API)
# to enable human edits before the API call. So we create a different messages.<api>.json file for each possible
# API.
def initialize_messages_json():
  status = readStatus()
  error = False

  # For every API, initialize messages.<api>.json.
  for api in apis:
    try:
      status['api'] = api
      messages_json = "messages." + api + ".json"

      # Dynamically create the correct LLM API instance
      if api.startswith(("gpt3", "gpt4", "gpt5", "o", "o-simple")):
        llm_api = OpenAI_API()
      elif api.startswith("gemini"):
        llm_api = Gemini_API()
      elif api == "claude":
        llm_api = Claude_API()
      else:
        raise ValueError(f"Unknown or unsupported API type: {api}")

      # Read the system message from <repo>/default_system_message.txt.
      with open(repo_dir + "/default_system_message.txt") as file:
        system = file.read()
      # Process with M5.
      system = processWithM5("system_message", api, system, status)

      # Initialize messages.<api>.json.
      with open(messages_json, "w") as message_file:
        prompt = prompts[prompt_id]["prompt"]
        # Search prompt string for "m5_" and use M5 if found.
        if prompt.find("m5_") != -1:
          prompt = processWithM5("prompt", "api", prompt, status)
        # Add "needs" fields to the prompt.
        if "needs" in prompts[prompt_id]:
          prompt += "\n\nNote that the following \"extra fields\" have been determined to characterize the Verilog code:"
          for field in prompts[prompt_id]["needs"]:
            value = str(status.get(field, "UNKNOWN"))
            if value == "UNKNOWN":
              print("Error: The field \"" + field + "\" is needed by the prompt but is not in the status. Using \"UNKNOWN\".")
            prompt += "\n   " + field + ": " + value
        message_obj = {}
        # If prompt has a "background" field, add it (first) to the message.
        if "background" in prompts[prompt_id]:
          message_obj["background"] = prompts[prompt_id]["background"]
        message_obj["prompt"] = prompt
        message = get_message_bundler_for_api(api).obj_to_request(message_obj)
        ejson_messages = to_extended_json(json.dumps(llm_api.initPrompt(api, system, message), indent=4))
        message_file.write(ejson_messages)
    except Exception as e:
      print("Error: Failed to initialize messages." + api + ".json due to: " + str(e))
      error = True
  if error:
    fail()


# Write prompt_id.txt.
def write_prompt_id():
  with open("prompt_id.txt", "w") as file:
    # Make sure there are no double quotes in the description.
    if prompts[prompt_id]["desc"].find('"') != -1:
      print("Error: The description of prompt " + str(prompt_id) + " contains a double quote.")
      fail()
    file.write('{"id": ' + str(prompt_id) + ', "desc": "' + prompts[prompt_id]["desc"] + '"}')


# Initialize the conversion directory for the next refactoring step.
def init_refactoring_step():
  global refactoring_step, mod_num, prompt_id

  # Get sticky status from current refactoring step before creating next.
  old_status = {}
  if refactoring_step <= 0:
    # Test that the code can be parsed by FEV.
    if not run_fev(working_verilog_file_name, working_verilog_file_name, True):
      print("Error: The original Verilog code failed to run through FEV flow.")
      print("Debug using logs in \"fev\" directory.")
      fail()
  else:
    old_status = readStatus()
    
  refactoring_step += 1
  mod_num = -1

  # Find the next prompt that should be executed.
  ok = False
  while not ok:
    prompt_id += 1

    # Check if conditions.
    if_ok = True     # Prompt is okay to execute based on "if" conditions.
    if "if" in prompts[prompt_id]:
      if_ok = False
      for field in prompts[prompt_id]["if"]:
        # If the field is a string, make it an array of one string.
        if type(prompts[prompt_id]["if"][field]) == str:
          prompts[prompt_id]["if"][field] = [prompts[prompt_id]["if"][field]]
        # If any of the values match, the prompt is okay.
        for value in prompts[prompt_id]["if"][field]:
          if value == old_status.get(field, ""):
            if_ok = True
            break
    
    # Check unless conditions.
    unless_ok = True # Prompt is okay to execute based on "unless" conditions.
    if "unless" in prompts[prompt_id]:
      for field in prompts[prompt_id]["unless"]:
        # If the field is a string, make it an array of one string.
        if type(prompts[prompt_id]["unless"][field]) == str:
          prompts[prompt_id]["unless"][field] = [prompts[prompt_id]["unless"][field]]
        # If any of the values match, the prompt is not okay.
        unless_ok = True
        for value in prompts[prompt_id]["unless"][field]:
          if value == old_status.get(field, ""):
            unless_ok = False
            break
        if unless_ok:
          break
    
    ok = if_ok and unless_ok
  
  # Update state in files.

  write_prompt_id()

  # Make history/# directory and populate it.
  os.mkdir("history/" + str(refactoring_step))
  os.system("cp prompt_id.txt history/" + str(refactoring_step) + "/")
  # Also, create an initial mod_0 directory populated with initial verilog and status.json indicating initial code.
  status = { "initial": True, "fev": "passed" }
  checkpoint(status, old_status)
  # (mod_num now 0)

  initialize_messages_json()



#############
# Run Tools #
#############


#
# M5
#

# Process text using M5, setting variables for sticky status fields.
# Produces /tmp/m5/<what>.<api>.txt.m5 and /tmp/m5/<what>.<api>.txt.
# Args:
#   what: A string indicating what we are processing ("system_message", "prompt").
#   body: The text to process.
#   status: The current status object.
def processWithM5(what, api, body, status):
  # Pass fields of status to M5 as var(status_<field>, <value>).
  status_m5 = "m5_use(m5-local)"    # TODO: Requires local environment.
  # Set M5 variables for the api and its properties.
  status_m5 += "m5_var(api, ['" + api + "'])"
  for field in apis[api]:
    status_m5 += "m5_var(api_" + field + ", ['" + str(apis[api][field]) + "'])"
  for field in status:
    status_m5 += "m5_var(status_" + field + ", ['" + str(status[field]) + "'])"
  status_m5 = "m5_eval(" + status_m5 + ")"
  # Run M5.
  # Delete(or not?) and create tmp/m5/.
  #os.system("rm -rf tmp/m5")
  if not os.path.exists("tmp/m5"):
    os.mkdir("tmp/m5")
  # Preppend m5_status to body.
  body = status_m5 + body
  # Write prompt to tmp/m5/prompt.txt.m5.
  with open("tmp/m5/" + what + "." + api + ".txt.m5", "w") as file:
    file.write(body)
  # Run M5.
  os.system(repo_dir + "/M5/bin/m5 --obj_dir tmp/m5 tmp/m5/" + what + "." + api + ".txt.m5 > tmp/m5/" + what + ".txt")
  # Read <what>.txt.
  with open("tmp/m5/" + what + ".txt") as file:
    body = file.read()
  return body


#
# LLM
#

# Checkpoint any manual edits, run LLM, and checkpoint the result if successful. Return nothing.
# messages: The messages.<api>.json object in OpenAI format.
# verilog: The current Verilog file contents.
def run_llm(messages, verilog, model="gpt-3.5-turbo"):

  # Run the LLM, passing the messages.<api>.json and verilog file contents.

  # Confirm.
  print("")
  print("The following prompt will be sent to " + model + "'s API together with the Verilog and prior messages:")
  print("")
  print(messages[-1]["content"])
  print("")
  press_any_key()

  # If there is already a response, prompt the user about possibly reusing it.
  # TODO: Consider using a disk/DB memoization library to cache responses, such as https://grantjenks.com/docs/diskcache/.
  reuse_llm_response = "n"
  if os.path.exists("llm_response.txt"):
    reuse_llm_response = prompt_user("There is already a response to this prompt. Would you like to reuse it [y/N]?")

  # For JSON, we use an "extra_fields" field to hold all the extra fields, otherwise these are flat with others.
  use_extra_fields = apis[models[model]["api"]]["format"] == "json"
  extra_fields = None  # The object containing extra_fields (and maybe other stuff).

  reject = False
  modified = True
  with FileLocked(working_verilog_file_name):
    checkpoint_if_pending()
    # Capture working file as the version we'll send to the LLM.
    os.system("cp " + working_verilog_file_name + " tmp/pre_llm.v")
    # Make writable.
    os.system("chmod a+w " + "tmp/pre_llm.v")
    
    if reuse_llm_response == "y":
      # Use llm_response.txt.
      with open("llm_response.txt") as file:
        response_str = file.read()
    else:
      # Call the API.
      response_str = llm_api.run(messages, verilog, model)
      # Write llm_response.txt (unless refusal).
      if (response_str != ""):
        with open("llm_response.txt", "w") as file:
          file.write(response_str)
    
    reject = response_str == ""


    if not reject:
      # Process the response.
      response_obj = get_message_bundler_for_model(model).response_to_obj(response_str, verilog)

      # "verilog" field is required.
      if "verilog" not in response_obj:
        print("\nError: API response is missing \"verilog\" field.")
        print("Rejecting response.")
        reject = True
      elif not response_obj["verilog"]:
        print("\nError: Failed to process \"verilog\" field in response.")
        print("Rejecting response.")
        reject = True
      else:
        # Check that this prompt produces all requested fields. If it does not, we force rejection.
        if "must_produce" in prompts[prompt_id]:
          if use_extra_fields and not "extra_fields" in response_obj:
            print("Error: API response is missing \"extra_fields\" field.")
            print("Rejecting response.")
            reject = True
          else:
            # Make sure all extra_fields exist in response.
            extra_fields = response_obj if not use_extra_fields else response_obj["extra_fields"]
            for field in prompts[prompt_id]["must_produce"]:
              if field not in extra_fields:
                print("Error: API response is missing required field: " + field)
                print("Rejecting response.")
                reject = True

    if not reject:
      # We haven't forced rejection.
      # Correct and present LLM results.
      
      print("")
      print("The following response was received from the API, to replace the Verilog file:")
      print("")
      # Reformat the JSON into multiple lines and extract the verilog for cleaner printing, then restore it.
      code = response_obj.get("verilog")
      if code:
        response_obj["verilog"] = "See meld."
      print(json.dumps(response_obj, indent=4))
      if code:
        #print("-------------")
        #print(code)
        #print("-------------")
        # Repair the response.
        response_obj["verilog"] = code
      print("")

      # Get working code.
      pre_llm_code = ""
      with open(working_verilog_file_name) as file:
        pre_llm_code = file.read()

      code = response_obj["verilog"]

      # Are there any modifications to the Verilog?
      modified = code != verilog

      # Write tmp/llm.v with updated (or not) Verilog.
      with open("tmp/llm.v", "w") as file:
        file.write(code)

    # Unlock the working file.

  if not reject:
    # Not yet rejected, prompt for edits, accept, reject.

    with open(working_verilog_file_name, "w") as file:
      file.write(code)
    
    # Prompt user to review, correct, and accept or reject the changes.
    done = False
    while not done:
      ch = prompt_user("Verilog updated by LLM. Review in meld ([m] to open), edit as needed, and accept [a] or reject [r] this updated Verilog?", options=["a", "r", "m"], default="a")
      if ch == "m":
        # Open meld.
        cmd = "meld current/feved.v current/chkpt.v " + working_verilog_file_name + " &"
        print("Running: " + cmd)
        os.system(cmd)
      else:
        done = True

    # If rejected, restore the working Verilog file to the previous change.
    # If accepted, checkpoint just the LLM's change first, then, if modified by the user,
    # the user's changes.
    
    # Verilog changes are monitored using meld, comparing working file vs. current/feved.v (read-only symlink).
    # TODO: The above must be maintained through commits and reverts.

    if ch == "a":
      # First checkpoint just the LLM's change.
      if modified:
        print("Checkpointing changes.")
      else:
        # LLM says no changes.
        print("No changes were made for this refactoring step. (Checkpointing anyway.)")
      
      # Checkpoint the LLM's change, whether modified or not.
      orig_status = readStatus()
      status = { "by": "llm", "model": model, "api": api, "incomplete": response_obj.get("incomplete", False), "modified": modified, "initial": False }
      if not modified:
        # Reflect FEV and compile status from prior checkpoint.
        status["compile"] = orig_status.get("compile")
        status["fev"] = orig_status.get("fev")
      # Record plan.
      if "plan" in response_obj:
        status["plan"] = response_obj["plan"]
      # Apply combination of must_produce and may_produce fields to status.
      for field in prompts[prompt_id].get("must_produce", []) + prompts[prompt_id].get("may_produce", []):
        if field in extra_fields:
          status[field] = extra_fields[field]
        
      checkpoint(status, orig_status, "tmp/llm.v")

      # Now, checkpoint the user's changes, if there are any.
      checkpoint_if_pending()

      # Response accepted, so delete llm_response.txt.
      os.remove("llm_response.txt")
    else:
      # Revert to the prior change.
      copy_if_different("tmp/pre_llm.v", working_verilog_file_name)
      print("Changes rejected. Restored to code prior to running LLM.")


#
# FEV
#

# Run SymbiYosys.
def run_sby():
  return subprocess.run(["sby", "-f", "tmp/fev.sby"])

# Run EQY.
def run_eqy():
  return subprocess.run(["eqy", "-f", "tmp/fev.eqy"])

# Run FEV using Yosys on the given top-level module name and orig and modified files.
# Return the subprocess.CompletedProcess of the FEV command.
def run_yosys_fev(module_name, orig_file_name, modified_file_name):
  env = {"TOP_MODULE": module_name, "ORIGINAL_VERILOG_FILE": orig_file_name, "MODIFIED_VERILOG_FILE": modified_file_name}
  return subprocess.run(["yosys", repo_dir + "/fev.tcl"], env=env)


# Run FEV against the given files.
# Return True if FEV passes, False if it fails.
def run_fev(orig_file_name, working_verilog_file_name, use_eqy = True):

  # Create fev.sby or fev.eqy.
  fev_file = "fev.eqy" if use_eqy else "fev.sby"
  # This is done by copying in <repo>/fev.sby and substituting "{MODULE_NAME}", "{ORIGINAL_FILE}", and "{MODIFIED_FILE}" using sed.
  os.system(f"cp " + repo_dir + "/" + fev_file + " tmp")
  os.system(f"sed -i 's/<MODULE_NAME>/{module_name}/g' tmp/" + fev_file)
  # These paths must be absolute.
  os.system(f"sed -i 's|<ORIGINAL_FILE>|{os.getcwd()}/{orig_file_name}|g' tmp/" + fev_file)
  os.system(f"sed -i 's|<MODIFIED_FILE>|{os.getcwd()}/{working_verilog_file_name}|g' tmp/" + fev_file)
  # To run the above manually in bash, as a one-liner from the conversion directory, providing <MODULE_NAME>, <ORIGINAL_FILE>, and <MODIFIED_FILE>:
  #   cp ../fev.sby fev.sby && sed -i 's/<MODULE_NAME>/<module_name>/g' fev.sby && sed -i "s|<ORIGINAL_FILE>|$PWD/<original_file>|g" fev.sby && sed -i "s|<MODIFIED_FILE>|$PWD/<modified_file>|g" fev.sby

  if use_eqy:
    # Run FEV using EQY.
    proc = run_eqy()
  else:
    #proc = run_sby()
    proc = run_yosys_fev(module_name, orig_file_name, working_verilog_file_name)
  
  # Return status.
  # TODO: If failed, bundle failure info for LLM, and call LLM (with approval).
  return proc.returncode == 0

# Run FEV against the last successfully FEVed code (if not in this refactoring step, the original code for this step).
# Checkpoint the code first and FEV vs. this checkpoint.
# Update status.json.
# use_eqy: Use EQY instead of SymbiYosys.
# use_original: Use the original code (history/1/mod_0) instead of the most recently FEVed code.
def fev_current(use_eqy = True, use_original = False):
  
  checkpoint_if_pending()

  checkpointed_verilog_file = mod_path() + "/" + working_verilog_file_name

  # This is a good time to strip temporary comments from the LLM and change New Task comments to Old Task.
  # We've found it sometimes convenient to ask the LLM to insert these so it doesn't forget what it has done.
  os.system("sed -i '/^\s*\/\/\s*LLM:\s*Temporary:.*/d' " + checkpointed_verilog_file)  # Whole line.
  # Also remove these at the end of a line without deleting the line.
  os.system("sed -i 's/^\s*\/\/\s*LLM:\s*Temporary:.*//' " + checkpointed_verilog_file)
  # Change "New Task" to "Old Task".
  os.system("sed -i 's/\/\/\s*LLM:\s*New Task:/\/\/ LLM: Old Task:/' " + checkpointed_verilog_file)

  status = readStatus()
  # Get the most recently FEVed code (mod with status["fev"] == "passed").
  orig_file_name = most_recently_feved_verilog_file() if not use_original else "history/1/mod_0/" + working_verilog_file_name
  
  print("Running FEV against " + orig_file_name + ". Diff:")
  print("==================")
  diff_status = os.system("diff " + orig_file_name + " " + checkpointed_verilog_file)
  print("==================")
  
  ret = False
  # Run FEV.
  if diff_status == 0:
    print("No changes to FEV. Choose a different command.")
    status["fev"] = "passed"
    ret = True
  else:
    # Run FEV.
    ret = run_fev(orig_file_name, checkpointed_verilog_file, use_eqy)

    if ret:
      print("FEV passed.")
      status["fev"] = "passed"
    else:
      print("Error: FEV failed. Try again.")
      status["fev"] = "failed"
  writeStatus(status)
  # Update current/feved.v to link to newly-FEVed code.
  if status["fev"] == "passed":
    update_feved()
   
  return ret


#
# Diff
#

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



#############
# User Flow #
#############

# Print the main user prompt.
def print_prompt():
  print("The current refactoring step (" + str(refactoring_step) + ") for the LLM uses prompt " + str(prompt_id) + ":\n")
  print("   | " + prompts[prompt_id]["desc"].replace("\n", "\n   | "))
  print("  ")
  print("  Make edits and enter command characters until a candidate is accepted or rejected. Generally, the sequence is:")
  print("    - (optional) Make any desired manual edits to " + working_verilog_file_name + " and/or messages.<api>.json.")
  print("    - l/L/m/M: (optional) Run the LLM step. (If this fails or is incomplete, make any further manual edits and try again.)")
  print("    - (optional) Make any desired manual edits to " + working_verilog_file_name + ". (You may use \"f\" to run FEV first.)")
  print("    - e/f: Run FEV (EQY/Yosys). (If this fails, make further manual Verilog edits and try again.).")
  print("    - y: Accept the current code as the completion of this refactoring step.")
  print("  (At any time: use \"n\" to undo changes; \"h\" for help; \"x\" to exit.)")
  print("  ")
  print("  Enter one of the following commands:")
  print("    l: LLM. Run with the default fast model (o4-mini).")
  print("    L: LLM. Run with the high-quality model (gpt-4o).")
  print("    m: LLM. Choose a model from important (recommended) options only.")
  print("    M: LLM. Choose a model from all available options.")
  print("    e/f/E: Run FEV (EQY/Yosys) on the current code (or [E]QY vs. original).")
  print("    y: Yes. Accept the current code as the completion of this refactoring step (if FEV already run and passed).")
  print("    u: Undo. Revert to a previous version of the code.")
  print("    U: Redo. Reapply a reverted code change (possible until next modification or exit).")
  print("    c: Checkpoint the current human edits in the history.")
  print("    p: Apply a specific prompt (out-of-order) from a complete listing.")
  print("    h: History. Show a history of recent changes in this refactoring step.")
  print("    ?: Help. Repeat this message.")
  print("    x: Exit.")
  llm = llm_finished()
  status = readStatus()
  fev = status.get("fev") == "passed"
  if llm or fev:
    print("  Status:")
    if llm:
      print("    The LLM has been run.")
    if fev:
      print("    Code has passed FEV.")


# Reset the current prompt/refactoring-step (which is just starting (by reversion, perhaps)) to a
# fresh one (type "r") or the previous one (type "u"). For "u", update state files.
# TODO: There's no checking that the prompt (for "u") is one that should be executed (according
#       to "if" and "unless").
# Params:
#   type: "u" for unaccept, "r" for reinitialize.
#   prev_prompt_id: The prompt ID of the previous step (to be incremented if "r").
def reset_prompt(type, prev_prompt_id):
  # Unaccept this refactoring step by:
  #   deleting this history directory for this refactoring step
  #   decrementing the refactoring step number
  #   setting the prompt ID
  # If type is "r", reinitialize a new refactoring step (in place of the old one).
  # If type is "u", update status to unaccepted ("u").
  global refactoring_step, prompt_id

  # Delete the history directory.
  shutil.rmtree("history/" + str(refactoring_step))
  # Decrement the refactoring step number.
  refactoring_step -= 1
  set_mod_num()
  prompt_id = prev_prompt_id
  # Update status to unaccepted ("u") or reinitialize the refactoring step ("r").
  if type == "r":
    init_refactoring_step()
    print("\nRefactoring step reset.")
  else:
    # Update state files to reflect the unacceptance.
    initialize_messages_json()
    update_chkpt()
    update_feved()
    write_prompt_id()
    
    # Unaccept.
    status = readStatus()
    status["accepted"] = False
    writeStatus(status)





######################
#                    #
#  Main entry point  #
#                    #
######################


#############
# Constants #
#############


# The various LLM APIs we support and their properties.
# In addition to use by this script, these properties are stringified and passed via M5 to
# default_system_messages.txt.
with open("config/apis.json") as f:
    apis = json.load(f)
with open("config/models.json") as f:
    model_data = json.load(f)
    models = model_data["models"]
    important_models = model_data["important"]

# The JSON schema for the LLM API, which is passed, e.g.:
json_schema = {
  "name": "verilog_refactoring",
  "strict": True,
  "schema": {
    "type": "object",
    "properties": {
      "verilog": {"type": "string", "description": "The refactored Verilog code (with \"...\" lines representing omitted unchanged code)."},
      "overview": {"type": "string", "description": "A brief overview of the changes."},
      "incomplete": {"type": "boolean", "description": "Whether further refactoring is required for this refactoring step."},
      "issues": {"type": "string", "description": "Any issues encountered during refactoring."},
      "notes": {"type": "string", "description": "Any notes for the user about the refactoring."},
      "plan": {"type": "string", "description": "The plan for completing this refactoring step if incomplete."},
    },
    "required": ["verilog", "overview", "incomplete", "issues", "notes", "plan"],
    "additionalProperties": False
  }
}


# Response fields.
response_fields = {"overview", "verilog", "notes", "issues", "incomplete", "plan", "extra_fields"}    # ("incomplete" is sticky between LLM runs, so it has special treatment.)
status_fields = {"by", "api", "compile", "fev", "modified", "incomplete", "accepted", "plan"}  # Status fields that are not sticky.
llm_status_fields = {"incomplete", "plan"}   # These are empty for a refactoring step and updated by LLM runs.
# (Fields not listed above are sticky.)


# TODO: It looks like all models support JSON output, and we can eliminate support for "md" responses.
message_bundler = {
  "json": JsonMessageBundler(),
  "md": PseudoMarkdownMessageBundler(),
}
def get_message_bundler_for_model(model):
  return message_bundler[apis[models[model]["api"]]["format"]]
def get_message_bundler_for_api(api):
  return message_bundler[apis[api]["format"]]

# Get the directory of this script.
repo_dir = os.path.dirname(os.path.realpath(__file__))


###########################
# Parse command-line args #
###########################

# (None)


##################
# Initialization #
##################


#
# Find FEV script.
#

if not os.path.exists(repo_dir + "/fev.sby") or not os.path.exists(repo_dir + "/fev.eqy"):
  print("Error: Conversion repository does not contain fev.sby or fev.eqy.")
  usage()

# Read prompts.json.
# prompts.json is a slight extension to JSON supporting newlines in strings. Any newlines within quotes are replaced with '\n'.
with open(repo_dir + "/prompts.json") as file:
  raw_contents = file.read()
json_str = from_extended_json(raw_contents)
prompts = json.loads(json_str)
# Add an index field to prompts. Also provide a dictionary of prompts indexed by desc.
prompts_by_desc = {}
for id, prompt in enumerate(prompts):
  prompt["index"] = id
  desc = prompt["desc"]
  if desc in prompts_by_desc:
    print("Error: Duplicate prompt description: " + desc)
    fail()
  prompts_by_desc[desc] = prompt


#
# Determine file names.
#

# Find the Verilog file to convert, ending in ".v" or ".sv" as the shortest Verilog file in the directory.
files = [f for f in os.listdir(".") if is_verilog(f)]
if len(files) != 1 and not os.path.exists("history"):
  print("Error: There must be exactly one Verilog file or a \"history\" directory in the current working directory.")
  usage()
# Choose the shortest Verilog file name as the one to convert (excluding "current/feved.v").
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
#orig_verilog_file_name = module_name + "_orig.v"
#llm_verilog_file_name = module_name + "_llm.v"


# Make sure files have proper permissions.
# <module>.v (working_verilog_file_name) should be writable.
if not os.access(working_verilog_file_name, os.W_OK):
  print("Error: The Verilog file " + working_verilog_file_name + " must be writable.")
  # Prompt the user to add user and group permissions.
  ch = prompt_user("Add user and group write permissions to " + working_verilog_file_name + "?", {"y", "n"}, "y")
  if ch == "y":
    os.system("chmod ug+w " + working_verilog_file_name)
    print("Permissions added.")
  else:
    print("Exiting.")
    fail()



####################
# Initialize State #
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
  if not os.path.exists("current"):
    os.mkdir("current")
  if not os.path.exists("current/feved.v"):
    os.system("ln -s ../history/1/mod_0/" + working_verilog_file_name + " current/feved.v")
  init_refactoring_step()
else:
  # Determine the current state of the conversion process.
  # Find the current refactoring step.
  for step in os.listdir("history"):
    refactoring_step = max(refactoring_step, int(step))
  # Find the current modification number.
  set_mod_num()

  # Get the prompt ID from the most recent prompt_id.txt file. Look back through the history directories until/if one is found.
  cn = refactoring_step
  while cn >= 0 and prompt_id == 0:
    if os.path.exists("history/" + str(cn) + "/prompt_id.txt"):
      with open("history/" + str(cn) + "/prompt_id.txt") as f:
        prompt_id = read_prompt_id(f)
    cn -= 1
  
  # If messages.<api>.json is/are older than prompts.json or default_system_message.txt, reinitialize it/them.
  # For every API ("gpt", "o"), initialize messages.<api>.json.
  reinitialize = False
  for api in apis:
    messages_json = "messages." + api + ".json"

    if (not os.path.exists(messages_json)) or (os.path.getmtime(messages_json) < os.path.getmtime(repo_dir + "/prompts.json")) or (os.path.getmtime(messages_json) < os.path.getmtime(repo_dir + "/default_system_message.txt")):
      reinitialize = True
  if reinitialize:
    # Confirm.
    ch = prompt_user("\"messages.<api>.json\" is/are missing or out of date. Reinitialize?", {"y", "n"}, "y")
    if ch == "y":
      initialize_messages_json()



###############
#             #
#  Main loop  #
#             #
###############

# Perform the next refactoring step until the user exits.
while True:

  # Determine whether the default_system_message.txt file has been modified after messages.<api>.json.
  for api in apis:
    messages_json = "messages." + api + ".json"
    if os.path.exists(repo_dir + "/default_system_message.txt") and os.path.exists(messages_json):
      if os.path.getmtime(repo_dir + "/default_system_message.txt") > os.path.getmtime(messages_json):
        print("Warning: default_system_message.txt has been modified since " + messages_json + ".")
        print("         Use \"u\" (repeated as needed), then \"r\" to reset the current refactoring step to pick up changes.\n")
  # Prompt the user.
  print_prompt()

  # Process user commands until a modification is accepted or rejected.
  while True:
    # Get the user's command as a single key press (without <Enter>) using pynput library.
    # TODO: Replay get_command(..) in favor of prompt_user(..).
    key = get_command(["l", "L", "m", "M", "e", "f", "E", "y", "u", "U", "c", "p", "h", "?", "x"])

    # Process the user's command.
    if key == "l" or key == "L" or key == "m" or key == "M":
      # Determine model.
      model = None
      if key == "l":
        # Use appropriate default model 
        model = "o4-mini" 
        llm_api = OpenAI_API()
      elif key == "L":
        # Use appropriate high-quality model 
        model = "gpt-4o" 
        llm_api = OpenAI_API()
      elif key in {"M", "m"}:
        # Load all models and APIs
        openai_api = OpenAI_API()
        gemini_api = Gemini_API()
        claude_api = Claude_API()
        all_models = []

        for m in openai_api.models.data:
            if hasattr(m, 'id'):
                all_models.append((m.id, "OpenAI"))

        for m in gemini_api.models:
            model_id = m.name.replace("models/", "")
            all_models.append((model_id, "Gemini"))

        for m in claude_api.models:
            all_models.append((m, "Claude"))

        # Filter if "m" pressed
        if key == "m":
            all_models = [(name, vendor) for name, vendor in all_models if name in important_models]

        # Display
        vendors_present = set(vendor for _, vendor in all_models)
        print("Available vendors:", ", ".join(sorted(vendors_present)))
        
        print("\nAvailable Models:")
        for i, (name, vendor) in enumerate(all_models):
            print(f"  {i}:  ({vendor}) {name}")

        while True:
            try:
                choice = int(input("Enter model number: "))
                model, vendor = all_models[choice]
                if vendor == "OpenAI":
                    llm_api = openai_api
                elif vendor == "Gemini":
                    llm_api = gemini_api
                elif vendor == "Claude":
                    llm_api = claude_api
                else:
                    print("Unknown vendor.")
                    fail()
                break
            except (ValueError, IndexError):
                print("Invalid input. Try again.")

      else:
        print("Bug: Invalid model.")
        fail()

      # Determine the API
      api = models[model]["api"]
      if apis.get(api) == None:
        print("Bug: Invalid API.")
        fail()
      
      messages_json = "messages." + api + ".json"

      # Run the LLM (if not already run).
      do_it = True
      if llm_finished():
        ch = prompt_user("LLM was already run and reported that the refactoring was complete. Run anyway?", {"y", "n"}, "n")
        if ch != "y":
          print("Aborted. Choose a different command.")
          do_it = False
      if do_it:
        with open(messages_json) as message_file:
          with open(working_verilog_file_name) as verilog_file:
            verilog = verilog_file.read()
            # Strip leading and trailing whitespace, then add trailing newline.
            verilog = verilog.strip() + "\n"
            msg_file_str = message_file.read()
            msg_json = from_extended_json(msg_file_str)
            ## Dump the JSON to a file for debugging.
            #with open("tmp/messages_debug.json", "w") as file:
            #  file.write(msg_json)
            messages = json.loads(msg_json)
            # Convert Gemini-style messages (with "parts") to OpenAI-style format (with "content"),
            # to ensure compatibility across API providers.
            for m in messages:
                if "parts" in m and "content" not in m:
                    m["content"] = "".join(m["parts"])  # assumes parts is a list of strings
                    del m["parts"]
            # Add "plan" field if given.
            status = readStatus()
            if "plan" in status:
              messages[-1]["content"] += ("\n\nAnother agent has already made some progress and has established this plan:\n\n" + status["plan"])
            run_llm(messages, verilog, model)
    elif key == "e":
      fev_current(True)
    elif key == "f":
      fev_current(False)
    elif key == "E":
      fev_current(True, True)
    elif key == "y":
      status = readStatus()
      # Can only accept changes that have been FEVed.
      # There must not be any uncommitted manual edits pending.
      confirm = True
      do_it = False
      last_mod = most_recent_mod()
      # Scan the file for comments that should have been removed.
      # Capture grep output to report problematic lines.
      grep_output = os.popen("grep -E 'LLM: (New|Old) Task:' " + working_verilog_file_name).read()
      grep_output += os.popen("grep -E '//\s*User:' " + working_verilog_file_name).read()
      if diff(working_verilog_file_name, mod_path() + "/" + working_verilog_file_name):
        print("Code edits are pending. You must run FEV (or revert) before accepting the refactoring changes.")
      elif status.get("fev") != "passed":
        print("FEV was not run on the current file or did not pass. Choose a different command.")
      elif grep_output != "":
        print("The following comments were found in the code that must be addressed before accepting the changes:")
        print(grep_output)
      elif status.get("incomplete", True):
        if status.get("incomplete", False):
          print("LLM reported that the refactoring is incomplete.")
        else:
          print("LLM has not been run.")
        do_it = True
      else:
        # All good.
        do_it = True
        confirm = False
      
      if do_it and confirm:
        ch = prompt_user("Are you sure you want to accept this refactoring step as complete?", {"y", "n"}, "n")
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

    elif key == "p":
      # Adjust the current prompt, skipping ahead or jumping back, chosen from a complete listing.
      # Permit this only if the current prompt was just begun.
      if most_recent_mod() != None:
        print("Error: You may only apply a specific prompt when the current prompt was just begun.")
        print("       Use \"u\" to revert to the beginning of the current prompt.")
        continue
      # List all prompts.
      print("Prompts:")
      for i in range(len(prompts)):
        print(f"  {i}: {prompts[i]['desc']}")
      print("\nNote: It may be necessary to manually update \"status.json\" to reflect values provided/consumed by LLM/prompts, then exit/restart.\n")
      # Get the prompt number.
      print("Enter the prompt number to apply.")
      print("> ", end="")
      prompt_id = int(input()) - 1
      # Reset to that prompt.
      reset_prompt("r", prompt_id)
      break  # Display prompt info.

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
        # Prompt user.
        resp = None
        if refactoring_step <= 1:
          resp = prompt_user("There is no previous modification. Would you like to [r]eset this refactoring step?", ["r", "n"], "n")
        else:
          print("There is no previous modification in the current refactoring step.")
          print("What would you like to do:")
          print("    [u]naccept (irreversibly) this refactoring step")
          print("    [r]eset this refactoring step")
          resp = prompt_user("    [N]othing", ["u", "r", "n"], "n")
        # Handle the user's response.
        if (resp == "u" and refactoring_step > 1) or (resp == "r"):
          # Determine the updated prompt ID.
          if refactoring_step > 0:
            with open("history/" + str(refactoring_step) + "/prompt_id.txt") as f:
              next_prompt_id = read_prompt_id(f)
              # TODO: Not sure why I read this. Isn't this the same as the current prompt_id?
              if prompt_id != next_prompt_id:
                print("Bug: Prompt ID mismatch. Continuing anyway.")
          else:
            next_prompt_id = 0
          
          reset_prompt(resp, next_prompt_id)
          
          if resp == "u":
            break

      else:
        # Revert to a previous version of the code.
        print("Reverting to the previous version of the code.")
        show_diff(mod, prev_mod)
        # Copy the checkpointed verilog, messages.<api>.json (if it exists), and llm_response.txt (if it exists).
        os.system("cp " + mod_path(prev_mod) + "/" + working_verilog_file_name + " " + working_verilog_file_name)
        if os.path.exists(mod_path(prev_mod) + "/" + messages_json):
          os.system("cp " + mod_path(prev_mod) + "/" + messages_json + " " + messages_json)
        if os.path.exists(mod_path(prev_mod) + "/llm_response.txt"):
          os.system("cp " + mod_path(prev_mod) + "/llm_response.txt llm_response.txt")

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
      ch = prompt_user("Enter the [#] number of the reversion to redo:")
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