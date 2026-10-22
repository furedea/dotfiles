"""Inspect literal text and pipeline structure for supplementary command policy."""

import shell_syntax


def text_outside_single_quotes(source: str) -> str:
    """The source without its single-quoted strings, which no shell expands; $'...' stays, as it decodes escapes."""
    data = source.encode()
    spans = sorted(
        (node["Pos"]["Offset"], node["End"]["Offset"])
        for node in shell_syntax.nodes(shell_syntax.syntax_tree(source))
        if node.get("Type") == "SglQuoted" and not node.get("Dollar")
    )
    kept, start = [], 0
    for begin, end in spans:
        kept.append(data[start:begin])
        start = max(start, end)
    kept.append(data[start:])
    return b"".join(kept).decode()


def is_plain_pipeline(source: str) -> bool:
    """Accept only a single foreground pipeline of unwrapped simple calls."""
    statements = shell_syntax.syntax_tree(source).get("Stmts", [])
    if len(statements) != 1:
        return False
    return plain_pipeline_statement(statements[0], source.encode())


def plain_pipeline_statement(statement: dict, data: bytes) -> bool:
    flags = ("Background", "Coprocess", "Negated", "Disown", "Redirs")
    if any(statement.get(flag) for flag in flags):
        return False
    command = statement.get("Cmd", {})
    if command.get("Type") == "CallExpr":
        return not command.get("Assigns")
    if command.get("Type") != "BinaryCmd":
        return False
    offset = command["OpPos"]["Offset"]
    if data[offset : offset + 1] != b"|" or data[offset + 1 : offset + 2] in {b"|", b"&"}:
        return False
    return all(plain_pipeline_statement(command[side], data) for side in ("X", "Y"))
