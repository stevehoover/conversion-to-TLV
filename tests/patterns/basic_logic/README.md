# Basic Logic Pattern Test Cases

This collection contains fundamental digital logic test cases implemented in Verilog. These test cases serve as examples for RTL to TLV conversion patterns.

## Components

1. **D Flip-Flop** (`d_flipflop.v`)
   - Parameterizable width
   - Enable control
   - Asynchronous reset
   - Clock-edge triggered

2. **Multiplexer** (`multiplexer.v`)
   - Configurable data width
   - Variable number of inputs
   - Binary select signal

3. **Decoder** (`decoder.v`)
   - Configurable input width
   - Configurable output width
   - One-hot output encoding

4. **Full Adder** (`full_adder.v`)
   - Three inputs (a, b, cin)
   - Sum and carry outputs
   - Standard logic implementation

## Usage

These test cases can be used as:
- Reference implementations for digital logic components
- Examples for RTL to TLV conversion patterns
- Building blocks for larger digital designs

## Verification

Each component includes:
- Built-in assertions for verification
- Clear interface definitions
- Comprehensive comments
- Modular and reusable design

## Directory Structure

```
basic_logic/
├── README.md
├── d_flipflop.v
├── multiplexer.v
├── decoder.v
└── full_adder.v
```

## D Flip-Flop (`d_flipflop.v`)

A parameterizable D Flip-Flop implementation with the following features:
- Configurable bit width
- Enable control for data capture
- Active-low asynchronous reset
- Clock-edge triggered operation

### Interface
```verilog
module d_flipflop #(
    parameter WIDTH = 1
)(
    input wire clk,
    input wire rst_n,
    input wire enable,
    input wire [WIDTH-1:0] d,
    output reg [WIDTH-1:0] q
);
```

### Verification
- Reset functionality verification
- Enable/disable behavior validation
- Data retention testing

## Multiplexer (`multiplexer.v`)

A flexible multiplexer implementation supporting:
- Configurable data width
- Variable number of inputs
- Binary select signal

### Interface
```verilog
module multiplexer #(
    parameter WIDTH = 8,
    parameter SEL_WIDTH = 3,
    parameter NUM_INPUTS = 8
)(
    input wire [SEL_WIDTH-1:0] sel,
    input wire [WIDTH-1:0] data_in [NUM_INPUTS-1:0],
    output wire [WIDTH-1:0] data_out
);
```

### Verification
- Input selection validation
- Data integrity checks
- Select signal range verification

## Decoder (`decoder.v`)

A binary-to-one-hot decoder implementation with:
- Configurable input width
- Configurable output width
- One-hot output encoding

### Interface
```verilog
module decoder #(
    parameter IN_WIDTH = 3,
    parameter OUT_WIDTH = 8
)(
    input wire [IN_WIDTH-1:0] in,
    output wire [OUT_WIDTH-1:0] out
);
```

### Verification
- One-hot output validation
- Input range checking
- Output pattern verification

## Full Adder (`full_adder.v`)

A standard full adder implementation featuring:
- Three inputs (a, b, cin)
- Sum and carry outputs
- Standard logic gate implementation

### Interface
```verilog
module full_adder(
    input wire a,
    input wire b,
    input wire cin,
    output wire sum,
    output wire cout
);
```

### Verification
- Complete input combination testing
- Sum calculation validation
- Carry generation verification 