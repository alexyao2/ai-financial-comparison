"""Write the comparison CSV and HTML report."""
import html
import json
import pandas as pd


def write_report(output, frames, statuses, mode):
    rows = []
    for name, frame in frames.items():
        last = frame.iloc[-1]
        responses = [json.loads(p.read_text())
                     for p in (output / name / "decisions").glob("*.response.json")]
        rows.append({"strategy": name, "ending_value": last["portfolio_value"],
                     "contributions": last["total_contributed"], "net_gain": last["net_gain"],
                     "trading_fees": last["total_fees"],
                     "time_weighted_return": last["time_weighted_return"],
                     "max_drawdown": frame["drawdown"].min(),
                     "valid_decisions": statuses[name]["valid_decisions"],
                     "mean_request_seconds": sum(r["latency_seconds"] for r in responses) / max(len(responses), 1),
                     "cached_decisions": sum(bool(r["api"].get("cache_hit")) for r in responses)})
    summary = pd.DataFrame(rows)
    summary.to_csv(output / "summary.csv", index=False)
    chart = ""
    if frames:
        values = [float(v) for frame in frames.values() for v in frame.portfolio_value]
        lo, hi = min(values), max(values)
        span = max(hi-lo, 1)
        lines = []
        for i,(name,frame) in enumerate(frames.items()):
            color = ["#64748b", "#2563eb", "#059669", "#c026d3", "#ea580c"][i % 5]
            points = " ".join(f"{40+840*j/max(len(frame)-1,1):.1f},{250-210*(float(v)-lo)/span:.1f}"
                              for j,v in enumerate(frame.portfolio_value))
            lines.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{points}"/>')
            lines.append(f'<text x="{40+i*160}" y="290" fill="{color}">{html.escape(name)}</text>')
        chart = '<svg viewBox="0 0 920 310" role="img" aria-label="Portfolio value over trading sessions">'+''.join(lines)+f'<text x="40" y="20">Portfolio value: ${lo:,.0f}–${hi:,.0f}; time runs left to right</text></svg>'
    body = summary.to_html(index=False, float_format=lambda v: f"{v:,.4f}") if rows else "No complete strategies."
    failures = html.escape(json.dumps({n:s for n,s in statuses.items() if s["status"] != "complete"}, indent=2))
    (output / "report.html").write_text(f"""<!doctype html><html><head><meta charset="utf-8"><title>Investment comparison</title>
    <style>body{{font:16px system-ui;max-width:1100px;margin:40px auto;padding:20px;color:#172033}}table{{border-collapse:collapse;font-size:13px}}td,th{{padding:10px;border-bottom:1px solid #ddd}}svg{{width:100%}}pre{{white-space:pre-wrap}}</style></head>
    <body><h1>Investment comparison</h1><p><strong>{html.escape(mode)}</strong></p>
    <p>Identical deposits, execution calendar, and trading fees. Returns and drawdowns are decimal fractions; time-weighted metrics remove external cash flows.</p>
    {chart}{body}<h2>Incomplete runs (not ranked)</h2><pre>{failures}</pre>
    <p>Historical results can reflect model recall. Adjusted-close dollar positions approximate total returns, not executable share accounting. No taxes, spreads, or interest beyond configured trading costs. See manifest.json and saved decisions for provenance.</p></body></html>""")


def write_period_report(output, frame, decision, opening, opening_fees, opening_index, closing):
    """Persist a completed review period before requesting the next decision."""
    output.mkdir(parents=True, exist_ok=True)
    last = frame.iloc[-1]
    contributions = closing["total_contributed"] - opening["total_contributed"]
    report = {
        "start_date": str(frame.index[0].date()), "end_date": str(frame.index[-1].date()),
        "decision": decision, "opening_portfolio": opening, "closing_portfolio": closing,
        "contributions": contributions, "trading_fees": float(last["total_fees"] - opening_fees),
        "net_gain": closing["portfolio_value"] - opening["portfolio_value"] - contributions,
        "time_weighted_return": float((1 + last["time_weighted_return"]) / opening_index - 1),
    }
    stem = output / report["start_date"]
    frame.to_csv(stem.with_suffix(".csv"))
    text = json.dumps(report, indent=2, allow_nan=False)
    temporary = stem.with_suffix(".tmp")
    temporary.write_text(text)
    temporary.replace(stem.with_suffix(".json"))
    stem.with_suffix(".html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Period report</title>'
        f'<h1>{report["start_date"]} to {report["end_date"]}</h1>'
        f'<pre>{html.escape(text)}</pre>')
