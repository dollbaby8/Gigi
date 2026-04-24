#!/usr/bin/env python3
"""Drafting aid for a Fifth Circuit petition for writ of mandamus.

Assembles a structured draft from a configuration file so counsel can focus on
legal analysis rather than boilerplate. This is not legal advice and not a
substitute for legal review. Every section must be reviewed and revised before
filing.

Authority consulted when building the template:
  - Fed. R. App. P. 21   writs of mandamus and prohibition; contents; length
  - Fed. R. App. P. 32   form of briefs and other papers; word limits
  - 5th Cir. R. 21       local mandamus rule
  - 5th Cir. R. 28.2.1   certificate of interested persons
  - 5th Cir. R. 32       local form requirements
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-not-found]

    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# FRAP 21(d): a petition, answer, or reply must not exceed 7,800 words.
WORD_LIMIT = 7800


REQUIRED_TOP_LEVEL = [
    "case",
    "counsel",
    "interested_persons",
    "issues",
    "facts",
    "jurisdiction",
    "argument",
    "relief",
]


def load_config(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        if not HAS_YAML:
            raise SystemExit(
                "PyYAML is required to read YAML config files. "
                "Install it with: pip install pyyaml"
            )
        data = yaml.safe_load(text)
    elif suffix == ".json":
        data = json.loads(text)
    else:
        # Try YAML if available, fall back to JSON.
        if HAS_YAML:
            data = yaml.safe_load(text)
        else:
            data = json.loads(text)
    if not isinstance(data, dict):
        raise SystemExit(f"Config must be a mapping at the top level (got {type(data).__name__}).")
    return data


def validate(config: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for key in REQUIRED_TOP_LEVEL:
        if key not in config:
            problems.append(f"missing required key: {key}")

    case = config.get("case") or {}
    for key in ("petitioner", "respondent", "district_court", "district_case_no"):
        if not case.get(key):
            problems.append(f"case.{key} is required")

    counsel = config.get("counsel") or {}
    for key in ("name", "address", "phone", "email"):
        if not counsel.get(key):
            problems.append(f"counsel.{key} is required")

    argument = config.get("argument") or {}
    for key in ("no_other_adequate_means", "clear_and_indisputable_right", "appropriateness"):
        if not argument.get(key):
            problems.append(f"argument.{key} is required (Cheney prong)")

    issues = config.get("issues")
    if not issues or not isinstance(issues, list):
        problems.append("issues must be a non-empty list")

    facts = config.get("facts")
    if not facts or not isinstance(facts, list):
        problems.append("facts must be a non-empty list of statements")

    return problems


# Rendering helpers ---------------------------------------------------------


def _hr() -> str:
    return "=" * 72


def _center(text: str, width: int = 72) -> str:
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            lines.append("")
        else:
            pad = max(0, (width - len(line)) // 2)
            lines.append(" " * pad + line)
    return "\n".join(lines)


def _section(title: str) -> str:
    return f"\n\n{title.upper()}\n{'-' * len(title)}\n"


def _numbered(items: list[str]) -> str:
    out = []
    for i, item in enumerate(items, 1):
        out.append(f"{i}. {item}".rstrip())
    return "\n\n".join(out)


def _bulleted(items: list[str]) -> str:
    return "\n".join(f"    - {item}" for item in items)


def count_words(text: str) -> int:
    # FRAP 32(f) excludes cover, tables, and certificates from the count.
    # This is a whole-document tally for a quick sanity check only; counsel
    # must compute the official count per FRAP 32(f) before filing.
    return len(re.findall(r"\b\w+\b", text))


# Renderer ------------------------------------------------------------------


def render(config: dict[str, Any]) -> str:
    case = config["case"]
    counsel = config["counsel"]
    oral = config.get("oral_argument") or {}
    interested = config["interested_persons"]
    issues = config["issues"]
    facts = config["facts"]
    jurisdiction = config["jurisdiction"]
    argument = config["argument"]
    relief = config["relief"]
    case_no = config.get("appeal_case_no") or "__________"

    petitioner = case["petitioner"]
    respondent = case["respondent"]
    real_party = case.get("real_party_in_interest")

    parts: list[str] = []

    # --- Cover page (5th Cir. R. 32.1) ------------------------------------
    parts.append(_hr())
    parts.append(
        _center(
            "\n".join(
                [
                    f"No. {case_no}",
                    "",
                    "IN THE UNITED STATES COURT OF APPEALS",
                    "FOR THE FIFTH CIRCUIT",
                    "",
                    "_____________________________",
                    "",
                    f"In re {petitioner},",
                    "",
                    "Petitioner.",
                    "_____________________________",
                    "",
                    "On Petition for Writ of Mandamus to the",
                    f"{case['district_court']}",
                    f"No. {case['district_case_no']}",
                    f"(Hon. {case.get('district_judge', respondent)})",
                    "_____________________________",
                    "",
                    "PETITION FOR WRIT OF MANDAMUS",
                    "_____________________________",
                    "",
                    counsel["name"],
                    counsel.get("firm", ""),
                    counsel["address"],
                    f"Tel: {counsel['phone']}",
                    f"Email: {counsel['email']}",
                    "",
                    "Counsel for Petitioner",
                ]
            )
        )
    )
    parts.append("\n" + _hr())

    # --- Certificate of Interested Persons (5th Cir. R. 28.2.1) -----------
    parts.append(_section("Certificate of Interested Persons"))
    parts.append(
        f"No. {case_no}, In re {petitioner}\n\n"
        "The undersigned counsel of record certifies that the following "
        "listed persons and entities as described in the fourth sentence of "
        "Fifth Circuit Rule 28.2.1 have an interest in the outcome of this "
        "case. These representations are made in order that the judges of "
        "this court may evaluate possible disqualification or recusal.\n"
    )
    parts.append(_bulleted(interested))
    parts.append(
        f"\n\nRespectfully submitted,\n\n    /s/ {counsel['name']}\n"
        f"    {counsel['name']}\n    Counsel for Petitioner"
    )

    # --- Statement Regarding Oral Argument --------------------------------
    parts.append(_section("Statement Regarding Oral Argument"))
    if oral.get("requested"):
        parts.append(
            "Petitioner respectfully requests oral argument. "
            + (oral.get("reason") or "").strip()
        )
    else:
        parts.append(
            "Petitioner does not believe oral argument is necessary. "
            + (oral.get("reason") or "").strip()
        )

    # --- Tables (placeholders) --------------------------------------------
    parts.append(_section("Table of Contents"))
    parts.append("    [Generate from final document before filing.]")
    parts.append(_section("Table of Authorities"))
    parts.append("    [Generate from final document before filing.]")

    # --- Relief Sought (FRAP 21(a)(2)(A)) ---------------------------------
    parts.append(_section("Relief Sought"))
    parts.append(relief.strip())

    # --- Issues Presented (FRAP 21(a)(2)(B)) ------------------------------
    parts.append(_section("Issues Presented"))
    parts.append(_numbered([i.strip() for i in issues]))

    # --- Jurisdiction -----------------------------------------------------
    parts.append(_section("Jurisdiction"))
    parts.append(jurisdiction.strip())

    # --- Statement of Facts (FRAP 21(a)(2)(C)) ----------------------------
    parts.append(_section("Statement of Facts"))
    parts.append(_numbered([f.strip() for f in facts]))

    # --- Reasons (FRAP 21(a)(2)(D)) ---------------------------------------
    parts.append(_section("Reasons Why the Writ Should Issue"))
    parts.append(
        "The Supreme Court has identified three conditions that must be "
        "satisfied before a writ of mandamus may issue. Cheney v. U.S. Dist. "
        "Court, 542 U.S. 367, 380-81 (2004). Each is satisfied here.\n"
    )

    parts.append(
        "I. PETITIONER HAS NO OTHER ADEQUATE MEANS TO ATTAIN THE RELIEF SOUGHT.\n"
    )
    parts.append(argument["no_other_adequate_means"].strip())

    parts.append(
        "\n\nII. PETITIONER'S RIGHT TO ISSUANCE OF THE WRIT IS CLEAR AND INDISPUTABLE.\n"
    )
    parts.append(argument["clear_and_indisputable_right"].strip())

    parts.append(
        "\n\nIII. THE WRIT IS APPROPRIATE UNDER THE CIRCUMSTANCES.\n"
    )
    parts.append(argument["appropriateness"].strip())

    # --- Conclusion / Prayer ----------------------------------------------
    parts.append(_section("Conclusion"))
    parts.append(
        f"For the foregoing reasons, {petitioner} respectfully requests that "
        "this Court issue a writ of mandamus granting the relief stated above, "
        "together with such other and further relief as the Court deems just "
        "and proper."
    )
    parts.append(
        f"\n\nRespectfully submitted,\n\n    /s/ {counsel['name']}\n"
        f"    {counsel['name']}\n"
        f"    {counsel.get('firm', '')}\n"
        f"    {counsel['address']}\n"
        f"    Tel: {counsel['phone']}\n"
        f"    Email: {counsel['email']}\n"
        f"    Counsel for Petitioner"
    )

    # --- Certificate of Service -------------------------------------------
    parts.append(_section("Certificate of Service"))
    service_list = config.get("service", [])
    parts.append(
        "I certify that on __________, 20__, I electronically filed the "
        "foregoing with the Clerk of the Court for the United States Court "
        "of Appeals for the Fifth Circuit using the CM/ECF system. I further "
        "certify that a copy was served by __________ on:\n"
    )
    if service_list:
        parts.append(_bulleted(service_list))
    else:
        parts.append("    [List respondent judge and all parties below.]")
    if real_party:
        parts.append(f"\n    Including: {real_party} (real party in interest).")
    parts.append(f"\n\n    /s/ {counsel['name']}\n    {counsel['name']}")

    # --- Certificate of Compliance (FRAP 32(g)) ---------------------------
    parts.append(_section("Certificate of Compliance"))
    parts.append(
        "1. This petition complies with the type-volume limit of Fed. R. App. "
        f"P. 21(d) because, excluding the parts exempted by Fed. R. App. P. "
        f"32(f), it contains ______ words (limit: {WORD_LIMIT}).\n\n"
        "2. This petition complies with the typeface requirements of Fed. R. "
        "App. P. 32(a)(5) and the type-style requirements of Fed. R. App. P. "
        "32(a)(6) because it has been prepared in a proportionally spaced "
        "typeface using __________ in 14-point __________ font."
    )
    parts.append(f"\n\n    /s/ {counsel['name']}\n    {counsel['name']}")

    return "\n".join(parts).rstrip() + "\n"


# Example config ------------------------------------------------------------


EXAMPLE_YAML = """\
# Fifth Circuit Mandamus Petition - configuration file.
# Fill in every field. Free-text fields may contain multi-paragraph content;
# they are inserted verbatim.

