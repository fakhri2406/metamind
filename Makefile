.PHONY: install lint test run help

install:
	pip install -r requirements.txt

lint:
	ruff check .

lint-fix:
	ruff check --fix .

test:
	pytest tests/ -v

run:
	python main.py run

help:
	python main.py --help
