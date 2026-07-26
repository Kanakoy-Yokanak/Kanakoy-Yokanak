from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
AVATAR = ROOT / "assets" / "ascii-avatar.svg.svg"
TARGETS = [ROOT / "assets" / "dark.svg", ROOT / "assets" / "light.svg"]

avatar = AVATAR.read_text(encoding="utf-8")
start = avatar.find(">")
end = avatar.rfind("</svg>")
if start == -1 or end == -1:
    raise SystemExit("Invalid avatar SVG")
inner = avatar[start + 1:end]

pattern = re.compile(
    r'<image\\b[^>]*href="ascii-avatar\\.svg\\.svg"[^>]*>.*?</image>',
    re.DOTALL,
)

replacement = f'''<g opacity="0.98">
        <animate attributeName="opacity" values="0.35;1;1;0.35" keyTimes="0;0.2;0.92;1" dur="10s" repeatCount="indefinite"/>
        <svg x="785" y="154" width="320" height="300" viewBox="0 0 2152 2014" preserveAspectRatio="xMidYMid meet">
          {inner}
        </svg>
      </g>'''

changed = 0
for target in TARGETS:
    text = target.read_text(encoding="utf-8")
    new_text, count = pattern.subn(replacement, text, count=1)
    if count:
        target.write_text(new_text, encoding="utf-8")
        print(f"Inlined avatar into {target.relative_to(ROOT)}")
        changed += 1
    elif "ascii-avatar.svg.svg" in text:
        raise SystemExit(f"Avatar reference found in unexpected format: {target}")
    else:
        print(f"No external avatar reference in {target.relative_to(ROOT)}; already inlined or not present")

if not changed:
    print("Nothing to change")
