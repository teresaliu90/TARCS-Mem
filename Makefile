.PHONY: test lint package evaluate evaluate-public serve

test:
	python -m pytest -q

lint:
	python -m ruff check src tests
	python -m ruff format --check src tests

package:
	python -m build

evaluate:
	PYTHONPATH=src python -m tarcsmem evaluate --db ./data/tarcsmem.db

evaluate-public:
	PYTHONPATH=src python -m tarcsmem evaluate-public --queries 120 --distractors 300 --output ./docs/benchmarks/fiqa-public-report.json

serve:
	PYTHONPATH=src python -m tarcsmem serve --db ./data/tarcsmem.db
