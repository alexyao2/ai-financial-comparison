# AI Financial Comparison

## Setup

Run these commands from the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

For live runs, create a `.env` file in the project directory with the providers you want to use:

```dotenv
NVIDIA_API_KEY=
NVIDIA_NEMOTRON_MODEL=
NVIDIA_GOOGLE_MODEL=
GEMINI_API_KEY=
GEMINI_MODEL=
GROQ_API_KEY=
GROQ_MODEL=

API_TIMEOUT_SECONDS=300
NVIDIA_NEMOTRON_MAX_OUTPUT_TOKENS=8192
GROQ_MAX_OUTPUT_TOKENS=8192
```

Fill in your API keys and model identifiers available through each provider. Both NVIDIA models share `NVIDIA_API_KEY`. Keep `.env` out of version control.

## Configure a household

- Edit `household` in `savings_calculations/household.py` for monthly income, expenses, and minimum spending.
- Edit `investment_config` in `model_decisions/investment.py` for starting capital, monthly contributions, allowed categories, and trading costs.
- Edit `prompts/investment_prompt.md` to change the investment instructions.

Household income does not automatically set the monthly contribution: it must be configured separately.

## Run

Test all three rebalance frequencies offline, without API keys:

```bash
python async_run.py \
  --start 2019-01-01 --end 2019-06-30 \
  --output runs/demo
```

Run fresh model decisions for monthly, quarterly, and annual rebalancing:

```bash
python async_run.py --live --fresh \
  --providers nvidia_nemotron nvidia_google gemini groq \
  --start 2019-01-01 --end 2019-06-30 \
  --output runs/comparison
```

Include only providers you configured. Frequencies execute sequentially.

To run one frequency:

```bash
python run_experiment.py --live --fresh \
  --providers nvidia_nemotron groq \
  --frequency quarterly \
  --start 2019-01-01 --end 2019-06-30 \
  --output runs/quarterly
```

- `--live`: use model APIs and historical market data. Without it, run synthetic data with local baseline and mock strategies.
- `--fresh`: request new model decisions instead of cached responses.
- `--overwrite`: delete the selected output folder inside `runs/` before starting again. The shared cache is retained but folder is deleted.

## View results

Open `report.html` inside the selected output folder. Batch runs also contain `monthly/`, `quarterly/`, and `annually/` reports.

- `summary.csv`: results summary
- `status.json`: completion and failure details.
- Each strategy's `decisions/`: saved prompts and responses.
- Each strategy's `periods/`: reports for individual review periods.

This project makes no live trades, this is only intended for simulation and demonstration, testing models against each other. 
Expect the live run executions to take time: endpoint connectivity can have delays.