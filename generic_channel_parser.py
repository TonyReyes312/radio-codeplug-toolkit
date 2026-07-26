"""
Radio-agnostic parser: turns a CSV of analog repeater/simplex frequencies
into a normalized list of channel dicts that any radio-specific writer can
consume. This part does NOT know or care what brand/model radio it's for —
that's the whole point. Keep this the same across every radio project;
only the writer module changes per radio.

Expected CSV columns (case-insensitive, order doesn't matter — common
variants are matched automatically):
    Output Freq / Output Frequency / RX Freq / Downlink
    Input Freq  / Input Frequency  / TX Freq / Uplink   (optional — defaults
                                                          to Output Freq for
                                                          simplex entries)
    Offset                                    (optional, +/- MHz; used only
                                                if Input Freq column absent)
    Uplink Tone / TX Tone / PL                (optional)
    Downlink Tone / RX Tone                   (optional)
    Call / Callsign                           (optional)
    Location / City                           (optional)
    County                                    (optional)
    State                                     (optional)
    Modes                                     (optional — rows with digital
                                                only modes and no analog mode
                                                are skipped)

Output: list of dicts with normalized keys:
    {
      'rx_freq': '223.50000',      # 5-decimal string, what the radio receives on
      'tx_freq': '223.50000',      # 5-decimal string, what the radio transmits on
      'rx_tone': 'OFF' | '91.5' | 'D025N',
      'tx_tone': 'OFF' | '91.5' | 'D025N',
      'name':    'Best 10-char name for this channel',
      'call':    'W1ABC' or '',
      'location':'Springfield' or '',
    }

This is intentionally generic. A radio-specific writer decides how to map
these normalized fields onto its own binary/text file format.
"""
import csv


COLUMN_ALIASES = {
    'rx_freq':     ['output freq', 'output frequency', 'rx freq', 'downlink', 'downlink freq', 'output'],
    'tx_freq':     ['input freq', 'input frequency', 'tx freq', 'uplink', 'uplink freq', 'input'],
    'offset':      ['offset'],
    'tx_tone':     ['uplink tone', 'tx tone', 'pl', 'ctcss', 'input tone'],
    'rx_tone':     ['downlink tone', 'rx tone', 'output tone'],
    'call':        ['call', 'callsign', 'call sign'],
    'location':    ['location', 'city'],
    'county':      ['county'],
    'state':       ['state'],
    'modes':       ['modes', 'mode'],
}


def _match_column(header_row, aliases):
    lower = {h.strip().lower(): h for h in header_row}
    for alias in aliases:
        if alias in lower:
            return lower[alias]
    return None


def _fmt_freq(raw):
    """Normalize a frequency string to 5 decimal places, e.g. '223.5' -> '223.50000'."""
    raw = raw.strip()
    if not raw:
        return ''
    return f"{float(raw):.5f}"


def _fmt_tone(raw):
    raw = (raw or '').strip().upper()
    if raw in ('', 'CSQ', 'NONE', 'OFF'):
        return 'OFF'
    return raw  # e.g. '91.5' or 'D025N' — pass through as-is


def parse_repeater_csv(path, name_field='location', name_maxlen=10,
                        include_simplex_calling=None, skip_digital_only=True):
    """
    path: path to the CSV file
    name_field: which normalized field to build the channel name from
                ('location', 'call', or 'both')
    name_maxlen: truncate channel name to this length (radio display limits vary)
    include_simplex_calling: optional (freq, label) tuple to prepend as
                              channel 1, e.g. ('223.50000', 'Simplex')
    skip_digital_only: skip rows whose Modes column indicates digital-only
                        (e.g. 'DMR', 'D-STAR') with no analog/FM mode present

    Returns: list of normalized channel dicts (see module docstring).
    """
    channels = []

    if include_simplex_calling:
        freq, label = include_simplex_calling
        channels.append({
            'rx_freq': _fmt_freq(freq), 'tx_freq': _fmt_freq(freq),
            'rx_tone': 'OFF', 'tx_tone': 'OFF',
            'name': label[:name_maxlen], 'call': '', 'location': '',
        })

    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return channels

    header = rows[0]
    col = {key: _match_column(header, aliases) for key, aliases in COLUMN_ALIASES.items()}
    idx = {key: header.index(col[key]) if col[key] else None for key in col}

    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue

        def get(key, default=''):
            i = idx.get(key)
            if i is None or i >= len(row):
                return default
            return row[i].strip()

        modes = get('modes').upper()
        if skip_digital_only and modes and 'FM' not in modes and 'ANALOG' not in modes and modes not in ('',):
            # Row explicitly lists only digital modes (e.g. "DMR", "D-STAR") — skip.
            digital_markers = ('DMR', 'D-STAR', 'DSTAR', 'P25', 'NXDN', 'YSF', 'C4FM')
            if any(m in modes for m in digital_markers) and 'FM' not in modes:
                continue

        rx_freq_raw = get('rx_freq')
        tx_freq_raw = get('tx_freq')
        if not rx_freq_raw:
            continue  # no usable output frequency, skip row

        if tx_freq_raw:
            tx_freq = _fmt_freq(tx_freq_raw)
        else:
            offset = get('offset')
            if offset:
                tx_freq = _fmt_freq(str(float(rx_freq_raw) + float(offset)))
            else:
                tx_freq = _fmt_freq(rx_freq_raw)  # simplex fallback

        location = get('location')
        call = get('call')
        if name_field == 'call':
            name = call or location
        elif name_field == 'both':
            name = f"{call} {location}".strip()
        else:
            name = location or call

        channels.append({
            'rx_freq': _fmt_freq(rx_freq_raw),
            'tx_freq': tx_freq,
            'rx_tone': _fmt_tone(get('rx_tone')),
            'tx_tone': _fmt_tone(get('tx_tone')),
            'name': name[:name_maxlen],
            'call': call,
            'location': location,
        })

    return channels


if __name__ == '__main__':
    import sys, json
    chans = parse_repeater_csv(sys.argv[1])
    print(json.dumps(chans, indent=2))
