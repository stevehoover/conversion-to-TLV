# Read and prepare the first design
read_verilog design1.v
proc; opt; flatten
rename top top1

# Read and prepare the second design
read_verilog design2.v
proc; opt; flatten
rename top top2

# Create the equivalence checking module
equiv_make top1 top2 equiv
hierarchy -top equiv

# Perform the equivalence check
equiv_simple
equiv_status
