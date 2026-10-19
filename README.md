# AI investment comparison

A historical portfolio experiment: give each model the same dated market context, let it select investments and target weights, and simulate the resulting portfolio with identical deposits and trading costs. This is a general simulated brokerage account, not a Roth IRA tax/contribution-rule simulator.

The default command is an **offline synthetic demonstration**. It makes no API requests and its mock strategy is not an AI result.

## Setup

Run from this project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python run_experiment.py
```

In VS Code, select `.venv/bin/python` as the interpreter. Open `runs/demo/report.html` for the demo comparison. The original `python -m simulation.portfolio` sample remains available.

`.env` has been created with blank credentials. `.env.example` documents the settings and is safe to commit. `.env`, `.venv`, generated runs, price caches, raw response caches, and the API budget database are ignored by Git. Never put keys in source files or chat. Existing tracked bytecode files are not removed by adding ignore rules.

## Enable API providers

ChatGPT/Codex and Gemini consumer subscriptions do not establish API credentials or API billing for this runner. Create separate provider API keys and paste them into your local `.env`:

- Groq: `GROQ_API_KEY`, `GROQ_MODEL`.
- Gemini: `GEMINI_API_KEY`, `GEMINI_MODEL`.
- Optional OpenAI: `OPENAI_API_KEY`, `OPENAI_MODEL`.

Use exact API model IDs available to your account, not app display names. Set each provider's `INPUT_PRICE` and `OUTPUT_PRICE` to its current USD price per million tokens, including billable reasoning output. Zero is valid only for genuinely free API usage; Groq's template assumes the free plan. Free quotas depend on the selected model/account, not a universal requests-per-day number.

Official documentation:

- [Groq OpenAI compatibility](https://console.groq.com/docs/openai) and [rate limits](https://console.groq.com/docs/rate-limits).
- [Gemini OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai) and [API pricing](https://ai.google.dev/gemini-api/docs/pricing).
- [OpenAI Chat Completions](https://platform.openai.com/docs/api-reference/chat/create) and [API pricing](https://openai.com/api/pricing/).

The common adapter requests JSON using Chat Completions. Provider/model support varies; live compatibility cannot be confirmed without your keys. A rejected request is recorded as a failure rather than silently switching models or retrying.

Start with a two-review pilot:

```bash
python run_experiment.py --live --providers groq gemini \
  --start 2019-01-01 --end 2019-06-30 --output runs/pilot
