#!/usr/bin/env python3
"""PreToolUse hook: deny full test-suite runs in the inner loop (docs/tests-boucle.md).

Fail open: a loop-cost guard, not a security boundary.
"""
import json
import re
import shlex
import sys

MESSAGE = (
    "Suite complète refusée dans la boucle interne. Lancer un test ciblé, par exemple "
    "`uv run pytest tests/<chemin> -n 0` ou `npx vitest run <fichier>`. Pour une vraie "
    "suite complète (fin de branche), préfixer la commande par `FULL_SUITE=1`. "
    "Voir docs/tests-boucle.md."
)
SEPARATORS = {"&&", "||", ";", "|", "&"}
WRAPPERS = {"rtk", "uv", "run", "npx", "python", "python3", "-m"}
PYTEST_TARGETING = {"-k", "--lf", "--last-failed", "--sw", "--stepwise"}
# Options whose next token is a value, not a positional argument.
VALUE_OPTIONS = {"-m", "-k", "-n", "-p", "-c", "-o", "--maxfail", "--tb", "--durations",
                 "--rootdir", "--ignore", "--deselect", "--junitxml", "--reporter"}
ASSIGNMENT = re.compile(r"^[A-Za-z_]\w*=")


def positionals(args):
    found, skip = [], False
    for arg in args:
        if skip:
            skip = False
        elif arg in VALUE_OPTIONS:
            skip = True
        elif not arg.startswith("-"):
            found.append(arg)
    return found


def pytest_is_full(args):
    if any(arg in PYTEST_TARGETING for arg in args):
        return False
    for flag, value in zip(args, args[1:]):
        if flag == "-m" and re.search(r"(?<!not )integration", value):
            return False
    return all(path in ("tests", "tests/") for path in positionals(args))


def vitest_is_full(args):
    if "related" in args or "--changed" in args:
        return False
    return not positionals([arg for arg in args if arg != "run"])


def segment_is_full_suite(tokens):
    while tokens and ASSIGNMENT.match(tokens[0]):
        if tokens[0] == "FULL_SUITE=1":
            return False
        tokens = tokens[1:]
    if tokens[:1] == ["npm"]:
        rest = tokens[1:]
        if rest[:1] == ["--prefix"]:
            rest = rest[2:]
        if rest[:2] == ["run", "test"]:
            rest = rest[1:]
        if rest[:1] != ["test"]:
            return False
        after_dashes = rest[rest.index("--") + 1:] if "--" in rest else []
        return vitest_is_full(after_dashes)
    while tokens and tokens[0] in WRAPPERS:
        tokens = tokens[1:]
    if tokens[:1] in (["pytest"], ["py.test"]):
        return pytest_is_full(tokens[1:])
    if tokens[:1] == ["vitest"]:
        return vitest_is_full(tokens[1:])
    return False


def is_full_suite(command):
    lexer = shlex.shlex(command.replace("\n", ";"), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    segment, segments = [], []
    for token in lexer:
        if token in SEPARATORS:
            segments.append(segment)
            segment = []
        else:
            segment.append(token)
    segments.append(segment)
    return any(segment_is_full_suite(segment) for segment in segments)


def main():
    try:
        command = json.load(sys.stdin)["tool_input"]["command"]
        denied = is_full_suite(command)
    except (ValueError, KeyError, TypeError):
        return
    if denied:
        json.dump({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": MESSAGE,
        }}, sys.stdout)


if __name__ == "__main__":
    main()
