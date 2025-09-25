`default_nettype none

// Defaults; override with -D on read_verilog if needed.
`ifndef RSTLEN
`define RSTLEN 5
`endif

`ifndef CLKSIG_GOLD
`define CLKSIG_GOLD clk
`endif
`ifndef RESETSIG_GOLD
`define RESETSIG_GOLD reset
`endif
`ifndef CLKSIG_GATE
`define CLKSIG_GATE clk
`endif
`ifndef RESETSIG_GATE
`define RESETSIG_GATE reset
`endif

module formal_reset_assumptions #(
  parameter int unsigned RSTLEN = `RSTLEN
)(
  input  logic clk,
  input  logic reset
);
  logic past_valid;
  logic [$clog2(RSTLEN+1)-1:0] rst_cnt;

  initial begin
    past_valid = 1'b0;
    rst_cnt    = '0;
  end

  always_ff @(posedge clk) begin
    past_valid <= 1'b1;
    if (!past_valid) begin
      rst_cnt <= '0;
    end else if (rst_cnt < RSTLEN) begin
      rst_cnt <= rst_cnt + 1'b1;
    end
  end

  // Assume reset high during first RSTLEN cycles, low thereafter.
  assume property (@(posedge clk) (rst_cnt < RSTLEN) |-> reset);
  assume property (@(posedge clk) (rst_cnt >= RSTLEN) |-> !reset);
endmodule

// Bind to each design instance so clk/reset need not be top-level ports.
bind gold formal_reset_assumptions #(.RSTLEN(`RSTLEN)) _fev_rst_gold (
  .clk   (`CLKSIG_GOLD),
  .reset (`RESETSIG_GOLD)
);
bind gate formal_reset_assumptions #(.RSTLEN(`RSTLEN)) _fev_rst_gate (
  .clk   (`CLKSIG_GATE),
  .reset (`RESETSIG_GATE)
);

`default_nettype wire
