```verilog
module verilog1(
   input wire a,
   input wire b,
   input wire clk,
   output wire y
);
   assign y = a & b;
endmodule
```