# Semi-automated Conversion from Verilog to TL-Verilog Using LLMs

## Goal

To use LLMs and TL-Verilog to improve all existing Verilog by reducing its size, improving its maintainability, making it more configurable, and identifying bugs? How could we possibly do all that? Transaction-Level Verilog (TL-Verilog) models are smaller, cleaner, and less bug-prone than their Verilog counterparts. But there's not much TL-Verilog in the wild yet. Advancements in AI make it feasible to automate the process of converting existing Verilog models to TL-Verilog.

If you ask ChatGPT to convert your code today, you won't be happy with the results[.](https://gitlab.com/rweda/Makerchip-public) But with a thoughtful approach, LLMs can help. Through a series of incremental conversion steps, backed by formal verification, automated conversion is possible, and the results will have better quality than without LLM, especially when it comes to preserving meaningful comments.

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
- Build tools (gcc, make, etc.)
- OpenAI API key (for LLM integration)

### System Dependencies

The project requires several system-level tools for formal verification and synthesis:

- Yosys (for synthesis)
- SymbiYosys (for formal verification)
- EQY (for equivalence checking)
- Z3 (SMT solver)

### Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/stevehoover/conversion-to-TLV.git
   cd conversion-to-TLV
   ```

2. Run the initialization script to install all dependencies:
   ```bash
   chmod +x init
   ./init
   ```

3. Set up your OpenAI API key:
   ```bash
   export OPENAI_API_KEY='your-api-key-here'
   ```

### Manual Installation

If you prefer to install dependencies manually:

1. Install system dependencies:
   ```bash
   # For Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install -y build-essential git python3 python3-pip tcl-dev libffi-dev libreadline-dev bison flex pkg-config zlib1g-dev graphviz
   
   # For macOS
   brew install python3 tcl libffi readline bison flex pkg-config zlib graphviz
   ```

2. Install Python dependencies:
   ```bash
   python3 -m pip install --upgrade pip
   pip3 install pynput openai
   ```

3. Install verification tools:
   - [Yosys Installation Guide](https://github.com/YosysHQ/yosys#building-from-source)
   - [SymbiYosys Installation Guide](https://github.com/YosysHQ/SymbiYosys#building-from-source)
   - [EQY Installation Guide](https://github.com/YosysHQ/eqy#building-from-source)

### Troubleshooting

Common issues and solutions:

1. **Yosys build fails**:
   - Ensure all system dependencies are installed
   - Check if you have sufficient disk space
   - Try cleaning the build directory: `make clean`

2. **SymbiYosys fails to find Yosys**:
   - Verify Yosys is in your PATH: `which yosys`
   - Check Yosys installation: `yosys --version`

3. **Python package installation fails**:
   - Try upgrading pip: `python3 -m pip install --upgrade pip`
   - Use virtual environment: `python3 -m venv venv && source venv/bin/activate`

4. **Formal verification tools not found**:
   - Ensure all tools are in your PATH
   - Check tool versions: `yosys --version && sby --version && eqy --version`

For more detailed troubleshooting, please open an issue in the repository.

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