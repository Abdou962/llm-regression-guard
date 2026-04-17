import html as _html


def _esc(text: str) -> str:
    """Escape HTML special characters to prevent XSS injection."""
    if not isinstance(text, str):
        text = str(text)
    return _html.escape(text, quote=True)


def generate_html_report(diff_data, prev_data, curr_data, metadata, trend_data):
    prev_map = {str(item.get('id', '')): item for item in prev_data}
    curr_map = {str(item.get('id', '')): item for item in curr_data}

    css = """
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; background-color: #f0f2f5; padding: 24px; line-height: 1.5; color: #1a1a2e; }}
        .report-container {{ max-width: 1400px; margin: 0 auto; background: white; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); overflow: hidden; }}
        .report-header {{ background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); color: white; padding: 32px; }}
        .report-header h1 {{ font-size: 28px; font-weight: 600; margin-bottom: 8px; }}
        .report-header p {{ opacity: 0.85; font-size: 14px; }}
        .section {{ padding: 28px 32px; border-bottom: 1px solid #e9ecef; }}
        .section-title {{ font-size: 20px; font-weight: 600; color: #1e3c72; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #e9ecef; }}
        .metadata-grid {{ background: #f8f9fa; border-radius: 8px; padding: 20px; display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; }}
        .metadata-item {{ display: flex; flex-direction: column; }}
        .metadata-label {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; color: #6c757d; margin-bottom: 4px; }}
        .metadata-value {{ font-size: 16px; font-weight: 500; color: #1a1a2e; word-break: break-all; }}
        .scorecard-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 20px; }}
        .scorecard-card {{ background: #f8f9fa; border-radius: 10px; padding: 20px; text-align: center; border-left: 4px solid #2a5298; }}
        .scorecard-label {{ font-size: 13px; text-transform: uppercase; color: #6c757d; letter-spacing: 0.5px; }}
        .scorecard-value {{ font-size: 32px; font-weight: 700; margin: 12px 0; }}
        .scorecard-delta {{ font-size: 14px; font-weight: 500; }}
        .flag-critical {{ background: #dc3545; color: white; padding: 6px 16px; border-radius: 20px; display: inline-block; font-weight: 600; font-size: 14px; }}
        .flag-warning {{ background: #ffc107; color: #1a1a2e; padding: 6px 16px; border-radius: 20px; display: inline-block; font-weight: 600; font-size: 14px; }}
        .flag-ok {{ background: #28a745; color: white; padding: 6px 16px; border-radius: 20px; display: inline-block; font-weight: 600; font-size: 14px; }}
        .data-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
        .data-table th {{ background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; border-bottom: 2px solid #dee2e6; }}
        .data-table td {{ padding: 12px; border-bottom: 1px solid #e9ecef; vertical-align: top; }}
        .data-table tr:hover {{ background: #f8f9fa; }}
        .regression-row {{ background: #fff5f5; }}
        .improvement-row {{ background: #f0fff4; }}
        .badge-regression {{ background: #dc3545; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }}
        .badge-improvement {{ background: #28a745; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }}
        .trend-chart {{ background: #f8f9fa; border-radius: 8px; padding: 20px; text-align: center; }}
        .report-footer {{ background: #f8f9fa; padding: 20px 32px; text-align: center; font-size: 12px; color: #6c757d; }}
        .text-positive {{ color: #28a745; font-weight: 600; }}
        .text-negative {{ color: #dc3545; font-weight: 600; }}
        .text-neutral {{ color: #6c757d; }}
        .summary-stats {{ display: flex; gap: 24px; margin-top: 20px; padding: 16px; background: #f8f9fa; border-radius: 8px; }}
        .stat {{ flex: 1; text-align: center; }}
        .stat-number {{ font-size: 28px; font-weight: 700; }}
        .stat-label {{ font-size: 12px; color: #6c757d; margin-top: 4px; }}
        @media (max-width: 768px) {{ .scorecard-grid {{ grid-template-columns: 1fr; }} .data-table {{ font-size: 12px; }} .section {{ padding: 20px; }} }}
    </style>
    """

    delta = diff_data['delta']
    flag = diff_data['flag']
    if delta > 0:
        delta_class = "text-positive"
        delta_sign = f"+{delta:.2%}"
    elif delta < 0:
        delta_class = "text-negative"
        delta_sign = f"{delta:.2%}"
    else:
        delta_class = "text-neutral"
        delta_sign = f"{delta:.2%}"
    flag_class = f"flag-{flag.lower()}"
    regressions_list = diff_data.get('regressions', [])
    improvements_list = diff_data.get('improvements', [])

    html = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>Classification Diff Report - {metadata['timestamp']}</title>
    {css}
