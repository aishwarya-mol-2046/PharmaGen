.PHONY: help install install-dev bootstrap test test-coverage lint format typecheck clean clean-db clean-all run backend frontend all

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	pip install -r requirements.txt

install-dev: ## Install development dependencies
	pip install -r requirements-dev.txt
	pre-commit install

bootstrap: ## Initialize the clinical knowledge base from CIViC
	python -m backend.app.db.bootstrap

test: ## Run all tests
	python -m pytest tests/ -v

test-coverage: ## Run tests with coverage report
	python -m pytest tests/ -v --cov=backend --cov-report=term-missing

lint: ## Run linter
	ruff check backend/ frontend/ tests/ convert_patient_vcf.py

format: ## Format code
	ruff format backend/ frontend/ tests/ convert_patient_vcf.py

typecheck: ## Run type checker
	mypy backend/ --ignore-missing-imports

clean: ## Clean generated files (caches only, DB preserved)
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	rm -rf backend/**/__pycache__ frontend/**/__pycache__ tests/**/__pycache__
	rm -f frontend_graph.html

clean-db: ## Clean clinical knowledge base DB (use with care)
	rm -rf backend/data/raw/*.db

clean-all: ## Clean everything (caches + DB)
	$(MAKE) clean
	$(MAKE) clean-db

run: ## Run both backend and frontend
	./run.sh

backend: ## Run backend only
	uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000

frontend: ## Run frontend only
	streamlit run frontend/app.py --server.port 8501

demo: ## Generate demo VCF and run analysis
	python convert_patient_vcf.py --generate-demo --demo-count 50 demo.vcf
	@echo "Demo VCF generated: demo.vcf"

all: install-dev bootstrap test ## Full setup: install, bootstrap KB, run tests