appeal_case_no: ""  # leave blank until the Fifth Circuit assigns a number

case:
  petitioner: "ACME Corporation"
  respondent: "Hon. Jane Doe, U.S. District Judge"
  real_party_in_interest: "John Smith"
  district_court: "United States District Court for the Southern District of Texas, Houston Division"
  district_case_no: "4:24-cv-01234"
  district_judge: "Jane Doe"

counsel:
  name: "A. Lawyer"
  firm: "Lawyer & Associates LLP"
  address: |
    123 Main Street, Suite 400
    Houston, TX 77002
  phone: "(713) 555-0100"
  email: "alawyer@example.com"
  bar_no: "TX 24000000"

interested_persons:
  - "ACME Corporation (Petitioner)"
  - "John Smith (Real Party in Interest)"
  - "A. Lawyer, Lawyer & Associates LLP (Counsel for Petitioner)"
  - "B. Counsel, Defense Firm LLP (Counsel for Real Party in Interest)"
  - "Hon. Jane Doe, United States District Judge (Respondent)"

oral_argument:
  requested: true
  reason: >-
    This petition presents a novel question concerning the scope of the
    attorney-client privilege in multi-district litigation, and oral argument
    would materially assist the Court.

issues:
  - >-
    Whether the district court clearly and indisputably erred by compelling
    production of documents protected by the attorney-client privilege.
  - >-
    Whether Petitioner has no other adequate means to obtain relief from the
    district court's order before the privileged information is disclosed.

