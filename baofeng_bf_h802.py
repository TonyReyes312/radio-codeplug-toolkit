"""
NRBF writer for Baofeng BF-H802 .dat codeplugs.

Usage:
    new_channels = [
        {'rxFreq': '223.50000', 'txFreq': '223.50000',
         'strRxCtsDcs': 'OFF', 'strTxCtsDcs': 'OFF',
         'scanAdd': 1, 'name': 'Simplex'},
        ... one dict per channel, in the order you want them written ...
    ]
    build('original_radio.dat', new_channels, 'updated_radio.dat')

By default, build() finds the first empty channel slot in the original file
and appends new_channels starting there, preserving everything before it.
Pass final_channels=[...] (a full 1000-entry list) instead if you need custom
placement (e.g. wiping the existing channels and starting from index 0).

Requires: pip install nrbf --break-system-packages
"""
import struct, json, nrbf

class Writer:
    def __init__(self):
        self.buf = []
        self.next_id = 1
        self.class_meta = {}
        self.queue = []  # list of thunks (callables) to run after current frame
        self.string_cache = {}  # interning cache for hardcoded default literals only

    def alloc_id(self):
        v = self.next_id
        self.next_id += 1
        return v

    def u8(self, v): self.buf.append(struct.pack('<B', v))
    def i32(self, v): self.buf.append(struct.pack('<i', v))
    def f32(self, v): self.buf.append(struct.pack('<f', v))

    def lps(self, s):
        b = s.encode('utf-8')
        length = len(b)
        while True:
            byte = length & 0x7F
            length >>= 7
            if length:
                self.u8(byte | 0x80)
            else:
                self.u8(byte)
                break
        self.buf.append(b)

    INTERNED_LITERALS = ("", "OFF")

    def binary_object_string(self, s):
        if s in self.INTERNED_LITERALS and s in self.string_cache:
            self.member_reference(self.string_cache[s])
            return self.string_cache[s]
        obj_id = self.alloc_id()
        self.u8(6)
        self.i32(obj_id)
        self.lps(s)
        if s in self.INTERNED_LITERALS:
            self.string_cache[s] = obj_id
        return obj_id

    def member_reference(self, ref_id):
        self.u8(9)
        self.i32(ref_id)

    def primitive(self, ptype, value):
        if ptype == 8:
            self.i32(int(value))
        elif ptype == 1:
            self.u8(1 if value else 0)
        elif ptype == 5:
            self.lps(str(value))
        elif ptype == 11:
            self.f32(float(value))
        else:
            raise ValueError(f"unhandled ptype {ptype}")

    def class_with_members_and_types_header(self, class_name, member_names, member_types, member_additional, lib_id, obj_id):
        self.u8(5)
        self.i32(obj_id)
        self.lps(class_name)
        self.i32(len(member_names))
        for n in member_names:
            self.lps(n)
        type_code = {'Primitive':0,'String':1,'Object':2,'SystemClass':3,'Class':4,
                     'ObjectArray':5,'StringArray':6,'PrimitiveArray':7}
        for t in member_types:
            self.u8(type_code[t])
        for t, add in zip(member_types, member_additional):
            if t in ('Primitive', 'PrimitiveArray'):
                self.u8(add)
            elif t == 'SystemClass':
                self.lps(add)
            elif t == 'Class':
                self.lps(add[0])
                self.i32(add[1])
        self.i32(lib_id)
        self.class_meta[class_name] = obj_id

    def class_with_id_header(self, class_name, obj_id):
        self.u8(1)
        self.i32(obj_id)
        self.i32(self.class_meta[class_name])

    def array_header_primitive(self, obj_id, length, ptype):
        self.u8(15)
        self.i32(obj_id)
        self.i32(length)
        self.u8(ptype)

    def array_header_string(self, obj_id, length):
        self.u8(17)
        self.i32(obj_id)
        self.i32(length)

    def array_header_class(self, obj_id, class_name, lib_id, length):
        self.u8(7)
        self.i32(obj_id)
        self.u8(0)
        self.i32(1)
        self.i32(length)
        self.u8(4)
        self.lps(class_name)
        self.i32(lib_id)

    def message_end(self):
        self.u8(11)

    def header(self, root_id):
        self.u8(0)
        self.i32(root_id)
        self.i32(-1)
        self.i32(1)
        self.i32(0)

    def binary_library(self, name):
        lib_id = self.alloc_id()
        self.u8(12)
        self.i32(lib_id)
        self.lps(name)
        return lib_id

    def bytes(self):
        return b''.join(self.buf)

    # ---- deferral helpers ----
    def defer(self, thunk):
        """Reserve an id, emit a MemberReference now, queue thunk(obj_id) for later."""
        obj_id = self.alloc_id()
        self.member_reference(obj_id)
        self.queue.append((obj_id, thunk))
        return obj_id

    def drain_queue(self):
        while self.queue:
            obj_id, thunk = self.queue.pop(0)
            thunk(obj_id)


