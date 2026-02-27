from pathlib import Path

from picoagent.skills import MarkdownSkillLibrary


def test_markdown_skill_library_lists_skills(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "alpha"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# alpha\n\nDo alpha work.", encoding="utf-8")

    lib = MarkdownSkillLibrary(tmp_path / "skills")
    skills = lib.list_skills()

    assert len(skills) == 1
    assert skills[0].name == "alpha"


def test_markdown_skill_selects_by_explicit_name(tmp_path: Path) -> None:
    skill_a = tmp_path / "skills" / "git-flow"
    skill_a.mkdir(parents=True)
    (skill_a / "SKILL.md").write_text("# git-flow\n\nUse when handling git workflow.", encoding="utf-8")

    lib = MarkdownSkillLibrary(tmp_path / "skills")
    selected = lib.select_for_message("please use $git-flow now")

    assert [s.name for s in selected] == ["git-flow"]
