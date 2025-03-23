# 4-bit Counter: Verilog to TL-Verilog Conversion Example

This example demonstrates the conversion of a simple 4-bit counter from Verilog to TL-Verilog.

## Design Overview

The counter has the following features:
- 4-bit output
- Synchronous reset
- Enable input
- Counts up when enabled

## Files

- `counter.v` - Original Verilog implementation
- `counter_tb.v` - Verilog testbench
- `counter.tlv` - TL-Verilog implementation

## Conversion Process

### 1. Understanding the Original Design
The Verilog design uses:
- An always block triggered by clock edge
- Reset logic inside the always block
- Enable signal for conditional counting

### 2. TL-Verilog Changes
Key changes in the TL-Verilog version:
- Removed explicit clock handling
- Used pipeline stage (@0)
- Used retiming operator (>>1) for previous value
- Simplified conditional logic using ?:
- More declarative style

### 3. Learnings
- TL-Verilog makes timing more implicit
- No need for explicit clock handling
- More concise representation
- Easier to understand intent
- Better separation of timing and functionality

## Testing

To test the designs:

1. Verilog Version:
   ```bash
   # Compile and run Verilog testbench
   iverilog -o counter_tb counter.v counter_tb.v
   ./counter_tb
   ```

2. TL-Verilog Version:
   ```bash
   # Use SandPiper-SaaS for compilation
   sandpiper-saas -i counter.tlv -o counter_tlv.v
   ```

## Verification

The designs can be verified for equivalence using:
```bash
# Run formal equivalence verification
./convert.py examples/counter/counter.v
``` 