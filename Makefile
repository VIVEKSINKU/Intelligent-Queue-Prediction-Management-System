.PHONY: all install train robustness test run-backend run-frontend clean

all: install train test

install:
	pip install -r requirements.txt
	cd frontend && npm install

train:
	python ml/train.py

robustness:
	python ml/robustness_experiment.py

test:
	pytest tests/ -v

run-backend:
	uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

run-frontend:
	cd frontend && npm run dev

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
