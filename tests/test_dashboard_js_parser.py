"""A successful HTTP deploy is not sufficient: the dashboard JavaScript must parse."""
from pathlib import Path
import shutil
import subprocess
import pytest


def test_dashboard_app_js_parses_with_node():
    node=shutil.which("node")
    if node is None:
        pytest.skip("Node runtime not installed")
    app=Path(__file__).resolve().parents[1]/"web"/"revenue-agent"/"app.js"
    proc=subprocess.run([node,"--check",str(app)],capture_output=True,
                        text=True,timeout=15)
    assert proc.returncode==0,proc.stderr


def test_application_history_renderer_is_complete():
    script=(Path(__file__).resolve().parents[1]/"web"/"revenue-agent"/"app.js").read_text("utf-8")
    assert "function renderApplicationHistory(items)" in script
    assert "function renderWorker(w)" in script
    assert "function renderCampaign(goal)" in script
    assert "renderApplicationHistory(data.application_history)" in script
    assert "renderCampaign(data.application_goal)" in script
