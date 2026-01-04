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

# Optioneel: Custom output directory (default: iCloud)
# DAILY_SUMMARY_OUTPUT_DIR=/custom/path
```

**Default output locatie:** `~/Library/Mobile Documents/com~apple~CloudDocs/365 days of AI Code`

Als je een andere output directory wilt gebruiken, stel dan `DAILY_SUMMARY_OUTPUT_DIR` in via het `.env` bestand.

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

Per dag wordt een folder aangemaakt met drie bestanden in je iCloud Drive:

```text
~/Library/Mobile Documents/com~apple~CloudDocs/365 days of AI Code/
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

## Hoe het werkt

1. **Vindt transcripties**: Filtert `.jsonl` bestanden uit `~/.claude/projects/` die de target datum bevatten
2. **Date filtering**: Maakt tijdelijke gefilterde JSONL files met *alleen* entries van de target datum
3. **HTML conversie**: Converteert gefilterde transcripties naar HTML via `claude-code-transcripts`
4. **Markdown conversie**: Converteert HTML naar markdown via `markitdown`
5. **Statistieken**: Verzamelt stats (prompts, messages, tool calls, commits) voor de target datum
6. **AI samenvatting**: Genereert Nederlandse samenvatting met Claude API (claude-sonnet-4)
7. **Output**: Schrijft alle bestanden naar iCloud Drive (`~/Library/Mobile Documents/com~apple~CloudDocs/365 days of AI Code/`)

**Belangrijk:** Door de date filtering in stap 2 bevat de summary alleen content van de gevraagde datum, zelfs als een JSONL bestand entries van meerdere datums bevat.

## Dependencies

- `anthropic` - Claude API
- `click` - CLI interface
- `markitdown` - HTML naar markdown conversie
- `claude-code-transcripts` - Transcript naar HTML conversie
- `python-dotenv` - .env file loading
