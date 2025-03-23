\m4_TLV_version 1d: tl-x.org
\SV
   // Include TL-Verilog files
   m4_include_lib(['https://raw.githubusercontent.com/stevehoover/warp-v/master/tlv_lib/basics.tlv'])

\TLV
   // Counter module
   |counter
      @0
         // Reset condition
         $reset = *reset;
         
         // Enable signal
         $enable = *enable;
         
         // Counter logic
         $count[3:0] = $reset ? 4'b0 :
                       $enable ? >>1$count + 1 :
                       >>1$count;
         
         // Output assignment
         *count = $count;

\SV
   // Instantiate the counter module
   module counter_4bit (
      input wire clk,
      input wire rst,
      input wire enable,
      output reg [3:0] count
   );
      
      // TL-Verilog design instance
      counter_gen counter (.*);
      
   endmodule 