facts:
  - "On January 3, 2026, Petitioner filed ... [describe procedural posture]."
  - "On February 14, 2026, the district court entered the order at issue ..."
  - "Petitioner timely moved for reconsideration, which the district court denied on ..."

jurisdiction: >-
  This Court has jurisdiction to issue a writ of mandamus under the All Writs
  Act, 28 U.S.C. Section 1651(a), in aid of its prospective appellate
  jurisdiction under 28 U.S.C. Section 1291.

argument:
  no_other_adequate_means: >-
    [Explain why appeal after final judgment, interlocutory review under
    Section 1292(b), certification, or any other vehicle is inadequate.
    Emphasize irreparable harm if the writ does not issue now.]
  clear_and_indisputable_right: >-
    [Explain the controlling authority that makes the district court's ruling
    plainly wrong. Cite Fifth Circuit decisions where possible. Distinguish
    any contrary authority.]
  appropriateness: >-
    [Explain why, in the exercise of the Court's discretion, the writ should
    issue: e.g., recurring question of first impression, supervisory need,
    usurpation of judicial power, etc.]

relief: >-
  Petitioner respectfully requests that this Court issue a writ of mandamus
  directing the district court to vacate its order of [date] and to enter an
  order [describe the specific relief].

service:
  - "Hon. Jane Doe, U.S. District Judge, [address]"
  - "B. Counsel, Defense Firm LLP, [address] (Counsel for Real Party in Interest)"
