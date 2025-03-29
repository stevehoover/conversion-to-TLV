# Shift Register Conversion

This demonstrates converting a shift register from Verilog to TL-Verilog. The shift register includes both serial and parallel loading capabilities.

### Original Verilog Code

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
   module shift_register (
      input wire clk,
      input wire rst_n,
      input wire load_en,    // Enable parallel loading
      input wire shift_en,   // Enable shifting
      input wire serial_in,  // Serial input
      input wire [7:0] data_in,  // Parallel input
      output reg [7:0] data_out  // Parallel output
   );
\TLV
   // Connect inputs:
   $reset = ~ *rst_n;
   $load_en = *load_en;
   $shift_en = *shift_en;
   $serial_in = *serial_in;
   $data_in = *data_in;
   
   // Shift register logic
   $DataOut[7:0] =
        $reset    ? 8'b0 :
        $load_en  ? $data_in :
        $shift_en ? {$serial_in, $DataOut[7:1]} :
        //default
                    $RETAIN;
   
   // Connect outputs.
   *data_out = >>1$DataOut;
\SV
   endmodule
```

