# 2-to-1 Multiplexer Conversion

This example demonstrates converting a 2-to-1 multiplexer from Verilog to TL-Verilog. The multiplexer includes 8-bit wide inputs and output.

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

## Conversion Steps

### 1. Three-space Indentation
- Applied standard three-space indentation
- Maintained readability of logic

### 2. Clocking Analysis
- No clock signals present
- Purely combinational logic
- No internal clock generation
- No gated or divided clocks

### 3. Reset Analysis
- No reset signals present
- Purely combinational circuit
- No asynchronous or synchronous resets

### 4. Control Signal Analysis
- Single control signal: select
- Clear priority: select signal
- No conflicting conditions

### 5. Signal Handling
- Maintain combinational functionality
- Preserve timing relationships
- Keep signal widths consistent

## TL-Verilog Version

```tlv
\TLV_version 1d: tl-x.org
\SV
   module mux_2to1 (
      input wire [7:0] in0,    // First input
      input wire [7:0] in1,    // Second input
      input wire sel,          // Select signal
      output wire [7:0] out    // Output
   );
\TLV
   // Connect inputs:
   $sel = *sel;
   $in0 = *in0;
   $in1 = *in1;
   
   // Multiplexer logic using ternary operator
   $Out[7:0] = $sel ? $in1 : $in0;
   
   // Connect outputs (immediate)
   *out = $Out;
\SV
   endmodule
```


