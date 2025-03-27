#Conversion from Verilog to TL-Verilog Using LLMs

## Goal

To use LLMs and TL-Verilog to improve all existing Verilog by reducing its size, improving its maintainability, making it more configurable, and identifying bugs? How could we possibly do all that? Transaction-Level Verilog (TL-Verilog) models are smaller, cleaner, and less bug-prone than their Verilog counterparts. But there's not much TL-Verilog in the wild yet. Advancements in AI make it feasible to automate the process of converting existing Verilog models to TL-Verilog.

If you ask ChatGPT to convert your code today, you won't be happy with the results. But with a thoughtful approach, LLMs can help. Through a series of incremental conversion steps, backed by formal verification, automated conversion is possible, and the results will have better quality than without LLM, especially when it comes to preserving meaningful comments.

## Approach

We aim to use existing LLMs, primarily various versions of ChatGPT via its API. We do not intend to tune a custom LLM (though that might be an option). The LLM will be trained through the conversation, primarily using "system messages".

A command-line Python script (`convert.py`) controls the interactions with the LLM. The script uses a recipe for conversion that includes numerous incremental conversion steps. The bulk of the process is refactoring Verilog to a form that looks similar to the (System)Verilog that would be produce by Redwood EDA's SandPiper(TM) tool. Each step:

- Provides the LLM with a "system message" that defines the nature of the conversion process and how to approach each step. (See `default_system_messages.txt`).
- Provide the prompt for the step and invoke the LLM to do all or part of the step.
- Extract the code from the LLM's response.
- Run FEV to test this code for correctness vs. the previous version of the code.
- If FEV passes
  - Update the code.
  - If the LLM indicated that it's update was incomplete, prompt again for more modifications and FEV, repeating until complete.
  - Move on to the next step, and repeat.

If any step in the process fails, the script will ask either the LLM or the human for assistance.

All updates performed by the script are captured in the file system so the script can be terminated and restarted, picking up where it left off. A complete history of changes is maintained with an ability to revert. These files can later be used as training data for an LLM to improve the process.

After refactoring the Verilog, the Verilog can be converted to TL-Verilog and refactored further.

This flow chart illustrates the conversion process provided by `convert.py`. It is maintained as a Google Slide [here](https://docs.google.com/presentation/d/1DrzpY_SHGRrRTwy-Qn1yxRMDGkBcj451uwVKhUJ295I/edit?usp=sharing). (To update, request permission, edit, download as PNG and place in docs/VerilogConversionFlow.png.)

![Conversion Flow Image](./docs/VerilogConversionFlow.png)

## Status

The initial script is in place for the Verilog conversion steps.

## Installation and Setup

### Prerequisites

- Python 3.10 or higher
- Git
- Linux/Unix-based system (tested on Ubuntu 22.04)

### Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/stevehoover/conversion-to-TLV.git
   cd conversion-to-TLV
   ```

2. Run the initialization script:
   ```bash
   chmod +x init
   ./init
   ```
   This script will:
   - Install required system packages
   - Set up Python environment
   - Install and configure Yosys, SymbiYosys, and EQY
   - Verify tool installations

3. Configure OpenAI API access:
   Place your OpenAI API key in `~/.openai/key.txt`:
   ```bash
   mkdir -p ~/.openai
   echo "your-api-key-here" > ~/.openai/key.txt
   ```

### Troubleshooting

If you encounter issues:

1. **Tool verification**:
   Check installed tools with:
   ```bash
   yosys --version    # Should show Yosys version
   sby --version      # Should show SymbiYosys version
   eqy --version     # Should show EQY version
   ```

2. **Clean build**:
   If you need to clean the build:
   ```bash
   ./make_clean
   ```

3. **Python environment**:
   The project uses a virtual environment. If needed:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

For additional help, please open an issue in the repository.

## Contributing

Here are a few ideas for those interested in contributing:

- Use the learning resources in Makerchip to learn about TL-Verilog.
- Use the learning resources in Makerchip and https://github.com/rweda/M5 to learn M5, which is used to parameterize prompts.
- If you'd like to explore LLM-assisted visualization, use the learning resources in Makerchip to learn Visual Debug.
- Study the current prompts https://github.com/stevehoover/conversion-to-TLV/blob/main/prompts.json, capturing any thoughts.
- Choose some simple open-source Verilog modules to convert. Run the flow to convert them. Do not use the LLM. Make each change manually as if you are the LLM. Debug using FEV (run by the flow). Capture learnings.
- Get an OpenAI API key and convert more. Make incremental improvements along the way.

## Ideas for Verilog Code Sources

- https://github.com/NVlabs/verilog-eval/blob/main/data/VerilogEval_Human.jsonl
- https://hdlbits.01xz.net/wiki/Main_Page
- A random Linkedin post that should be an easy conversion: https://www.linkedin.com/pulse/exploring-multiplication-structures-rtl-level-fpgas-stefanazzi-t0ajc%3FtrackingId=aC3MgfsoAaKippYXPY%252Fb1Q%253D%253D/?trackingId=aC3MgfsoAaKippYXPY%2Fb1Q%3D%3D
- RISC-V Cores
  - SERV
  - SweRV
  - cv32e40p
- Verilog libraries (These will be more difficult due to parameterization.)
  - BaseJump STL