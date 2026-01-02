# Daily Claude Code Transcript Summary

Genereer dagelijkse samenvattingen van Claude Code transcripties.

## Installatie

```bash
# Maak virtuele omgeving
uv venv

# Installeer dependencies
uv pip install -e .
```

## Configuratie

Maak een `.env` bestand met je Anthropic API key:

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

## Gebruik

```bash
# Samenvatting voor gisteren (default)
python daily_summary.py

# Samenvatting voor specifieke datum
python daily_summary.py --date 20260101

# Dry-run (toon welke transcripties worden verwerkt)
python daily_summary.py --dry-run
```

## Output

Per dag wordt een folder aangemaakt met drie bestanden:

```text
claude-transcripts/
└── 20260101/
    ├── 20260101-summary.md   # AI-gegenereerde samenvatting + bronverwijzingen
    ├── 20260101-journal.md   # Leeg template voor eigen notities
    └── 20260101-stats.json   # Statistieken in JSON formaat
```

Voorbeeld `stats.json`:

```json
{
  "date": "2026-01-01",
  "stats": {
    "prompts": 42,
    "messages": 84,
    "tool_calls": 156,
    "commits": 8
  }
}
```

De summary bevat onderaan een "Bronnen" sectie met links naar de originele transcript folders.

De `claude-transcripts/` folder staat in `.gitignore` en wordt niet meegenomen in git.

## Hoe het werkt

1. Filtert `.jsonl` transcripties uit `~/.claude/projects/` op datum
2. Converteert naar HTML via `claude-code-transcripts`
3. Converteert HTML naar markdown via `markitdown`
4. Verzamelt statistieken uit de transcripties
5. Genereert samenvatting met Claude API (claude-sonnet-4)
6. Schrijft alle bestanden naar iCloud folder

## Dependencies

- `anthropic` - Claude API
- `click` - CLI interface
- `markitdown` - HTML naar markdown conversie
- `claude-code-transcripts` - Transcript naar HTML conversie
- `python-dotenv` - .env file loading
