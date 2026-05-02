from pathlib import Path


def check_disclosure() -> None:
    prompt_path = Path(__file__).parent / "prompts" / "agent_system.md"
    content = prompt_path.read_text()
    if "AI" not in content:
        raise RuntimeError("agent_system.md must contain 'AI' disclosure")
    if "disclose" not in content:
        raise RuntimeError("agent_system.md must contain 'disclose' keyword")


if __name__ == "__main__":
    check_disclosure()
    print("Disclosure check passed.")