</head>
<body>
<div class=\"report-container\">
    <div class=\"report-header\">
        <h1>Classification Regression Report</h1>
        <p>Comparison between baseline and current evaluation run</p>
    </div>
    <div class=\"section\">
        <h2 class=\"section-title\">Run Metadata</h2>
        <div class=\"metadata-grid\">
            <div class=\"metadata-item\"><div class=\"metadata-label\">Prompt Version</div><div class=\"metadata-value\">{metadata['prompt_version']}</div></div>
            <div class=\"metadata-item\"><div class=\"metadata-label\">Prompt Timestamp</div><div class=\"metadata-value\">{metadata['prompt_timestamp']}</div></div>
            <div class=\"metadata-item\"><div class=\"metadata-label\">Model</div><div class=\"metadata-value\">{metadata['model']}</div></div>
            <div class=\"metadata-item\"><div class=\"metadata-label\">Run Timestamp</div><div class=\"metadata-value\">{metadata['timestamp']}</div></div>
            <div class=\"metadata-item\"><div class=\"metadata-label\">Dataset Size</div><div class=\"metadata-value\">{metadata['dataset_size']} cases</div></div>
            <div class=\"metadata-item\"><div class=\"metadata-label\">Thresholds</div><div class=\"metadata-value\">Warning: {metadata.get('warning_threshold', 3)}% | Critical: {metadata.get('critical_threshold', 8)}%</div></div>
        </div>
    </div>
    <div class=\"section\">
        <h2 class=\"section-title\">Performance Scorecard</h2>
        <div class=\"scorecard-grid\">
            <div class=\"scorecard-card\"><div class=\"scorecard-label\">Baseline Pass Rate</div><div class=\"scorecard-value\">{diff_data['global_pass_rate_prev']:.2%}</div></div>
            <div class=\"scorecard-card\"><div class=\"scorecard-label\">Current Pass Rate</div><div class=\"scorecard-value\">{diff_data['global_pass_rate_curr']:.2%}</div></div>
            <div class=\"scorecard-card\"><div class=\"scorecard-label\">Delta</div><div class=\"scorecard-value {delta_class}\">{delta_sign}</div></div>
            <div class=\"scorecard-card\"><div class=\"scorecard-label\">Status</div><div class=\"scorecard-value\"><span class=\"{flag_class}\">{flag}</span></div></div>
        </div>
    </div>
    <div class=\"section\">
        <h2 class=\"section-title\">Per-Category Accuracy</h2>
        <table class=\"data-table\"><thead><tr><th>Category</th><th>Baseline</th><th>Current</th><th>Delta</th></tr></thead><tbody>
