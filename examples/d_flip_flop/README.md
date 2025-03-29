# D Flip-Flop Conversion

This example demonstrates converting a D flip-flop from Verilog to TL-Verilog. The D flip-flop includes synchronous reset functionality.



## Original Verilog Code

```verilog
module d_flip_flop (
   input wire clk,
   input wire rst_n,
   input wire d,
   output reg q
);

   // D flip-flop logic
   always @(posedge clk or negedge rst_n) begin
      if (!rst_n)
         q <= 1'b0;
      else
         q <= d;
   end

endmodule
```

## Conversion Steps

### 1. Three-space Indentation
- Applied standard three-space indentation
- Maintained readability of control logic

### 2. Clocking Analysis
- Single global clock input `clk`
- Used with `posedge` trigger
- No internal clock generation
- No gated or divided clocks



### 3. Reset Analysis
- Active-low reset signal `rst_n`
- Used asynchronously
- Will be converted to synchronous reset


### 4. Control Signal Analysis
- Single control signal: reset
- No other control conditions
- Simple data path


### 5. Reset Signal Handling
- Convert to synchronous reset
- Maintain flip-flop functionality
- Preserve timing relationships



## TL-Verilog Version

### Version 1: Exact Verilog Behavior (No Pipeline Stage)
```tlv
\TLV_version 1d: tl-x.org
\SV
   module d_flip_flop (
      input wire clk,
      input wire rst_n,
      input wire d,
      output reg q
   );
\TLV
   // Connect inputs:
   $reset = ~ *rst_n;
   $d = *d;
   
   // D flip-flop logic using ternary operator
   $Q = $reset ? 1'b0 : $d;
   
   // Connect outputs (immediate)
   *q = $Q;
\SV
   endmodule
```

### Version 2: Pipelined Version (One Cycle Delay)
```tlv
\TLV_version 1d: tl-x.org
\SV
   module d_flip_flop (
      input wire clk,
      input wire rst_n,
      input wire d,
      output reg q
   );
\TLV
   // Connect inputs:
   $reset = ~ *rst_n;
   $d = *d;
   
   // D flip-flop logic using ternary operator
   $Q = $reset ? 1'b0 : $d;
   
   // Connect outputs (one cycle delay)
   *q = >>1$Q;
\SV
   endmodule
```

