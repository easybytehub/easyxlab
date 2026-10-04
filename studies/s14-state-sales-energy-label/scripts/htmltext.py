"""Plain text from an HTML page (for grepping legal texts literally)."""
import re, html, sys, gzip
def text(path):
    b = open(path, "rb").read()
    if b[:2] == b"\x1f\x8b":
        b = gzip.decompress(b)
    s = b.decode("utf-8", "replace")
    s = re.sub(r"<(script|style)\b.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>|</p>|</h\d>|</li>|</div>|</tr>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\xa0]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n", s)
if __name__ == "__main__":
    sys.stdout.write(text(sys.argv[1]))
