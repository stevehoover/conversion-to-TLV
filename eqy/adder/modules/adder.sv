module miter (
  input  [  0:0] \__pi_a ,
  input  [  0:0] \__pi_b ,
`ifdef DIRECT_CROSS_POINTS
`else
`endif
  output [  0:0] \__po_carry__gold ,
  output [  0:0] \__po_sum__gold ,
  output [  0:0] \__po_carry__gate ,
  output [  0:0] \__po_sum__gate
);
  \gold.adder gold (
    .\__pi_a (\__pi_a ),
    .\__pi_b (\__pi_b ),
`ifdef DIRECT_CROSS_POINTS
`else
`endif
    .\__po_carry (\__po_carry__gold ),
    .\__po_sum (\__po_sum__gold )
  );
  \gate.adder gate (
    .\__pi_a (\__pi_a ),
    .\__pi_b (\__pi_b ),
`ifdef DIRECT_CROSS_POINTS
`else
`endif
    .\__po_carry (\__po_carry__gate ),
    .\__po_sum (\__po_sum__gate )
  );
`ifdef ASSUME_DEFINED_INPUTS
  miter_def_prop #(1, "assume") \__pi_a__assume (\__pi_a );
  miter_def_prop #(1, "assume") \__pi_b__assume (\__pi_b );
`endif
`ifndef DIRECT_CROSS_POINTS
`endif
`ifdef CHECK_MATCH_POINTS
`endif
`ifdef CHECK_OUTPUTS
  miter_cmp_prop #(1, "assert") \__po_carry__assert (\__po_carry__gold , \__po_carry__gate );
  miter_cmp_prop #(1, "assert") \__po_sum__assert (\__po_sum__gold , \__po_sum__gate );
`endif
`ifdef COVER_DEF_CROSS_POINTS
  `ifdef DIRECT_CROSS_POINTS
  `else
  `endif
`endif
`ifdef COVER_DEF_GOLD_MATCH_POINTS
`endif
`ifdef COVER_DEF_GATE_MATCH_POINTS
`endif
`ifdef COVER_DEF_GOLD_OUTPUTS
  miter_def_prop #(1, "cover") \__po_carry__gold_cover (\__po_carry__gold );
  miter_def_prop #(1, "cover") \__po_sum__gold_cover (\__po_sum__gold );
`endif
`ifdef COVER_DEF_GATE_OUTPUTS
  miter_def_prop #(1, "cover") \__po_carry__gate_cover (\__po_carry__gate );
  miter_def_prop #(1, "cover") \__po_sum__gate_cover (\__po_sum__gate );
`endif
endmodule
module miter_cmp_prop #(parameter WIDTH=1, parameter TYPE="assert") (input [WIDTH-1:0] in_gold, in_gate);
  reg okay;
  integer i;
  always @* begin
    okay = 1;
    for (i = 0; i < WIDTH; i = i+1)
      okay = okay && (in_gold[i] === 1'bx || in_gold[i] === in_gate[i]);
  end
  generate
    if (TYPE == "assert") always @* assert(okay);
    if (TYPE == "assume") always @* assume(okay);
    if (TYPE == "cover")  always @* cover(okay);
  endgenerate
endmodule
module miter_def_prop #(parameter WIDTH=1, parameter TYPE="assert") (input [WIDTH-1:0] in);
  wire okay = ^in !== 1'bx;
  generate
    if (TYPE == "assert") always @* assert(okay);
    if (TYPE == "assume") always @* assume(okay);
    if (TYPE == "cover")  always @* cover(okay);
  endgenerate
endmodule
module \gold.adder (
  input  [  0:0] \__pi_a ,
  input  [  0:0] \__pi_b ,
  output [  0:0] \__po_carry ,
  output [  0:0] \__po_sum
);
endmodule
module \gate.adder (
  input  [  0:0] \__pi_a ,
  input  [  0:0] \__pi_b ,
  output [  0:0] \__po_carry ,
  output [  0:0] \__po_sum
);
endmodule