"""


EXAMPLE_JSON_NOTE = (
    "// Use mandamus_draft.py init --format json to generate a JSON starter.\n"
)


def write_example(path: Path, fmt: str) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite existing file: {path}")
    if fmt == "yaml":
        path.write_text(EXAMPLE_YAML, encoding="utf-8")
        return
    if fmt == "json":
        # Parse the YAML example and dump as JSON so the two stay in sync.
        if not HAS_YAML:
            raise SystemExit("JSON export requires PyYAML to parse the example template.")
        data = yaml.safe_load(EXAMPLE_YAML)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return
    raise SystemExit(f"unknown format: {fmt}")


# CLI -----------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> int:
    path = Path(args.output)
    fmt = args.format or ("yaml" if path.suffix.lower() in {".yaml", ".yml"} else "json")
    write_example(path, fmt)
    print(f"wrote example config to {path}")
    return 0


def cmd_draft(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    problems = validate(config)
    if problems:
        print("configuration problems:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        if not args.force:
            print("(pass --force to render anyway)", file=sys.stderr)
            return 2
    text = render(config)
    out_path = Path(args.output) if args.output else None
    if out_path:
        out_path.write_text(text, encoding="utf-8")
        print(f"wrote draft to {out_path}")
    else:
        sys.stdout.write(text)
    words = count_words(text)
    status = "OK" if words <= WORD_LIMIT else "OVER LIMIT"
    print(
        f"[rough word count: {words} / {WORD_LIMIT}  ({status})  "
        f"- not the official FRAP 32(f) count]",
        file=sys.stderr,
    )
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    problems = validate(config)
    if problems:
        for p in problems:
            print(f"  - {p}")
        return 1
    print("configuration looks complete.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mandamus_draft",
        description=(
            "Draft a Fifth Circuit petition for writ of mandamus from a "
            "configuration file. Drafting aid only; not legal advice."
        ),
    )
    sub = p.add_subparsers(dest="command", required=True)

    pi = sub.add_parser("init", help="write an example configuration file")
    pi.add_argument("output", help="path to write (e.g. config.yaml or config.json)")
    pi.add_argument(
        "--format",
        choices=("yaml", "json"),
        help="force format (otherwise inferred from the file extension)",
    )
    pi.set_defaults(func=cmd_init)

    pd = sub.add_parser("draft", help="render a petition draft from a config file")
    pd.add_argument("config", help="path to the configuration file")
    pd.add_argument("-o", "--output", help="write draft to this file (default: stdout)")
    pd.add_argument(
        "--force",
        action="store_true",
        help="render even if validation reports missing fields",
    )
    pd.set_defaults(func=cmd_draft)

    pc = sub.add_parser("check", help="validate a configuration file")
    pc.add_argument("config", help="path to the configuration file")
    pc.set_defaults(func=cmd_check)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
