from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable

if TYPE_CHECKING:
    from picoagent.agent.loop import AgentTurnResult


class CLIChannel:
    name = "cli"

    async def start(self, handler: Callable[[str], Awaitable["AgentTurnResult"]]) -> None:
        print("picoagent CLI started. Type 'exit' to quit.")
        while True:
            try:
                user = input("you> ").strip()
            except EOFError:
                print()
                break
            if not user:
                continue
            if user.lower() in {"exit", "quit"}:
                break
                
            turn = await handler(user)
            print(f"agent> {turn.text}")
            
            # Render entropy bar if a tool decision was made and entropy is meaningful
            if turn.decision.tool_name is not None and not turn.decision.should_clarify and turn.decision.entropy_bits > 0:
                self._draw_entropy_bar(turn.decision.entropy_bits, turn.threshold_bits)

    def _draw_entropy_bar(self, entropy: float, threshold: float) -> None:
        # e.g. [entropy: ██░░░ 1.2 bits / threshold: 1.5]
        bar_length = 10
        # If threshold is very small, protect against div by zero
        max_val = max(threshold * 1.5, 0.1) 
        ratio = min(entropy / max_val, 1.0)
        filled = int(round(ratio * bar_length))
        empty = bar_length - filled
        
        # Use simple ASCII blocks
        bar = ("█" * filled) + ("░" * empty)
        
        # Color coding (green if confident/safe, yellow if getting close, red if over)
        # Using standard ANSI escapes (light colors)
        color = "\033[92m" # Green (safe, low entropy)
        if entropy > threshold:
            color = "\033[91m" # Red (unsafe)
        elif entropy > threshold * 0.7:
            color = "\033[93m" # Yellow (warning)
        reset = "\033[0m"
        
        print(f"  {color}[entropy: {bar} {entropy:.2f} bits / threshold: {threshold:.2f}]{reset}")
