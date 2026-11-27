from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ScriptEncodingTests(unittest.TestCase):
    def test_powershell_scripts_contain_only_ascii(self):
        # Windows PowerShell 5.1 reads a BOM-less .ps1 file using the system
        # ANSI code page. Non-ASCII bytes then get mangled into characters that
        # the parser treats as string delimiters (for example U+201C for "✓"),
        # so the whole script fails to parse before it runs. Keeping these files
        # ASCII-only makes them independent of the host locale and encoding.
        offenders = []
        for path in sorted(ROOT.rglob("*.ps1")):
            relative = path.relative_to(ROOT)
            if any(part.startswith(".") for part in relative.parts):
                continue
            for number, line in enumerate(path.read_bytes().splitlines(), start=1):
                if any(byte > 0x7F for byte in line):
                    offenders.append(f"{relative}:{number}")
        self.assertEqual(
            offenders,
            [],
            "PowerShell scripts must stay ASCII-only: " + ", ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
