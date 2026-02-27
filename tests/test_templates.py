import json
from pathlib import Path

from picoagent.templates import TemplateLoader


def test_template_loader_prefers_workspace(tmp_path: Path) -> None:
    # Setup workspace
    workspace_templates = tmp_path / "templates"
    workspace_templates.mkdir(parents=True)
    (workspace_templates / "SOUL.md").write_text("Workspace Soul", encoding="utf-8")

    # The builtin logic depends on __file__ in templates.py, which is hard to mock cleanly
    # without patching. But we can test the workspace loading works perfectly.
    loader = TemplateLoader(workspace_root=tmp_path)
    content = loader.load_template("SOUL.md")
    
    assert content == "Workspace Soul"


def test_template_loader_strips_frontmatter(tmp_path: Path) -> None:
    workspace_templates = tmp_path / "templates"
    workspace_templates.mkdir(parents=True)
    
    markdown_with_frontmatter = (
        "---\n"
        "name: test\n"
        "---\n\n"
        "# Real content\n"
        "Here is the text."
    )
    (workspace_templates / "USER.md").write_text(markdown_with_frontmatter, encoding="utf-8")

    loader = TemplateLoader(workspace_root=tmp_path)
    content = loader.load_template("USER.md")
    
    assert content == "# Real content\nHere is the text."


def test_template_loader_builds_combined_prompt(tmp_path: Path) -> None:
    workspace_templates = tmp_path / "templates"
    workspace_templates.mkdir(parents=True)
    
    (workspace_templates / "SOUL.md").write_text("I am Soul.", encoding="utf-8")
    (workspace_templates / "USER.md").write_text("I am User.", encoding="utf-8")
    (workspace_templates / "AGENTS.md").write_text("I am Agent.", encoding="utf-8")

    loader = TemplateLoader(workspace_root=tmp_path)
    prompt = loader.build_system_prompt()
    
    assert prompt == "I am Soul.\n\n---\n\nI am User.\n\n---\n\nI am Agent."


def test_template_loader_handles_missing_templates(tmp_path: Path) -> None:
    loader = TemplateLoader(workspace_root=tmp_path)
    
    # We are using an empty tmp_path, so there are no workspace templates.
    # We also pass a garbage name so the builtin fallback fails too.
    content = loader.load_template("DOES_NOT_EXIST.md")
    assert content is None
