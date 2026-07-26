# radio-codeplug-toolkit

Give this repo a CSV of repeaters & it builds a codeplug file for your radio. No manual data entry into the CPS software, no re-typing 83 frequencies by hand.

## What it does

The toolkit is two layers. `generic_channel_parser.py` reads a repeater CSV & normalizes it into a plain list of channels: RX frequency, TX frequency, tones, name. It doesn't know or care what radio you own.

The `writers/` folder holds one module per radio model. Each module knows that specific radio's file format & converts the normalized channel list into it. Right now there's one: `writers/baofeng_bf_h802.py`, built for the Baofeng BF-H802's CPS software.

## Why two layers

Baofeng's BF-H802 saves its codeplug as a raw .NET BinaryFormatter (NRBF) stream, not a text file. The channel array is a fixed 1000 slots. Objects reference each other through deferred forward references instead of being written inline, and the strings `""` & `"OFF"` get reused via reference every time they recur instead of being re-written. Get any of that wrong & the CPS software throws a bare "Failure!" dialog with no further detail.

None of that has anything to do with parsing a CSV. Splitting the CSV logic from the file-format logic means the parser gets written once & reused for every radio, while each new radio only requires a new writer module, not a new parser.

## Usage

```python
from generic_channel_parser import parse_repeater_csv
from writers.baofeng_bf_h802 import build, from_normalized_channels

channels = parse_repeater_csv(
    "repeaters.csv",
    include_simplex_calling=("223.50000", "Simplex"),
)
native = from_normalized_channels(channels)
build("original_radio.dat", native, "updated_radio.dat")
```

That call took an 83-repeater CSV & produced a working 1_25_Radio_updated.dat, verified byte-identical to the original in every section the channels didn't touch.

## Adding a new radio

Check the file format first. Some CPS software saves plain CSV or XML; those just need a parser & a field-mapping function. Others use a binary serialization format, and NRBF-based ones tend to share the same three traps: forward references, fixed-length arrays, string interning.

If you hit a binary format, don't guess. Open the original file in the real CPS software, change nothing, & hit Save. Byte-diff that against your first attempt. That's how `baofeng_bf_h802.py` got built: two failed attempts guessing at the format, then a working file within 42 bytes of the real one after diffing against an actual software save.

Every writer module needs two functions to plug into the rest of the toolkit: `from_normalized_channels()`, which maps the generic field names onto the radio's native ones, and `build()`, which takes the original file plus the converted channel list & writes the new file.

## CSV format

The parser auto-detects common column name variants: Output Freq / RX Freq / Downlink for the receive frequency, Input Freq / TX Freq / Uplink for transmit, plus Offset, Uplink Tone, Downlink Tone, Call, and Location. Blank or "CSQ" tone entries map to OFF. Rows tagged as digital-only (DMR, D-STAR, P25, NXDN, YSF, C4FM) with no FM mode listed get skipped, since this toolkit is for analog only.

## Status

One radio supported: Baofeng BF-H802. Add a writer module for anything else & send a pull request.