"""
    all_cats = set(diff_data['per_category_prev'].keys()) | set(diff_data['per_category_curr'].keys())
    for cat in sorted(all_cats):
        p = diff_data['per_category_prev'].get(cat, 0.0)
        c = diff_data['per_category_curr'].get(cat, 0.0)
        cat_delta = c - p
        if cat_delta > 0.03:
            delta_class = "text-positive"
            delta_sign_cat = f"+{cat_delta:.2%}"
        elif cat_delta < -0.03:
            delta_class = "text-negative"
            delta_sign_cat = f"{cat_delta:.2%}"
        else:
            delta_class = "text-neutral"
            delta_sign_cat = f"{cat_delta:+.2%}"
        html += f"<tr><td><strong>{_esc(cat)}</strong></td><td>{p:.2%}</td><td>{c:.2%}</td><td class=\"{delta_class}\">{delta_sign_cat}</td></tr>"
    html += """</tbody></table></div><div class=\"section\"><div class=\"summary-stats\"><div class=\"stat\"><div class=\"stat-number\">{regression_count}</div><div class=\"stat-label\">Regressions (Pass to Fail)</div></div><div class=\"stat\"><div class=\"stat-number\">{improvement_count}</div><div class=\"stat-label\">Improvements (Fail to Pass)</div></div><div class=\"stat\"><div class=\"stat-number\">{len_curr}</div><div class=\"stat-label\">Total Cases</div></div></div></div>"""
    html = html.format(regression_count=len(regressions_list), improvement_count=len(improvements_list), len_curr=len(curr_data))
    html += """<div class=\"section\"><h2 class=\"section-title\">Regressions (Pass to Fail)</h2>"""
    if regressions_list:
        html += """<table class=\"data-table\"><thead><tr><th>ID</th><th>Input</th><th>Expected Output</th><th>Previous Output</th><th>Current Output</th></tr></thead><tbody>"""
        for case_id in regressions_list:
            old = prev_map.get(str(case_id), {})
            new = curr_map.get(str(case_id), {})
            input_text = old.get('input', '') or new.get('input', '') or ''
            if len(input_text) > 150:
                input_text = input_text[:150] + "..."
            expected = old.get('expected_output', new.get('expected_output', {}))
            if isinstance(expected, dict):
                expected_str = f"{expected.get('category', '?')}: {expected.get('summary', '?')}"
            else:
                expected_str = str(expected)
            old_output = old.get('raw_output', '?')
            new_output = new.get('raw_output', '?')
            html += f"<tr class=\"regression-row\"><td><strong>{_esc(str(case_id))}</strong></td><td>{_esc(input_text)}</td><td>{_esc(expected_str)}</td><td>{_esc(old_output)}</td><td>{_esc(new_output)}</td></tr>"
        html += """</tbody></table>"""
    else:
        html += '<p>No regressions detected. All passing cases remain passing.</p>'
    html += """</div><div class=\"section\"><h2 class=\"section-title\">Improvements (Fail to Pass)</h2>"""
    if improvements_list:
        html += """<table class=\"data-table\"><thead><tr><th>ID</th><th>Input</th><th>Expected Output</th><th>Previous Output</th><th>Current Output</th></tr></thead><tbody>"""
        for case_id in improvements_list:
            old = prev_map.get(str(case_id), {})
            new = curr_map.get(str(case_id), {})
            input_text = old.get('input', '') or new.get('input', '') or ''
            if len(input_text) > 150:
                input_text = input_text[:150] + "..."
            expected = old.get('expected_output', new.get('expected_output', {}))
            if isinstance(expected, dict):
                expected_str = f"{expected.get('category', '?')}: {expected.get('summary', '?')}"
            else:
                expected_str = str(expected)
            old_output = old.get('raw_output', '?')
            new_output = new.get('raw_output', '?')
            html += f"<tr class=\"improvement-row\"><td><strong>{_esc(str(case_id))}</strong></td><td>{_esc(input_text)}</td><td>{_esc(expected_str)}</td><td>{_esc(old_output)}</td><td>{_esc(new_output)}</td></tr>"
        html += """</tbody></table>"""
    else:
        html += '<p>No improvements detected. Failing cases remain failing.</p>'
    html += """</div><div class=\"section\"><h2 class=\"section-title\">Performance Trend</h2><div class=\"trend-chart\">"""
    if len(trend_data) > 1:
        max_pass = max(t['pass_rate'] for t in trend_data)
        min_pass = min(t['pass_rate'] for t in trend_data)
        rng = max_pass - min_pass if max_pass != min_pass else 0.01
        width = 700
        height = 300
        margin_left = 60
        margin_right = 40
        margin_top = 30
        margin_bottom = 40
        graph_width = width - margin_left - margin_right
        graph_height = height - margin_top - margin_bottom
        svg = f'<svg width="{width}" height="{height}" style="background: white; border: 1px solid #ddd; border-radius: 8px;">'
        for i in range(5):
            y = margin_top + (i * graph_height // 4)
            value = max_pass - (i * rng / 4)
            svg += f'<line x1="{margin_left}" y1="{y}" x2="{width - margin_right}" y2="{y}" stroke="#e0e0e0" stroke-width="1"/>'
            svg += f'<text x="{margin_left - 8}" y="{y + 4}" font-size="11" text-anchor="end" fill="#666">{value:.1%}</text>'
        points = []
        for i, t in enumerate(trend_data):
            x = margin_left + (i * graph_width // max(1, len(trend_data) - 1))
            y = margin_top + graph_height - int(graph_height * (t['pass_rate'] - min_pass) / rng)
            points.append((x, y))
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            svg += f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#2a5298" stroke-width="2.5" stroke-linecap="round"/>'
        for i, (x, y) in enumerate(points):
            svg += f'<circle cx="{x}" cy="{y}" r="5" fill="#2a5298" stroke="white" stroke-width="2"/>'
            svg += f'<text x="{x}" y="{y - 10}" font-size="10" text-anchor="middle" fill="#333" font-weight="bold">{trend_data[i]["pass_rate"]:.1%}</text>'
            svg += f'<text x="{x}" y="{y + 18}" font-size="9" text-anchor="middle" fill="#888">{trend_data[i]["timestamp"][:10]}</text>'
        svg += '</svg>'
        html += svg
    else:
        html += '<p>Need at least 2 runs to display trend chart.</p>'
    html += f"""</div></div><div class=\"report-footer\"><p>Generated by Classification Pipeline | Thresholds: Warning 3% | Critical 8%</p><p>Report generated on {metadata['timestamp']}</p></div></div></body></html>"""
    return html
