EQY := eqy

test: adder/PASS 

adder/PASS: adder.eqy adder.v adderc.v
	$(EQY) -f adder.eqy


clean:
	rm -rf adder/
.PHONY: test clean
