from __future__ import annotations

import asyncio
import re
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from picoagent.agent.context import ContextBuilder
from picoagent.agent.subagents import SubagentCoordinator
from picoagent.agent.tools.registry import ToolContext, ToolRegistry, validate_params
from picoagent.core.adaptive import AdaptiveThreshold
from picoagent.core.dual_memory import DualMemoryStore
from picoagent.core.memory import VectorMemory
from picoagent.core.scheduler import EntropyScheduler, ToolDecision
from picoagent.providers.registry import LocalHeuristicClient, ProviderClient, ProviderError
from picoagent.session import SessionManager, SessionState
from picoagent.skills import MarkdownSkillLibrary
from picoagent import hooks


@dataclass(slots=True)
class AgentTurnResult:
    text: str
    selected_tool: str | None
    tool_args: dict
    tool_output: str
    decision: ToolDecision
    active_skills: list[str] = field(default_factory=list)
    subagent_note: str | None = None


class AgentLoop:
    def __init__(
        self,
        *,
        config: AgentConfig,
        provider: ProviderClient,
        memory: VectorMemory,
        scheduler: EntropyScheduler,
        tools: ToolRegistry,
        context_builder: ContextBuilder | None = None,
        skill_library: MarkdownSkillLibrary | None = None,
        subagent_coordinator: SubagentCoordinator | None = None,
        adaptive_threshold: AdaptiveThreshold | None = None,
        session_manager: SessionManager | None = None,
        dual_memory: DualMemoryStore | None = None,
    ) -> None:
        self.config = config
        self.provider = provider
        self.memory = memory
        self.scheduler = scheduler
        self.tools = tools
        self.context_builder = context_builder or ContextBuilder()
        self.skill_library = skill_library
        self.subagent_coordinator = subagent_coordinator
        self.adaptive_threshold = adaptive_threshold
        self.session_manager = session_manager
        self.dual_memory = dual_memory

    def load_memory(self) -> int:
        try:
            return self.memory.load()
        except ValueError:
            return 0

    def save_memory(self) -> None:
        try:
            self.memory.save()
        except ValueError:
            pass

    async def run_turn(self, user_message: str, *, session_id: str | None = None) -> AgentTurnResult:
        await hooks.fire("on_turn_start", message=user_message, session_id=session_id)
        tool_docs = self.tools.docs()
        session = self._get_session(session_id)
        if session is not None:
            session.add_message("user", user_message)
            self.session_manager.save_session(session)

        active_skill_names: list[str] = []

        try:
            try:
                query_embedding = self.provider.embed(user_message)
                memories = self.memory.recall(query_embedding, k=self.config.memory_top_k)
            except ProviderError:
                # Provider doesn't support embeddings (e.g. Groq) — skip memory recall
                memories = []

            history = session.get_history(max_messages=12) if session is not None else []

            selected_skills: list[dict[str, str]] = []
            skills_summary = ""
            if self.skill_library is not None and self.config.enable_skills:
                skills_summary = self.skill_library.summary()
                picked = self.skill_library.select_for_message(user_message, max_skills=self.config.max_active_skills)
                active_skill_names = [s.name for s in picked]
                selected_skills = [
                    {
                        "name": s.name,
                        "path": str(s.path),
                        "content": s.content,
                    }
                    for s in picked
                ]

            context_messages = self.context_builder.build_messages(
                user_message=user_message,
                memories=memories,
                history=history,
                skills_summary=skills_summary,
                active_skills=selected_skills,
            )
            routing_message = "\n\n".join(m["content"] for m in context_messages)
        except ProviderError as exc:
            decision = ToolDecision(tool_name=None, entropy_bits=0.0, probabilities={}, should_clarify=True)
            text = f"Provider error while preparing turn: {exc}"
            self._finalize_session_turn(session, text)
            await hooks.fire("on_turn_end", response=text, session_id=session_id)
            return AgentTurnResult(
                text=text,
                selected_tool=None,
                tool_args={},
                tool_output="",
                decision=decision,
                active_skills=active_skill_names,
            )

        heuristic = LocalHeuristicClient()
        if self._should_reply_directly(user_message):
            text = self._direct_chat_reply(user_message, memories=memories, history=history)
            self._finalize_session_turn(session, text)
            await hooks.fire("on_turn_end", response=text, session_id=session_id)
            return AgentTurnResult(
                text=text,
                selected_tool=None,
                tool_args={},
                tool_output="",
                decision=ToolDecision(tool_name=None, entropy_bits=0.0, probabilities={}, should_clarify=False),
                active_skills=active_skill_names,
            )

        try:
            scores = self.provider.score_tools(routing_message, tool_docs)
        except ProviderError:
            # If external provider routing fails (e.g., HTTP 403), keep the turn alive with offline heuristics.
            scores = heuristic.score_tools(routing_message, tool_docs)

        threshold_bits = self.config.entropy_threshold_bits
        if self.adaptive_threshold is not None and self.config.adaptive_threshold_enabled:
            threshold_bits = self.adaptive_threshold.current()

        decision = self.scheduler.decide(scores, threshold_bits=threshold_bits)
        if decision.should_clarify or decision.tool_name is None:
            top_tools = sorted(decision.probabilities.items(), key=lambda kv: kv[1], reverse=True)[:2]
            suggestions = ", ".join(f"{name} ({p:.2f})" for name, p in top_tools) if top_tools else "none"
            text = (
                "I am not confident enough to choose a tool. "
                f"Top candidates: {suggestions}. "
                f"(entropy={decision.entropy_bits:.2f}, threshold={threshold_bits:.2f}) "
                "Please clarify what action you want."
            )
            self._finalize_session_turn(session, text)
            await hooks.fire("on_turn_end", response=text, session_id=session_id)
            return AgentTurnResult(
                text=text,
                selected_tool=None,
                tool_args={},
                tool_output="",
                decision=decision,
                active_skills=active_skill_names,
            )

        tool_name = decision.tool_name
        tool_doc = tool_docs.get(tool_name, "")

        try:
            # Argument planning should focus on the user's request, not the expanded routing context.
            tool_args = self.provider.plan_tool_args(user_message, tool_name, tool_doc)
        except ProviderError:
            tool_args = heuristic.plan_tool_args(user_message, tool_name, tool_doc)

        if not isinstance(tool_args, dict):
            tool_args = {}

        # Repair invalid planned args before running tool validation path.
        try:
            tool_schema = getattr(self.tools.get(tool_name), "parameters", None)
        except KeyError:
            tool_schema = None
        if isinstance(tool_schema, dict):
            validation_errors = validate_params(tool_args, tool_schema)
            if validation_errors:
                fallback_args = heuristic.plan_tool_args(user_message, tool_name, tool_doc)
                if isinstance(fallback_args, dict):
                    # Validate fallback args through schema before accepting them
                    fallback_errors = validate_params(fallback_args, tool_schema)
                    if fallback_errors:
                        import logging as _logging
                        _logging.getLogger(__name__).warning(
                            "Heuristic fallback args for tool '%s' failed schema validation: %s",
                            tool_name,
                            "; ".join(fallback_errors),
                        )
                        # For non-shell tools, skip execution; for shell, let the repair logic below handle it
                        if tool_name != "shell":
                            text = self._direct_chat_reply(user_message, memories=memories, history=history)
                            self._finalize_session_turn(session, text)
                            await hooks.fire("on_turn_end", response=text, session_id=session_id)
                            return AgentTurnResult(
                                text=text,
                                selected_tool=None,
                                tool_args={},
                                tool_output="",
                                decision=decision,
                                active_skills=active_skill_names,
                            )
                    else:
                        tool_args = fallback_args
                if tool_name == "shell":
                    command = str(tool_args.get("command", "")).strip() if isinstance(tool_args, dict) else ""
                    if not command and self._looks_like_shell_command(user_message):
                        tool_args = {"command": user_message.strip()}

        if tool_name == "shell":
            command = str(tool_args.get("command", "")).strip() if isinstance(tool_args, dict) else ""
            if not command or not self._looks_like_shell_command(command):
                text = self._direct_chat_reply(user_message, memories=memories, history=history)
                self._finalize_session_turn(session, text)
                await hooks.fire("on_turn_end", response=text, session_id=session_id)
                return AgentTurnResult(
                    text=text,
                    selected_tool=None,
                    tool_args={},
                    tool_output="",
                    decision=decision,
                    active_skills=active_skill_names,
                )
            tool_args = {"command": command, **{k: v for k, v in tool_args.items() if k != "command"}}

        context = ToolContext(workspace_root=Path(self.config.workspace_root), session_id=session_id)
        result_success = False
        max_tool_chain = 3
        chain_depth = 0

        try:
            result = await asyncio.wait_for(
                self.tools.run(tool_name, tool_args, context),
                timeout=self.config.tool_timeout_seconds,
            )
            tool_output = result.output
            result_success = result.success
        except asyncio.TimeoutError:
            from picoagent.agent.tools.registry import ToolResult
            result = ToolResult(
                output=f"Tool timed out after {self.config.tool_timeout_seconds}s",
                success=False,
            )
            tool_output = result.output
            result_success = False
        except Exception:  # noqa: BLE001
            tool_output = traceback.format_exc()

        # Multi-turn tool chain: if tool succeeded, re-score with tool result appended
        while result_success and chain_depth < max_tool_chain:
            chain_depth += 1
            chained_routing = routing_message + f"\n\nTool result: {tool_output}"
            try:
                chain_scores = self.provider.score_tools(chained_routing, tool_docs)
            except ProviderError:
                break
            chain_decision = self.scheduler.decide(chain_scores, threshold_bits=threshold_bits)
            if (
                chain_decision.tool_name is None
                or chain_decision.should_clarify
                or chain_decision.entropy_bits >= threshold_bits
            ):
                break
            # Check if top tool score is above 0.7
            top_chain_score = float(chain_decision.probabilities.get(chain_decision.tool_name, 0.0))
            if top_chain_score <= 0.7:
                break
            # Execute the chained tool
            chained_tool_name = chain_decision.tool_name
            chained_tool_doc = tool_docs.get(chained_tool_name, "")
            try:
                chained_args = self.provider.plan_tool_args(user_message, chained_tool_name, chained_tool_doc)
            except ProviderError:
                chained_args = heuristic.plan_tool_args(user_message, chained_tool_name, chained_tool_doc)
            if not isinstance(chained_args, dict):
                chained_args = {}
            # Validate chained args before executing; break chain if invalid
            try:
                chained_schema = getattr(self.tools.get(chained_tool_name), "parameters", None)
            except KeyError:
                chained_schema = None
            if isinstance(chained_schema, dict):
                chained_errors = validate_params(chained_args, chained_schema)
                if chained_errors:
                    break
            try:
                chained_result = await asyncio.wait_for(
                    self.tools.run(chained_tool_name, chained_args, context),
                    timeout=self.config.tool_timeout_seconds,
                )
                tool_output = chained_result.output
                result_success = chained_result.success
                tool_name = chained_tool_name
                tool_args = chained_args
                decision = chain_decision
            except (asyncio.TimeoutError, Exception):
                break

        await hooks.fire("on_tool_result", tool_name=tool_name, result=result, session_id=session_id)
        await self._remember_turn(user_message, tool_output, memory_type="tool", tag=tool_name)

        if self.adaptive_threshold is not None and self.config.adaptive_threshold_enabled:
            top_confidence = float(decision.probabilities.get(tool_name, 0.0))
            self.adaptive_threshold.observe(success=result_success, top_confidence=top_confidence)

        try:
            text = self.provider.synthesize_response(user_message, tool_name, tool_output, memories)
        except ProviderError:
            text = f"Tool `{tool_name}` result:\n{tool_output}"

        subagent_note: str | None = None
        if self.subagent_coordinator is not None and self.config.enable_subagents:
            subagent_result = await self.subagent_coordinator.maybe_spawn(user_message, decision, tool_output)
            if subagent_result.spawned and subagent_result.note:
                subagent_note = subagent_result.note
                text = f"{text}\n\nSubagent review:\n{subagent_note}"

        self._finalize_session_turn(session, text)
        await hooks.fire("on_turn_end", response=text, session_id=session_id)
        return AgentTurnResult(
            text=text,
            selected_tool=tool_name,
            tool_args=tool_args,
            tool_output=tool_output,
            decision=decision,
            active_skills=active_skill_names,
            subagent_note=subagent_note,
        )

    def _get_session(self, session_id: str | None) -> SessionState | None:
        if self.session_manager is None:
            return None
        key = session_id or "default"
        return self.session_manager.get_or_create(key)

    def _finalize_session_turn(self, session: SessionState | None, assistant_text: str) -> None:
        if session is None:
            return
        session.add_message("assistant", assistant_text)
        self._maybe_consolidate_session(session)
        self.session_manager.save_session(session)

    def _maybe_consolidate_session(self, session: SessionState) -> None:
        if not self.config.session_consolidation_enabled:
            return
        total = len(session.messages)
        if total <= self.config.session_memory_window:
            return

        cut_index = total - self.config.session_keep_recent
        if cut_index <= session.last_consolidated:
            return

        old_messages = session.messages[session.last_consolidated:cut_index]
        if not old_messages:
            return

        summary = self._summarize_messages_for_memory(session.key, old_messages)
        try:
            embedding = self.provider.embed(summary)
            self.memory.store(
                summary[:1000],
                embedding,
                metadata={"type": "session_summary", "session": session.key, "count": len(old_messages)},
            )
            self.save_memory()
        except (ProviderError, ValueError):
            pass

        if getattr(self, "dual_memory", None):
            import asyncio
            from loguru import logger
            logger.info("Scheduling dual-memory consolidation task for session {}", session.key)
            asyncio.create_task(
                self.dual_memory.consolidate(
                    session=session,
                    provider=self.provider,
                    model=self.provider.get_default_model(),
                )
            )

        session.last_consolidated = cut_index

    @staticmethod
    def _summarize_messages_for_memory(session_key: str, messages: list) -> str:
        lines = []
        for item in messages[-20:]:
            content = item.content.strip().replace("\n", " ")
            if content:
                lines.append(f"[{item.role}] {content[:220]}")

        joined = "\n".join(lines) if lines else "(no content)"
        return f"Session {session_key} summary ({len(messages)} messages):\n{joined}"

    @staticmethod
    def _looks_like_shell_command(text: str) -> bool:
        raw = (text or "").strip()
        if not raw:
            return False

        lowered = raw.lower()
        if any(
            lowered.startswith(prefix)
            for prefix in ("run ", "execute ", "shell ", "terminal ", "cmd ", "command ", "bash ", "zsh ", "sh ")
        ):
            return True

        if any(marker in raw for marker in ("&&", "||", "|", ";", "$(", "`", ">", "<", "\n")):
            return True

        first = lowered.split()[0]
        if first.startswith(("./", "/", "~/")) or first.endswith(".sh"):
            return True

        common = {
            "ls",
            "pwd",
            "cd",
            "cat",
            "grep",
            "find",
            "rg",
            "sed",
            "awk",
            "head",
            "tail",
            "wc",
            "git",
            "python",
            "python3",
            "pip",
            "pip3",
            "npm",
            "pnpm",
            "yarn",
            "node",
            "make",
            "pytest",
            "uv",
            "docker",
            "kubectl",
            "curl",
            "wget",
            "echo",
            "mkdir",
            "touch",
            "cp",
            "mv",
            "rm",
            "chmod",
            "chown",
            "ps",
            "kill",
            "whoami",
            "uname",
            "date",
        }
        if first in common:
            return True

        if re.fullmatch(r"[a-z0-9._/\-]+", first) is None:
            return False
        return len(raw.split()) > 1

    @staticmethod
    def _should_reply_directly(text: str) -> bool:
        raw = (text or "").strip()
        if not raw:
            return False

        lowered = raw.lower()
        greetings = {
            "hi",
            "hello",
            "hey",
            "yo",
            "sup",
            "thanks",
            "thank you",
            "good morning",
            "good afternoon",
            "good evening",
        }
        if lowered in greetings:
            return True
        if lowered.startswith(("hi ", "hello ", "hey ", "thanks ", "thank you ")):
            return True

        if AgentLoop._looks_like_shell_command(raw):
            return False

        tokens = re.findall(r"[a-z0-9_]+", lowered)
        if not tokens:
            return False

        tool_intent = {
            "run",
            "execute",
            "shell",
            "terminal",
            "command",
            "read",
            "write",
            "edit",
            "file",
            "folder",
            "path",
            "search",
            "lookup",
            "google",
            "web",
            "http",
            "https",
            "git",
            "python",
            "npm",
            "pip",
            "test",
            "build",
            "deploy",
            "debug",
            "fix",
        }
        if any(t in tool_intent for t in tokens):
            return False

        path_hints = ("/", "\\", ".py", ".md", ".json", ".yaml", ".yml", ".txt")
        if any(h in lowered for h in path_hints):
            return False

        return len(tokens) <= 3

    def _direct_chat_reply(self, user_message: str, *, memories: list[str], history: list[dict[str, str]]) -> str:
        history_lines = [f"[{m.get('role', 'user')}] {m.get('content', '')}" for m in history[-6:]]
        history_block = "\n".join(history_lines) if history_lines else "(none)"
        memory_block = "\n".join(f"- {m}" for m in memories[:5]) if memories else "- (none)"
        prompt = (
            f"Recent conversation:\n{history_block}\n\n"
            f"Relevant memories:\n{memory_block}\n\n"
            f"User message:\n{user_message}"
        )
        base_sys = self.context_builder.build_system_prompt([])
        system = f"{base_sys}\n\nReply directly and conversationally when the user is chatting. Do not suggest shell commands unless explicitly asked."
        try:
            return self.provider.chat(prompt, system_prompt=system)
        except ProviderError as e:
            return f"Provider error: {e}"

    async def _remember_turn(self, user_message: str, output: str, *, memory_type: str, tag: str) -> None:
        try:
            user_embedding = self.provider.embed(user_message)
            self.memory.store(user_message, user_embedding, metadata={"type": "user"})

            output_embedding = self.provider.embed(output)
            self.memory.store(
                f"{tag}: {output[:500]}",
                output_embedding,
                metadata={"type": memory_type, "tag": tag},
            )
            self.save_memory()
        except (ProviderError, ValueError):
            return
