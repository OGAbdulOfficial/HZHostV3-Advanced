from datetime import datetime


NEON_LINE = "━━━━━━━━━━━━━━━━━━━━"


def neon_panel(title: str, lines: list[str], footer: str | None = None) -> str:
    parts = [f"🌈 **{title}**", NEON_LINE]
    parts.extend(lines)
    if footer:
        parts.extend(["", footer])
    return "\n".join(parts)


def neon_kv(label: str, value: str, icon: str = "✦") -> str:
    return f"{icon} **{label}:** `{value}`"


def neon_text(icon: str, text: str) -> str:
    return f"{icon} {text}"


def fmt_dt(value) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M UTC")
    return "N/A"
