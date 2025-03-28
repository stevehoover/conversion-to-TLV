# D Flip-Flop Conversion Process

This details the manual conversion process of a D flip-flop from Verilog to TL-Verilog, following the project's conversion flow.

## Original Verilog Code
```verilog
module d_flip_flop (
    input wire clk,
    input wire rst_n,  // Active low reset
    input wire d,
    output reg q
);

    // D flip-flop with asynchronous reset
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            q <= 1'b0;
        else
            q <= d;
    end

endmodule
```

## Conversion Steps Applied

### 1. Three-space Indentation
- Module declaration and endmodule: no indentation
- Module body: one level (3 spaces)
- Begin/end blocks: additional level
- Result:
```verilog
module d_flip_flop (
   input wire clk,
   input wire rst_n,  // Active low reset
   input wire d,
   output reg q
);

   // D flip-flop with asynchronous reset
   always @(posedge clk or negedge rst_n) begin
      if (!rst_n)
         q <= 1'b0;
      else
         q <= d;
   end

endmodule
```

### 2. Clocking Analysis
- Status: PASS with changes needed
- Found single global clock input `clk`
- Used with `posedge` trigger
- No internal clock generation
- No gated or divided clocks
- Clock signal name is already "clk" (standard name)

### 3. Reset Analysis
- Status: NEEDS CHANGE
- Found active-low reset signal `rst_n`
- Used asynchronously (in `negedge rst_n`)
- Must be converted to synchronous reset
- Reset assertion: "low"

### 4. Non-synthesizable Code Check
- Status: PASS
- No initial blocks
- No simulation delays
- No analog constructs
- No tri-state logic

### 5. Reset Signal Handling
- Convert active-low async reset to active-high sync reset
- Add intermediate reset signal
- Remove async reset from sensitivity list
- Result:
```verilog
module d_flip_flop (
   input wire clk,
   input wire rst_n,  // Active low reset
   input wire d,
   output reg q
);

   // Convert active-low async reset to active-high sync reset
   logic rst;
   assign rst = ~rst_n;

   // D flip-flop with synchronous reset
   always_ff @(posedge clk) begin
      if (rst)
         q <= 1'b0;
      else
         q <= d;
   end

endmodule
```

### 6. Non-deterministic Behavior Check
- Status: PASS
- Using non-blocking assignments (`<=`)
- Clear clock domain
- Complete sensitivity list
- No race conditions

### 7. Partial Signal Assignments
- Status: PASS
- Full signal assignments only
- No concatenation needed

### 8. If/else to Ternary
- Could convert to ternary, but keeping if/else for readability
- Sequential logic often clearer with if/else
- No change needed