```

For just Groq, use `--providers groq`. When the pilot passes, run the configured full date interval:

```bash
python run_experiment.py --live --providers groq gemini --output runs/full
```

**Budget:** all live runs share `.cache/api_budget.sqlite3` and a $5 application-level cap. The runner reserves conservative input/output costs before calling, then settles using returned token usage. Failed/uncertain calls keep their reservation and are not automatically retried. An explicit HTTP 429 rejection releases its reservation; wait for the provider quota to reset, then rerun. Responses are cached before decision validation; rerunning identical requests reuses them. Do not delete the ledger to retry a failed request. Inspect provider usage first. Correct pricing is essential: this cap is an estimate based on supplied prices, not a provider-enforced billing limit. Set provider billing limits too where available. Never share the `.cache` directory, since it contains prompts and household data.

## Files to customize

| File | Purpose |
| --- | --- |
| `savings_calculations/household.py` | Household inputs and constraints |
| `model_decisions/investment.py` | Starting capital, monthly contribution, dates, review frequency, trade fee rate |
| `prompts/investment_prompt.md` | Common model instructions |
| `prompts/decision_validation.py` | Strict response validation |
| `config/assets.json` | Verified ticker-to-category registry |
| `config/events.json` | Optional historically available economic information |
| `market_data/store.py` | Historical downloads, caches, trailing returns |
| `model_decisions/api.py` | Provider adapters, response cache, budget ledger |
| `simulation/engine.py` | Persistent holdings and contribution/rebalance accounting |
| `run_experiment.py` | Dated decision loop and experiment artifacts |
| `simulation/reporting.py` | Comparison CSV and HTML |
| `tests/test_pipeline.py` | Offline accounting and integration tests |

The inherited `transaction_costs = 0.01` means **1% of every purchase and sale**, not 0.01%. It is an experimental assumption, not an estimate of typical broker commissions. Choose the assumption before running comparisons and keep it identical across providers. Initial capital is pre-existing investment money; monthly contributions are a separate input and should be checked against household surplus.

## Market context and asset choice

Models may propose any eligible Yahoo Finance identifier in the five permitted categories. They are not restricted to the small registry. If a proposed ticker is absent from `config/assets.json`, the run stops after saving the response. Verify the instrument's category, add it to the registry, and rerun: the saved response is reused. ETF classifications require human verification; a successful price download alone does not prove that an ETF is broad equity, Treasury-only, or unleveraged. Symbols such as `^TNX` are yields, not investable bond prices.

Every chosen noncash asset must have observed prices on/before the decision cutoff and on each session where it is held. Missing data fails the run; the runner does not silently fill prices, replace assets, or discard holdings. Prior prices are evidence of historical availability, not complete security-master verification. Delistings and ticker changes require better data before those runs can be completed.

The built-in common packet contains trailing 21/63/126/252-session returns for SPY, TLT, and AAPL. No full future price series is sent to models. **By default there is no macroeconomic news context**, so the experiment measures reactions to market returns rather than a full economic briefing.

To add economic context, put events in `config/events.json`:

```json
[
  {
    "published_at": "2019-01-15 12:00:00",
    "description": "Replace this with a verified historical release and its original reported value.",
    "source": "URL or archived source citation"
  }
]
```

This is a format example, not an actual historical fact. Use the original release/vintage, not today's revised observation. Timestamps are naive UTC. Only events published by the cutoff are sent. Review cutoffs use midnight UTC on the preceding available session; this is deliberately conservative about same-day releases. Models can still recall future historical events from training, so results are hindsight-exposed historical performance, not evidence of prospective forecasting skill.

## Simulation conventions

- The SPY trading-session calendar is shared by all portfolios. Crypto is valued/traded on these same sessions; weekend trading is excluded.
- Initial capital and the first monthly contribution arrive on the first execution session. Subsequent contributions arrive on the first available session of each calendar month.
- An initial decision is made before the first execution. Further reviews happen on the first session of each monthly/quarterly/annual calendar period, using context through the prior available session. Execution uses the later session's close.
- Existing positions earn returns before new trades execute. Between reviews, deposits buy the latest target weights without rebalancing existing positions.
- At reviews, both selling and buying incur costs. The engine solves for affordable post-fee target holdings, so it cannot borrow to pay fees.
- Holdings are dollar positions updated by adjusted-close ratios, approximating reinvested-distribution total returns. They are not actual executable share quantities. Do not separately credit dividends or subtract ETF operating fees already reflected in prices.
- Cash earns zero interest. Fractional positions are allowed. No taxes, explicit spreads/slippage, leverage, or short sales.
- Baselines are cash and a 60/40 SPY/TLT portfolio rebalanced on the same schedule. The demo also includes a deterministic mock strategy.

## Artifacts and interpretation

Each output folder contains `manifest.json`, `status.json`, input price snapshots, accepted decisions, exact request packets, response metadata, daily portfolio CSVs, final holdings, `summary.csv`, and `report.html`.

The report shows ending value, net gain after contributions, trading fees, time-weighted return, and cash-flow-adjusted maximum drawdown. Invalid or failed strategies are excluded from performance comparisons and retained in `status.json`. Attempted and accepted decision counts provide a first reliability check; a stopped run's rate is not an unbiased estimate of long-run model reliability. Token usage, request latency, cached-response status, and API cost estimates are saved beside each response. The shared budget ledger accounts for uncertain calls as well.

Use a new output directory when changing the prompt, model, dates, household, events, or pricing. Identical reruns replay cached decisions, so they are not independent trials. Repeated independent samples and wider asset coverage are future extensions; this version is a single reproducible run per configured provider/model.
