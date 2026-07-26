# Standard Prompt: CSV Repeater List → Any Analog Radio Codeplug

This toolkit works for any radio, not just one model. It's split into two
layers so most of it never needs to be rebuilt:

- `generic_channel_parser.py` — reads your repeater CSV into a clean,
  radio-agnostic list of channels (frequencies, tones, names). Reuse this
  for every radio, every time. It doesn't know or care what brand radio
  you're targeting.
- `writers/<radio_name>.py` — one small module per radio model, each one
  knowing that radio's specific codeplug file format. The first time you
  use a given radio, Claude builds and verifies this module (see below).
  Every time after that, it's just reused.

---

## PROMPT (copy from here down)

I need you to build an updated codeplug from a CSV of analog
repeater/simplex frequencies, using my radio codeplug toolkit.

**Files attached:**
1. `[ORIGINAL_CODEPLUG_FILENAME]` — the base codeplug file to modify
2. `[CSV_FILENAME]` — repeater list (any reasonable column naming for
   output/input frequency, offset, tones, callsign, location — the parser
   auto-detects common variants)
3. `generic_channel_parser.py` — the radio-agnostic CSV parser, use as-is
4. `writers/[RADIO_MODEL].py` — **if I have a writer for this radio already,
   it's attached; use it as-is via its `build()` and
   `from_normalized_channels()` functions, do not regenerate it.**
   **If no writer is attached, this is a new radio — see "Building a new
   writer" below.**

**Radio model / CPS software:** `[e.g. Baofeng BF-H802, Anytone AT-778UV, etc.]`

**What I want done:**
- [ Keep the existing preset channels and append the new ones after them
    / Wipe existing channels and replace entirely with the new list ]
- [ Add a national FM simplex calling frequency as channel 1 — yes/no,
    and if yes, the frequency ]
- Channel name = [ Location / Call sign / both, truncated to fit the radio's
    display limit ]
- Tone mapping: Uplink Tone → TX CTCSS/DCS, Downlink Tone → RX CTCSS/DCS,
  blank or "CSQ" → OFF

**Workflow:**
1. Use `generic_channel_parser.parse_repeater_csv()` on the CSV to get a
   normalized channel list.
2. If a writer for `[RADIO_MODEL]` is attached: call its
   `from_normalized_channels()` to convert to that radio's native field
   names, then its `build()` to produce the output file.
3. Verify: round-trip the output back through whatever parsing the writer
   uses, confirm every new channel's fields match, and confirm untouched
   sections of the original file are byte-identical to the source.

---

## Building a new writer (first time only, for a radio not yet in the library)

If no writer is attached for this radio, tell me before doing anything else,
then:

1. Figure out the file format: is it plain text/CSV (many CHIRP-compatible
   radios), XML, or a binary serialization format? Inspect the raw bytes/
   structure of the attached original file to determine this — don't guess
   from the file extension alone.
2. If it's a structured text/XML format: parse it directly, find the
   channel-list section, and write a `writers/[radio_name].py` module with
   a `build(original_path, native_channels, out_path)` function and a
   `from_normalized_channels()` adapter matching the pattern in
   `writers/baofeng_bf_h802.py` (use that file as a reference for the
   module shape, not the binary-specific internals).
3. If it's a binary serialization format (e.g. another .NET NRBF-based CPS,
   like the Baofeng one): expect the same category of quirks we hit before —
   forward/deferred references, string interning of common literals, fixed-
   length arrays with placeholder padding. Use `nrbf.loads()` (or the
   equivalent library for that format) to read the original for reference
   values, then hand-roll a writer with `struct`.
4. **Critical**: if the first attempt fails to load in the radio's actual
   CPS software, get a real software-resaved reference file (open the
   original in the CPS software, change nothing, hit Save) and byte-diff it
   against your first attempt. Guessing at binary quirks burns far more
   effort than one real reference file. This is how the Baofeng writer got
   built — don't skip straight to guessing.
5. Once verified working, save the new module as `writers/[radio_name].py`
   using the same `build()` / `from_normalized_channels()` shape, so it
   drops into this same toolkit and gets reused next time without a rebuild.

---

## What to fill in / attach each time
- Original codeplug file + new CSV
- `generic_channel_parser.py` (always)
- `writers/[radio_model].py` if you've already built one for this radio —
  otherwise expect a one-time build-and-verify pass
- Radio model name
- Keep-vs-replace, simplex channel yes/no, naming convention

## If a writer fails to load in the CPS software
Get a real software-resaved reference file and send it over — byte-diffing
against real software output is far faster than guessing at binary quirks.
