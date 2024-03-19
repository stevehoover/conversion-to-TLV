yosys -import

# TOP_MODULE can be passed in or default to "top".
set top "top"
if { [info exists ::env(TOP_MODULE)] } {
  set top $::env(TOP_MODULE)
}

# Get original and modified file names from environment variable:
# ORIGINAL_VERILOG_FILE
set orig_file "top.v"
if { [info exists ::env(ORIGINAL_VERILOG_FILE)]} {
    set orig_file $::env(ORIGINAL_VERILOG_FILE)
}
# MODIFIED_VERILOG_FILE
set modified_file "top.v"
if { [info exists ::env(MODIFIED_VERILOG_FILE)]} {
    set modified_file $::env(MODIFIED_VERILOG_FILE)
}
# RESET_SIGNAL_NAME
set reset_signal_name ""
if { [info exists ::env(RESET_SIGNAL_NAME)]} {
    set reset_signal_name $::env(RESET_SIGNAL_NAME)
}
# RESET_ASSERTION_LEVEL
set reset_assertion_level ""
if { [info exists ::env(RESET_ASSERTION_LEVEL)]} {
    set reset_assertion_level $::env(RESET_ASSERTION_LEVEL)
}

yosys read_verilog -sv $orig_file
yosys hierarchy -top $top
yosys proc
yosys clean
yosys design -stash orig

yosys read_verilog -sv $modified_file
yosys hierarchy -top $top
yosys proc
yosys clean
yosys design -stash modified

yosys design -copy-from orig -as orig $top
yosys design -copy-from modified -as modified $top
yosys miter -equiv -make_assert -flatten orig modified miter
#show miter
# Must init states to 0 because initialization will be inconsistent between orig and modified otherwise and will mismatch during reset.
# (It would be better to disable checks during reset, but not sure how.)
# Force reset input if there is one, based on RESET_ASSERTION_LEVEL. It would be better for testbench to do this based on $initstate.
set reset_duration 5
set operational_duration 15
set seq_value [expr $reset_duration + $operational_duration - 1]
set reset_level [expr {$reset_assertion_level == "low" ? 0 : 1}]
set operational_level [expr {$reset_assertion_level == "low" ? 1 : 0}]
set reset_cmds ""
if {$reset_assertion_level ne ""} {
    for {set i 1} {$i <= $reset_duration} {incr i} {
        append reset_cmds " -set-at $i in_$reset_signal_name $reset_level"
    }
    for {set i [expr $reset_duration + 1]} {$i <= $seq_value + 1} {incr i} {
        append reset_cmds " -set-at $i in_$reset_signal_name $operational_level"
    }
}
set sat_cmd "sat -show-all -seq 19 -prove-asserts -enable_undef -set-init-zero $reset_cmds -dump_vcd tmp/fev.vcd miter"
puts $sat_cmd
yosys $sat_cmd