LIB_NAME = 'T6UV Series EN CPS, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null'

CHANNEL_MEMBERS = ['id','rxFreq','strRxCtsDcs','txFreq','strTxCtsDcs','busyLock','txPower',
                   'bandwide','scanAdd','sqMode','pttid','signalGroup','fhss','name']
CHANNEL_TYPES = ['Primitive','String','String','String','String','Primitive','Primitive',
                 'Primitive','Primitive','Primitive','Primitive','Primitive','Primitive','String']
CHANNEL_ADD = [8,None,None,None,None,8,8,8,8,8,8,8,8,None]

VFO_MEMBERS = ['vfoAFreq','strVFOARxCtsDcs','strVFOATxCtsDcs','vfoABusylock','vfoADir','vfoApttid',
               'vfoASignalGroup','vfoATxPower','vfoABandwide','vfoASQMode','vfoAStep','vfoAFhss','vfoAOffset',
               'vfoBFreq','strVFOBRxCtsDcs','strVFOBTxCtsDcs','vfoBBusyLock','vfoBDir','vfoBpttid',
               'vfoBSignalGroup','vfoBTxPower','vfoBBandwide','vfoBSQMode','vfoBStep','vfoBFhss','vfoBOffset',
               'busyLock','vfoScanRang_L','vfoScanRang_H']
VFO_TYPES = ['String','String','String','Primitive','Primitive','Primitive','Primitive','Primitive','Primitive',
             'Primitive','Primitive','Primitive','String','String','String','String','Primitive','Primitive',
             'Primitive','Primitive','Primitive','Primitive','Primitive','Primitive','Primitive','String',
             'Primitive','Primitive','Primitive']
VFO_ADD = [None,None,None,8,8,8,8,8,8,8,8,8,None,None,None,None,8,8,8,8,8,8,8,8,8,None,8,5,5]

FUNC_MEMBERS = ['sql','saveMode','vox','voxDlyTime','dualStandby','tot','beep','sideTone','scanMode','voiceSw',
                'voice','pttDly','chADisType','chBDisType','autoLock','micGain','alarmMode','alarmTone',
                'tailClear','rptTailClear','rptTailDet','roger','fmEnable','chAWorkmode','chBWorkmode','keyLock',
                'autoPowerOff','powerOnDisType','tone','signalingSystem','backlight','menuQuitTime','key1Short',
                'key1Long','key2Short','key2Long','bright','rstMenu','totAlarm','gpsSw','gpsMode','ctsDcsScanType']
FUNC_TYPES = ['Primitive'] * len(FUNC_MEMBERS)
FUNC_ADD = [8] * len(FUNC_MEMBERS)

FM_MEMBERS = ['channels','curFreq']
FM_TYPES = ['PrimitiveArray','Primitive']
FM_ADD = [8,8]

DTMF_MEMBERS = ['localID','group','groupName','press','release','wordTime','idleTime','hangUp']
DTMF_TYPES = ['String','StringArray','StringArray','Primitive','Primitive','Primitive','Primitive','Primitive']
DTMF_ADD = [None,None,None,1,1,8,8,8]

APPDATA_MEMBERS = ['channels','vfos','funCfgs','fms','dtmfs','line1Msg','line2Msg','bufStrModelType']
APPDATA_TYPES = ['Class','Class','Class','Class','Class','String','String','String']


def write_member_value(w, t, a, v, class_name_for_array=None, lib_id=None):
    """Write a single member's value inline (primitives/strings) using w's current buffer position."""
    if t == 'Primitive':
        w.primitive(a, v)
    elif t == 'String':
        w.binary_object_string(v if v is not None else '')
    else:
        raise ValueError("call write_deferred_member instead")


def write_channel_body(w, ch, first, obj_id):
    lib_id = w.class_meta.get('__lib__')
    if first:
        w.class_with_members_and_types_header('BF_H802_CPS.Channel', CHANNEL_MEMBERS, CHANNEL_TYPES, CHANNEL_ADD, lib_id, obj_id)
    else:
        w.class_with_id_header('BF_H802_CPS.Channel', obj_id)
    for name, t in zip(CHANNEL_MEMBERS, CHANNEL_TYPES):
        v = ch.get(name, 0 if t == 'Primitive' else '')
        write_member_value(w, t, 8, v)


def write_simple_class_body(w, class_name, members, types, add, obj, obj_id):
    lib_id = w.class_meta.get('__lib__')
    w.class_with_members_and_types_header(class_name, members, types, add, lib_id, obj_id)
    for name, t, a in zip(members, types, add):
        v = obj[name]
        if t == 'Primitive':
            w.primitive(a, v)
        elif t == 'String':
            w.binary_object_string(v if v is not None else '')
        elif t == 'PrimitiveArray':
            def thunk(aid, v=v, a=a):
                w.array_header_primitive(aid, len(v), a)
                for item in v:
                    w.primitive(a, item)
            w.defer(thunk)
        elif t == 'StringArray':
            def thunk(aid, v=v):
                w.array_header_string(aid, len(v))
                for item in v:
                    w.binary_object_string(item if item is not None else '')
            w.defer(thunk)


