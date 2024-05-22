.DEFAULT_GOAL := all

strategies/adder.sum/simple/status:
	@echo "Running strategy 'simple' on 'adder.sum'.."
	@bash -c "cd strategies/adder.sum/simple; source run.sh"

strategies/adder.carry/simple/status:
	@echo "Running strategy 'simple' on 'adder.carry'.."
	@bash -c "cd strategies/adder.carry/simple; source run.sh"

.PHONY: all summary
all: strategies/adder.carry/simple/status strategies/adder.sum/simple/status
	$(MAKE) -f strategies.mk summary
summary:
	@rc=0 ; \
	while read f; do \
		p=$${f#strategies/} ; p=$${p%/*/status} ; \
		if grep -q "PASS" $$f ; then \
			echo "* Successfully proved equivalence of partition $$p" ; \
		else \
			echo "* Failed to prove equivalence of partition $$p" ; rc=1 ; \
		fi ; \
	done < summary_targets.list ; \
	if [ "$$rc" -eq 0 ] ; then \
		echo "* Successfully proved designs equivalent" ; \
	fi
