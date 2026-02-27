import asyncio
from pathlib import Path

from picoagent.skills import ProjectMapSkill, ReadmeSkill, SkillContext, SkillRegistry


def test_skill_registry_picks_project_map(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    (tmp_path / "src").mkdir()

    registry = SkillRegistry(threshold=0.5)
    registry.register(ProjectMapSkill())
    registry.register(ReadmeSkill())

    context = SkillContext(workspace_root=tmp_path, memories=[])
    decision = registry.decide("show me the project structure", context)

    assert decision.should_run is True
    assert decision.skill_name == "project_map"


def test_readme_skill_output(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# title\n\nusage text", encoding="utf-8")

    registry = SkillRegistry(threshold=0.2)
    registry.register(ReadmeSkill())

    context = SkillContext(workspace_root=tmp_path, memories=[])
    decision = registry.decide("read the docs", context)
    assert decision.skill_name == "readme_lookup"

    result = asyncio.run(registry.run(decision.skill_name, "read the docs", context))
    assert "README excerpt" in result.output
