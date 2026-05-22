from pathlib import Path


def test_required_project_files_exist() -> None:
    required = [
        "README.md",
        "app/core.py",
        "app/main.py",
        "scripts/collect_once.py",
        "docs/architecture.md",
        ".github/workflows/ci.yml",
        ".github/workflows/collect.yml",
    ]
    missing = [path for path in required if not Path(path).exists()]
    assert missing == []


def test_readme_documents_safety_first_policy() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "Safety-first" in readme
    assert "Upwork" in readme
    assert "approved API access" in readme
