# mandamus_draft

A small command-line tool that assembles a draft **petition for writ of
mandamus** for the United States Court of Appeals for the Fifth Circuit from
a structured configuration file.

The generated draft follows:

- Fed. R. App. P. 21 (form, contents, length)
- Fed. R. App. P. 32 (typography; word count exclusions)
- 5th Cir. R. 21 (local mandamus rule)
- 5th Cir. R. 28.2.1 (Certificate of Interested Persons)
- 5th Cir. R. 32 (local form requirements)

> **Drafting aid only.** This tool is not legal advice and is not a substitute
> for counsel's review. Every section of the output must be reviewed, revised,
> and verified against the current rules before filing.

## Requirements

- Python 3.9+
- `PyYAML` (optional, only needed for YAML configs). JSON works with the
  standard library alone.

## Usage

Create a starter config:

```
python3 mandamus_draft.py init config.yaml
```

Validate:

```
python3 mandamus_draft.py check config.yaml
```

Render the draft:

```
python3 mandamus_draft.py draft config.yaml -o petition.txt
```

The tool prints a rough word count (whole document) as a sanity check. The
official FRAP 32(f) count excludes the cover page, tables, and certificates
and must be computed separately before filing.

## Sections produced

1. Cover page
2. Certificate of Interested Persons
3. Statement Regarding Oral Argument
4. Table of Contents / Table of Authorities (placeholders)
5. Relief Sought
6. Issues Presented
7. Jurisdiction
8. Statement of Facts
9. Reasons Why the Writ Should Issue (the three *Cheney* prongs)
10. Conclusion and prayer for relief
11. Certificate of Service
12. Certificate of Compliance (FRAP 32(g))

## Tests

```
python3 -m unittest discover -s tests -v
```
