EQY := eqy

test: aliases/PASS 

aliases/PASS: aliases.eqy aliases.sv aliases.s.sv 
	$(EQY) -f aliases.eqy

clean:
	rm -rf aliases/ 
.PHONY: test clean
