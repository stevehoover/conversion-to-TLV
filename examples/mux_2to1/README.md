# 2-to-1 Multiplexer Example

## Files
- `mux_2to1.v`: Verilog implementation of a 2-to-1 multiplexer

## Module Features
- 8-bit wide inputs and output
- Single select signal
- Pure combinational logic
- No clock or reset signals

## Conversion Process
This module will be converted using the project's conversion flow:
1. Run the conversion script:
   ```bash
   python3 convert.py mux_2to1.v
   ```
2. The script will:
   - Apply conversion steps from prompts.json
   - Use FEV to verify each step
   - Generate the TL-Verilog version

## Notes
- This is a combinational circuit, so it doesn't have clock or reset signals
- The conversion process will be simpler than sequential circuits
- FEV will verify functional equivalence at each step 

# 2-to-1 Multiplexer Conversion Process

This document details the manual conversion process of a 2-to-1 multiplexer from Verilog to TL-Verilog, following the project's conversion flow.

## Original Verilog Code
```verilog
module mux_2to1 (
    input wire [7:0] in0,    // First input
    input wire [7:0] in1,    // Second input
    input wire sel,          // Select signal
    output wire [7:0] out    // Output
);

    // 2-to-1 multiplexer implementation
    assign out = sel ? in1 : in0;

endmodule
```

## Conversion Steps Applied

### 1. Three-space Indentation
- Module declaration and endmodule: no indentation
- Module body: one level (3 spaces)
- No tabs used, only spaces
- Result:
```verilog
module mux_2to1 (
   input wire [7:0] in0,    // First input
   input wire [7:0] in1,    // Second input
   input wire sel,          // Select signal
   output wire [7:0] out    // Output
);

   // 2-to-1 multiplexer implementation
   assign out = sel ? in1 : in0;

endmodule
```

### 2. Clocking Analysis
- Status: PASS
- No clock signals present
- Purely combinational logic
- No internal clock generation
- No gated or divided clocks

### 3. Reset Analysis
- Status: PASS
- No reset signals present
- Purely combinational circuit
- No asynchronous or synchronous resets

### 4. Non-synthesizable Code Check
- Status: PASS
- No initial blocks
- No simulation delays
- No analog constructs
- No tri-state logic

### 5. Separate Declarations
- Status: PASS
- All signals are ports
- No combined declarations and assignments
- No changes needed

### 6. Non-deterministic Behavior Check
- Status: PASS
- Using continuous assignment (assign)
- No race conditions possible
- No sensitivity list issues
- No blocking/non-blocking assignment conflicts

### 7. Partial Signal Assignments
- Status: PASS
- Full signal assignments only
- No concatenation needed

### 8. If/else to Ternary
- Status: PASS
- Already using ternary operator
- No if/else statements to convert
