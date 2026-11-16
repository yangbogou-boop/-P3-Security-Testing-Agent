"""Check local inline Markdown links in the maintained navigation, without network I/O."""
import argparse
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
NAVIGATION = ("README.md", "AGENTS.md", "docs/INDEX.md")
INLINE_LINK = re.compile(r"\[[^\]\n]*\]\(\s*(?:<([^>\n]+)>|([^\s)]+))")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
HEADING = re.compile(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$")


def prose_lines(document):
    fence = None
    for number, line in enumerate(document.read_text(encoding="utf-8-sig").splitlines(), 1):
        marker = FENCE.match(line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence) and not line[marker.end():].strip():
                fence = None
        elif fence is None:
            yield number, line


def heading_ids(document):
    anchors = set()
    for _, line in prose_lines(document):
        heading = HEADING.match(line)
        if heading:
            slug = re.sub(r"[^\w -]", "", heading[1].lower()).replace(" ", "-")
            anchor = slug
            suffix = 1
            while anchor in anchors:
                anchor = f"{slug}-{suffix}"
                suffix += 1
            anchors.add(anchor)
    return anchors


def check_links(root, documents):
    """Return local links checked, their inbound references, and missing targets."""
    count = 0
    inbound = {}
    failures = []
    for document in documents:
        origin = root / document
        for number, line in prose_lines(origin):
            for match in INLINE_LINK.finditer(line):
                link = match[1] or match[2]
                parsed = urlsplit(link)
                if parsed.scheme or parsed.netloc:
                    continue
                count += 1
                path = unquote(parsed.path)
                destination = (origin.parent / path).resolve() if path else origin.resolve()
                try:
                    relative = destination.relative_to(root).as_posix()
                except ValueError:
                    failures.append((document, number, link, "outside repository"))
                    continue
                inbound.setdefault(relative, set()).add(f"{document}:{number}")
                if not destination.exists():
                    failures.append((document, number, link, "missing target"))
                elif parsed.fragment and destination.suffix.lower() == ".md":
                    if unquote(parsed.fragment) not in heading_ids(destination):
                        failures.append((document, number, link, "missing heading"))
    return count, inbound, failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="also inspect historical Markdown")
    options = parser.parse_args()
    documents = NAVIGATION
    if options.all:
        documents = sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.md")
                           if ".git" not in p.relative_to(ROOT).parts)
    count, _, failures = check_links(ROOT, documents)
    for document, number, link, reason in failures:
        print(f"{document}:{number}: {link} ({reason})")
    print(f"Checked {count} local links in {len(documents)} documents. Issues: {len(failures)}.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