def from_normalized_channels(channels, active=True):
    """
    Adapter: converts generic_channel_parser.py's normalized channel dicts
    (rx_freq, tx_freq, rx_tone, tx_tone, name) into this radio's native
    field names (rxFreq, strRxCtsDcs, txFreq, strTxCtsDcs, scanAdd, name).
    Every radio-specific writer should expose a function like this so the
    generic parser output can plug into any writer without the parser
    needing to know radio-specific field names.
    """
    return [
        {
            'rxFreq': c['rx_freq'], 'strRxCtsDcs': c['rx_tone'],
            'txFreq': c['tx_freq'], 'strTxCtsDcs': c['tx_tone'],
            'scanAdd': 1 if active else 0, 'name': c['name'],
        }
        for c in channels
    ]


def build(orig_dat_path, new_channels, out_path, final_channels=None):
    orig = nrbf.loads(open(orig_dat_path, 'rb').read())
    channels = orig['channels']

    if final_channels is None:
        first_empty = None
        for i, c in enumerate(channels):
            if c['scanAdd'] == 0 and c['rxFreq'] == '':
                first_empty = i
                break
        assert first_empty is not None
        assert first_empty + len(new_channels) <= len(channels)

        final_channels = []
        for i, c in enumerate(channels):
            if first_empty <= i < first_empty + len(new_channels):
                nc = new_channels[i - first_empty]
                final_channels.append({
                    'id': 0, 'rxFreq': nc['rxFreq'], 'strRxCtsDcs': nc['strRxCtsDcs'],
                    'txFreq': nc['txFreq'], 'strTxCtsDcs': nc['strTxCtsDcs'],
                    'busyLock': 0, 'txPower': 0, 'bandwide': 0, 'scanAdd': nc['scanAdd'],
                    'sqMode': 0, 'pttid': 0, 'signalGroup': 0, 'fhss': 0, 'name': nc['name'],
                })
            else:
                final_channels.append(c)

    w = Writer()
    w.header(1)
    w.next_id = 1
    appdata_id = w.alloc_id()          # 1
    lib_id = w.binary_library(LIB_NAME)  # 2
    w.class_meta['__lib__'] = lib_id

    APPDATA_ADD = [('BF_H802_CPS.Channel[]', lib_id), ('BF_H802_CPS.VFOInfos', lib_id),
                   ('BF_H802_CPS.Function', lib_id), ('BF_H802_CPS.FMChannel', lib_id),
                   ('BF_H802_CPS.DTMF', lib_id), None, None, None]

    w.class_with_members_and_types_header('BF_H802_CPS.AppData', APPDATA_MEMBERS, APPDATA_TYPES, APPDATA_ADD, lib_id, appdata_id)

    # channels: deferred array-of-class
    def channels_thunk(aid):
        w.array_header_class(aid, 'BF_H802_CPS.Channel', lib_id, len(final_channels))
        channel_ids = [w.alloc_id() for _ in range(len(final_channels))]
        for cid in channel_ids:
            w.member_reference(cid)
        for i, (ch, cid) in enumerate(zip(final_channels, channel_ids)):
            w.queue.append((cid, lambda oid, ch=ch, first=(i == 0): write_channel_body(w, ch, first, oid)))
    w.defer(channels_thunk)

    def make_simple_thunk(class_name, members, types, add, obj):
        def thunk(oid):
            write_simple_class_body(w, class_name, members, types, add, obj, oid)
        return thunk

    w.defer(make_simple_thunk('BF_H802_CPS.VFOInfos', VFO_MEMBERS, VFO_TYPES, VFO_ADD, orig['vfos']))
    w.defer(make_simple_thunk('BF_H802_CPS.Function', FUNC_MEMBERS, FUNC_TYPES, FUNC_ADD, orig['funCfgs']))
    w.defer(make_simple_thunk('BF_H802_CPS.FMChannel', FM_MEMBERS, FM_TYPES, FM_ADD, orig['fms']))
    w.defer(make_simple_thunk('BF_H802_CPS.DTMF', DTMF_MEMBERS, DTMF_TYPES, DTMF_ADD, orig['dtmfs']))

    w.binary_object_string(orig['line1Msg'])
    w.binary_object_string(orig['line2Msg'])
    w.binary_object_string(orig['bufStrModelType'])

    w.drain_queue()
    w.message_end()

    with open(out_path, 'wb') as f:
        f.write(w.bytes())
    return w.bytes()


if __name__ == '__main__':
    # Example usage — replace paths and new_channels.json with your own.
    new_channels = json.load(open('new_channels.json'))
    out_bytes = build('original_radio.dat', new_channels, 'updated_radio.dat')
    print("wrote", len(out_bytes), "bytes")
