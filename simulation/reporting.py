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
        costs = [r["api"].get("cost_usd") for r in responses]
        rows.append({"strategy": name, "ending_value": last["portfolio_value"],
                     "contributions": last["total_contributed"], "net_gain": last["net_gain"],
                     "trading_fees": last["total_fees"],
                     "time_weighted_return": last["time_weighted_return"],
                     "max_drawdown": frame["drawdown"].min(),
                     "valid_decisions": statuses[name]["valid_decisions"],
                     "api_cost_usd": sum(costs) if all(c is not None for c in costs) else None,
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
