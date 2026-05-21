.PHONY: install test clean run

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt -r requirements-dev.txt

test:
	python -m pytest tests/ -v --cov=src --cov-report=term-missing

run:
	python -m src.main --spec configs/uart_demo.yaml

run-json:
	python -m src.main --spec configs/uart_demo.yaml --json

eval-only:
	python -m src.main --spec configs/uart_demo.yaml --eval-only

clean:
	rm -rf output/* logs/* .pytest_cache __pycache__ */__pycache__ */*/__pycache__
	rm -rf models/saved/*.json

docker-build:
	docker build -t uvm-tb-generator .

docker-run:
	docker run --rm -v $(PWD)/output:/app/output uvm-tb-generator --spec configs/uart_demo.yaml

lint:
	python -m flake8 src/ tests/
