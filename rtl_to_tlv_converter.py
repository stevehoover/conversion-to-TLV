import re
import json
from typing import Dict, List, Tuple

class RTLToTLVConverter:
    def __init__(self):
        # Training patterns learned from D Flip-Flop
        self.patterns = {
            'clock_edge': {
                'rtl': r'always\s*@\s*\(\s*posedge\s+(\w+)\s*\)',
                'tlv': 'event {clk}_posedge;\nalways @(posedge {clk}) -> {clk}_posedge;'
            },
            'reset': {
                'rtl': r'if\s*\(\s*!\s*(\w+)\s*\)\s*(\w+)\s*<=\s*0',
                'tlv': 'property reset_property;\n    @(negedge {rst}) {q} == 0;\nendproperty'
            },
            'enable': {
                'rtl': r'else\s+if\s*\(\s*(\w+)\s*\)\s*(\w+)\s*<=\s*(\w+)',
                'tlv': 'property enable_property;\n    @(posedge {clk}) disable iff (!{rst})\n        if ({enable}) {q} == {d};\nendproperty'
            }
        }

    def convert_rtl_to_tlv(self, rtl_code: str) -> str:
        """Convert RTL code to TLV using learned patterns"""
        tlv_code = []
        
        # Extract module parameters and ports
        module_info = self._extract_module_info(rtl_code)
        tlv_code.append(self._generate_module_header(module_info))
        
        # Convert clock edge detection
        tlv_code.append(self._convert_clock_edge(rtl_code))
        
        # Convert reset logic
        tlv_code.append(self._convert_reset(rtl_code))
        
        # Convert enable logic
        tlv_code.append(self._convert_enable(rtl_code))
        
        # Add clock stability property
        tlv_code.append(self._generate_clock_property(module_info))
        
        # Add assertions
        tlv_code.append(self._generate_assertions(rtl_code))
        
        return '\n'.join(tlv_code)

    def _extract_module_info(self, rtl_code: str) -> Dict:
        """Extract module name, parameters, and ports"""
        # Extract module name
        name_match = re.search(r'module\s+(\w+)', rtl_code)
        module_name = name_match.group(1) if name_match else 'module_name'
        
        # Extract parameters
        param_match = re.search(r'parameter\s+(\w+)\s*=\s*(\d+)', rtl_code)
        params = {}
        if param_match:
            params[param_match.group(1)] = int(param_match.group(2))
        
        # Extract ports
        ports = {}
        port_pattern = r'(input|output)\s+(wire|reg)\s+(?:\[(\w+)-1:0\])?\s*(\w+)'
        for match in re.finditer(port_pattern, rtl_code):
            direction, type_, width, name = match.groups()
            width_str = f"[{width}-1:0] " if width else ""
            ports[name] = {
                'direction': direction,
                'type': type_,
                'width': width,
                'declaration': f"{direction} {type_} {width_str}{name}"
            }
        
        return {
            'name': module_name,
            'params': params,
            'ports': ports
        }

    def _generate_module_header(self, info: Dict) -> str:
        """Generate TLV module header"""
        # Generate parameter string
        param_str = ""
        if info['params']:
            param_str = "#(\n    " + ",\n    ".join(f"parameter {k} = {v}" for k, v in info['params'].items()) + "\n)"
        
        # Generate port declarations
        port_declarations = []
        for name, port in info['ports'].items():
            port_declarations.append(port['declaration'])
        
        port_str = "(\n    " + ",\n    ".join(port_declarations) + "\n)"
        
        return f"module {info['name']}_tlv {param_str}{port_str};"

    def _convert_clock_edge(self, rtl_code: str) -> str:
        """Convert clock edge detection to event-based modeling"""
        clk_match = re.search(self.patterns['clock_edge']['rtl'], rtl_code)
        if clk_match:
            clk = clk_match.group(1)
            return self.patterns['clock_edge']['tlv'].format(clk=clk)
        return ""

    def _convert_reset(self, rtl_code: str) -> str:
        """Convert reset logic to property"""
        reset_match = re.search(self.patterns['reset']['rtl'], rtl_code)
        if reset_match:
            rst, q = reset_match.groups()
            return self.patterns['reset']['tlv'].format(rst=rst, q=q)
        return ""

    def _convert_enable(self, rtl_code: str) -> str:
        """Convert enable logic to property"""
        enable_match = re.search(self.patterns['enable']['rtl'], rtl_code)
        if enable_match:
            enable, q, d = enable_match.groups()
            # Special handling for counter increment
            if '+' in rtl_code:
                return f"""property enable_property;
    @(posedge clk) disable iff (!rst_n)
        if ({enable}) {q} == $past({q}) + 1;
endproperty"""
            return self.patterns['enable']['tlv'].format(
                clk='clk', rst='rst_n', enable=enable, q=q, d=d)
        return ""

    def _generate_clock_property(self, info: Dict) -> str:
        """Generate clock stability property"""
        # Find output register
        output_reg = None
        for name, port in info['ports'].items():
            if port['direction'] == 'output' and port['type'] == 'reg':
                output_reg = name
                break
        
        if output_reg:
            return f"""property clock_property;
    @(posedge clk) disable iff (!rst_n)
        if (!enable) $stable({output_reg});
endproperty"""
        return ""

    def _generate_assertions(self, rtl_code: str) -> str:
        """Generate TLV assertions"""
        return """
    // Assert the properties
    assert property (reset_property) else $error("Reset failed");
    assert property (enable_property) else $error("Enable failed");
    assert property (clock_property) else $error("Clock failed");
    
endmodule"""

def main():
    # Example usage
    converter = RTLToTLVConverter()
    
    # Example RTL input
    rtl_input = """
    module counter #(
        parameter WIDTH = 4
    )(
        input wire clk,
        input wire rst_n,
        input wire enable,
        output reg [WIDTH-1:0] count
    );

        always @(posedge clk) begin
            if (!rst_n) count <= 0;
            else if (enable) count <= count + 1;
        end

    endmodule
    """
    
    # Convert to TLV
    tlv_output = converter.convert_rtl_to_tlv(rtl_input)
    
    # Print results
    print("Input RTL:")
    print(rtl_input)
    print("\nOutput TLV:")
    print(tlv_output)

if __name__ == "__main__":
    main() 