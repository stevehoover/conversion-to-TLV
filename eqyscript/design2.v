module top
(
    input_1,
    input_2,
    and_result,
    and_result2,
    and_result3
);

input  input_1;
input  input_2;
output and_result;
output and_result2;
output and_result3;

wire   and_temp;

assign and_temp = input_1 & input_2;

assign and_result = and_temp;
assign and_result2 = input_1 | input_2;
assign and_result3 = input_1 ^ input_2;

endmodule // top
