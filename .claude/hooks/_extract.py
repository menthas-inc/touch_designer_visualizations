"""Read a Claude Code tool-call payload on stdin and print the fields a hook cares about.

Usage: _extract.py path   -> the target file path, or an empty line
       _extract.py content -> every text field that may carry file content, decoded

Kept separate because grep cannot parse a JSON string that contains an escaped quote,
which is most source files.
"""
import json
import sys

FIELDS = ("content", "new_string", "new_str", "old_string")


def walk(node, out):
    if isinstance(node, dict):
        for key, value in node.items():
            if key in FIELDS and isinstance(value, str):
                out.append(value)
            else:
                walk(value, out)
    elif isinstance(node, list):
        for value in node:
            walk(value, out)


def main():
    want = sys.argv[1] if len(sys.argv) > 1 else "content"
    if want == "command":
        found = []

        def find_cmd(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key == "command" and isinstance(value, str):
                        found.append(value)
                    else:
                        find_cmd(value)
            elif isinstance(node, list):
                for value in node:
                    find_cmd(value)

        try:
            payload = json.load(sys.stdin)
        except Exception:
            return 0
        find_cmd(payload)
        print(found[0] if found else "")
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if want == "path":
        found = []

        def find_path(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key == "file_path" and isinstance(value, str):
                        found.append(value)
                    else:
                        find_path(value)
            elif isinstance(node, list):
                for value in node:
                    find_path(value)

        find_path(payload)
        print(found[0] if found else "")
        return 0
    out = []
    walk(payload, out)
    sys.stdout.write("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
