import openai
import requests
import json
import time
import os

class TLVerilogAssistant:
    def __init__(self, api_key):
        self.api_key = api_key
        openai.api_key = api_key
        self.assistant = self.create_assistant()

    def create_assistant(self):
        """Creates or retrieves the TL-Verilog assistant."""
        return openai.beta.assistants.create(
            name="convert_tl_verilog",
            model="gpt-4o",
            instructions=(
                "Converts Transaction-Level Verilog (TL-Verilog) hardware description language code into SystemVerilog code "
                "using Redwood EDA, LLC's SandPiper™ tool. The assistant uses a tool that receives a TL-Verilog source file "
                "as input and produces a SystemVerilog file as output. If an error occurs, STDERR output is returned. "
                "Warnings and informational messages may also be present in STDERR even if the conversion is successful."
            ),
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "convert_tl_verilog",
                        "description": (
                            "Uses Redwood EDA, LLC's SandPiper™ tool to convert a TL-Verilog file into SystemVerilog. "
                            "The response includes 'systemverilog' containing the generated SystemVerilog code (if successful) "
                            "and 'stderr' containing any warnings, informational messages, or error messages from the conversion process."
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "source_tlv": {
                                    "type": "string",
                                    "description": "The contents of the TL-Verilog source file."
                                }
                            },
                            "required": ["source_tlv"]
                        }
                    }
                }
            ]
        )
    
    def create_thread(self):
        """Creates a new thread for interaction."""
        thread = openai.beta.threads.create()
        return thread.id

    def call_sandpiper_saas(self, source_tlv):
        """Calls the SandPiper-SaaS API to convert TL-Verilog to SystemVerilog."""
        api_url = "https://faas.makerchip.com/function/sandpiper-faas"
        
        # Command-line arguments
        # "--fmtNoSource"
        args = f"-i test.tlv -o test.sv --m4out out/m4out --inlineGen --iArgs"
        
        payload = {
            "args": args,
            "responseType": "json",
            "sv_url_inc": False,
            "files": {
                "test.tlv": source_tlv
            }
        }
        
        try:
            response = requests.post(api_url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            return {
                "systemverilog": data.get("out/test.sv", "// Compilation failed."),
                "stderr": data.get("stderr", "")
            }
        except requests.RequestException as e:
            return {"systemverilog": "", "stderr": f"Request failed: {str(e)}"}

    def handle_function_call(self, thread_id, run_id):
        """Handles function call requests from the assistant."""
        while True:
            run_status = openai.beta.threads.runs.retrieve(run_id, thread_id=thread_id)
            
            if run_status.status == "completed":
                print("Assistant run completed!")
                return
            
            elif run_status.status == "requires_action":
                function_call = run_status.required_action.submit_tool_outputs.tool_calls[0]
                if function_call.function.name == "convert_tl_verilog":
                    arguments = json.loads(function_call.function.arguments)
                    result = self.call_sandpiper_saas(arguments["source_tlv"])
                    
                    openai.beta.threads.runs.submit_tool_outputs(
                        thread_id=thread_id,
                        run_id=run_id,
                        tool_outputs=[{
                            "tool_call_id": function_call.id,
                            "output": json.dumps(result)
                        }]
                    )
                    print("Function call submitted.")
            else:
                print("Waiting for assistant to complete...")
            time.sleep(1)
    
    def one_shot(self, content):
        """Sends user content to the LLM."""
        thread_id = self.create_thread()

        # Send the user message
        message = openai.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=content
        )

        run = openai.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=self.assistant.id
        )

        self.handle_function_call(thread_id, run.id)

        messages = openai.beta.threads.messages.list(thread_id=thread_id)
        for msg in messages.data:
            print(f"{msg.role}: {msg.content}")




# ========================================================


# Test the TLVerilogAssistant class.

# if OPENAI_API_KEY env var does not exist, get it from ~/.openai/key.txt or input prompt.
if not os.getenv("OPENAI_API_KEY"):
  key_file_name = os.path.expanduser("~/.openai/key.txt")
  if os.path.exists(key_file_name):
    with open(key_file_name) as file:
      os.environ["OPENAI_API_KEY"] = file.read()
  else:
    os.environ["OPENAI_API_KEY"] = input("Enter your OpenAI API key: ")

# Use an organization in the request if one is provided, either in the OPENAI_ORG_ID env var or in ~/.openai/org_id.txt.
org_id = os.getenv("OPENAI_ORG_ID")
if not org_id:
  org_file_name = os.path.expanduser("~/.openai/org_id.txt")
  if os.path.exists(org_file_name):
    with open(org_file_name) as file:
      org_id = file.read()

tlv_assistant = TLVerilogAssistant(api_key=os.getenv("OPENAI_API_KEY"))

# TL-Verilog source code to convert.
source_tlv = """
\m5_TLV_version 1d: tl-x.org
\SV
   m5_use(m5-1.0)
   `include "sqrt32.v";
   
   m5_makerchip_module
\TLV
      
   // Stimulus
   |calc
      @0
         $valid = & $rand_valid[1:0];  // Valid with 1/4 probability
                                       // (& over two random bits).
   
   |calc
      ?$valid
         // Pythagoras's Theorem
         @1
            $aa_sq[7:0] = $aa[3:0] ** 2;
            $bb_sq[7:0] = $bb[3:0] ** 2;
         @2
            $cc_sq[8:0] = $aa_sq + $bb_sq;
         @3
            $cc[4:0] = sqrt($cc_sq);

\SV
   endmodule
"""



# Run the conversion process.
#tlv_assistant.one_shot(f"Convert the following TL-Verilog code to SystemVerilog:\n\n{source_tlv}")

tlv_assistant.one_shot(f"Make sure the following TL-Verilog code compiles, then modify it to move the expression for `$aa` to stage `@0` and recompile. Observe and report on the differences in the generated SystemVerilog. Here's the code:\n\n{source_tlv}")