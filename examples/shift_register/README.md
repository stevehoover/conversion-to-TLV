# Shift Register Conversion

This example demonstrates converting a shift register from Verilog to TL-Verilog. The shift register includes both serial and parallel loading capabilities.

## Original Verilog Code

```verilog
module shift_register (
   input wire clk,
   input wire rst_n,
   input wire load_en,    // Enable parallel loading
   input wire shift_en,   // Enable shifting
   input wire serial_in,  // Serial input
   input wire [7:0] data_in,  // Parallel input
   output reg [7:0] data_out  // Parallel output
);

   // Shift register logic
   always @(posedge clk or negedge rst_n) begin
      if (!rst_n)
         data_out <= 8'b0;
      else begin
         if (load_en)
            data_out <= data_in;
         else if (shift_en)
            data_out <= {serial_in, data_out[7:1]};
      end
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
- Two control signals: `load_en` and `shift_en`
- Clear priority: load takes precedence over shift
- No conflicting control conditions

### 5. Reset Signal Handling
- Convert to synchronous reset
- Maintain register functionality
- Preserve control signal behavior

## TL-Verilog Version

```tlv
\TLV_version 1d: tl-x.org
\SV
   // Convert active-low async reset to active-high sync reset
   logic rst;
   assign rst = ~rst_n;

   // Register for shift register data
   logic [7:0] data_out;

   // Shift register logic
   always_ff @(posedge clk) begin
      if (rst)
         data_out <= 8'b0;
      else begin
         if (load_en)
            data_out <= data_in;
         else if (shift_en)
            data_out <= {serial_in, data_out[7:1]};
      end
   end
\SV_plus
   // Transaction-level logic can be added here
   // For example, we could add:
   // - Data pattern monitoring
   // - Shift operation verification
   // - Load operation verification
```

## Key Learnings

1. Shift registers in TL-Verilog maintain clear control logic
2. Synchronous reset conversion preserves functionality
3. Control signal priority remains explicit
4. Parallel and serial operations are clearly separated

## Verification

The design has been verified using:
- Basic simulation
- Load operation checks
- Shift operation checks
- Reset behavior validation

## Next Steps

Future improvements could include:
- Adding transaction-level monitoring
- Implementing pattern detection
- Adding configurable width
- Including shift direction control 