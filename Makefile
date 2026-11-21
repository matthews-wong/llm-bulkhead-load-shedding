.PHONY: test simulate validate

test:
	python3 -m unittest discover -s tests -t . -q

simulate:
	PYTHONPATH=. python3 scripts/simulate.py

validate: test simulate
