#!/usr/bin/env bash

PROJECT_DIR="qest-portfolio-qaoa"

echo "Creating project directory structure..."
mkdir -p "$PROJECT_DIR"/{data/{raw,processed},configs,notebooks,src/{data,problem,quantum,pipeline},scripts,results/logs}

cd "$PROJECT_DIR" || exit

echo "Creating Python package __init__.py files..."
touch src/__init__.py src/data/__init__.py src/problem/__init__.py src/quantum/__init__.py src/pipeline/__init__.py

echo "Creating core module files..."
touch src/data/{loader.py,constraints.py}
touch src/problem/{qubo_builder.py,classical_solver.py}
touch src/quantum/{ansatzes.py,optimizers.py,execution.py}
touch src/pipeline/{evaluator.py,runner.py}
touch scripts/run_experiment.py

echo "Creating configuration and notebook files..."
touch configs/{ibm_provider.yaml,grid_search.yaml}
touch notebooks/01_data_exploration.ipynb

echo "Writing requirements.txt..."
cat << 'EOF' > requirements.txt
qiskit>=1.0.0
qiskit-ibm-runtime
qiskit-optimization
qiskit-algorithms
pandas
numpy
scipy
yfinance
pyyaml
jupyter
EOF

echo "Writing README.md..."
cat << 'EOF' > README.md
# Coop Pank QAOA Portfolio Optimization

## Setup
1. Activate your virtual environment.
2. Run `pip install -r requirements.txt`
3. Place `qest_stock_data.csv` and `qest_correlation_2021_2024.csv` into `data/raw/`
4. Configure your Qiskit Runtime credentials in `configs/ibm_provider.yaml`
EOF

echo "Writing .gitignore..."
cat << 'EOF' > .gitignore
# Python
__pycache__/
*.py[cod]
.venv/
venv/
.env

# Data & Secrets (Keep raw data and API keys out of version control)
data/raw/*.csv
configs/ibm_provider.yaml
results/logs/*.csv
results/logs/*.json
EOF

echo "Setting up Python virtual environment..."
python -m venv .venv

echo "================================================="
echo "Project scaffolding complete in ./$PROJECT_DIR"
echo "To get started, run:"
echo "  cd $PROJECT_DIR"
echo "  source .venv/bin/activate"
echo "  pip install -r requirements.txt"
echo "================================================="