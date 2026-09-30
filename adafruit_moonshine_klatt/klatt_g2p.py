# SPDX-FileCopyrightText: 2026 Moonshine AI (original C++), Adafruit port
# SPDX-License-Identifier: MIT
"""English text -> base-phone tokens.

Ported from moonshine micro/g2p: g2p.cc (TextToPhones), g2p_rules.cc (letter-to-sound),
g2p_numbers.cc (numerals), ipa_tokens.cc (TokenizeIpa), and the key normalization and
override lexicon from g2p_dict.cc.

Per word the lookup order is: user overrides -> numbers -> dictionary -> rules. The
dictionary is pluggable: any object with lookup(key) -> ipa or None, where key comes from
normalize_word_key(). Moonshine's letter-homophone table is empty upstream and is omitted.
"""

PRIMARY = "ˈ"
SECONDARY = "ˌ"

# ---------------------------------------------------------------------------
# Tokenizer (ipa_tokens.cc)
# ---------------------------------------------------------------------------

# Longest-first rewrite rules: (pattern, emitted tokens)
_IPA_RULES = (
    ("eɪ", ("e", "ɪ")),
    ("ɑɪ", ("ɑ", "ɪ")),
    ("aɪ", ("ɑ", "ɪ")),
    ("ɑʊ", ("ɑ", "ʊ")),
    ("aʊ", ("ɑ", "ʊ")),
    ("ɔɪ", ("ɔ", "ɪ")),
    ("oʊ", ("o", "ʊ")),
    ("əʊ", ("o", "ʊ")),
    ("tʃ", ("t", "ʃ")),
    ("dʒ", ("d", "ʒ")),
    ("ː", ()),
    ("ˈ", ("ˈ",)),
    ("ˌ", ("ˌ",)),
    ("ɡ", ("g",)),
    ("ɚ", ("ɝ",)),
    ("ɘ", ("ə",)),
    ("ɐ", ("ʌ",)),
    ("ɜ", ("ɝ",)),
    ("ɒ", ("ɔ",)),
    ("ɾ", ("d",)),
    ("ɪ", ("ɪ",)),
    ("ɛ", ("ɛ",)),
    ("æ", ("æ",)),
    ("ɑ", ("ɑ",)),
    ("ɔ", ("ɔ",)),
    ("ʊ", ("ʊ",)),
    ("ʌ", ("ʌ",)),
    ("ɝ", ("ɝ",)),
    ("ə", ("ə",)),
    ("ŋ", ("ŋ",)),
    ("θ", ("θ",)),
    ("ð", ("ð",)),
    ("ʃ", ("ʃ",)),
    ("ʒ", ("ʒ",)),
    ("ɹ", ("ɹ",)),
    ("a", ("ɑ",)),
    ("r", ("ɹ",)),
    ("y", ("j",)),
    ("g", ("g",)),
    (" ", (" ",)),
    ("\t", (" ",)),
    ("\n", (" ",)),
)
_DIRECT_ASCII = "ieoupbtdkmnfvszhwjl"


def tokenize_ipa(ipa):
    """Split an IPA string into base-phone tokens (diphthongs and affricates split)."""
    out = []
    i = 0
    n = len(ipa)
    while i < n:
        for pattern, emit in _IPA_RULES:
            if ipa.startswith(pattern, i):
                out.extend(emit)
                i += len(pattern)
                break
        else:
            c = ipa[i]
            if c in _DIRECT_ASCII:
                out.append(c)
            i += 1
    return out


# ---------------------------------------------------------------------------
# Word keys and overrides (g2p_dict.cc)
# ---------------------------------------------------------------------------


def normalize_word_key(word):
    """Lowercase ASCII letters and apostrophes, with surrounding apostrophes stripped."""
    key = "".join(c for c in word.lower() if ("a" <= c <= "z") or c == "'")
    return key.strip("'")


def _letters(word):
    return "".join(c for c in word.lower() if "a" <= c <= "z")


class Lexicon:
    """Runtime word -> IPA overrides (proper nouns etc.). Later entries win."""

    def __init__(self, entries=None):
        self._map = {}
        if entries:
            for word, ipa in entries:
                self.add(word, ipa)

    def add(self, word, ipa):
        key = normalize_word_key(word)
        if key and ipa:
            self._map[key] = ipa

    def lookup(self, key):
        return self._map.get(key)


# ---------------------------------------------------------------------------
# Numbers (g2p_numbers.cc)
# ---------------------------------------------------------------------------

_UNITS = ("ˈzɪroʊ", "wˈʌn", "tˈu", "θɹˈi", "fˈɔɹ", "fˈaɪv", "sˈɪks", "sˈɛvən", "ˈeɪt", "nˈaɪn")
_TEENS = (
    "tˈɛn",
    "ɪlˈɛvən",
    "twˈɛlv",
    "θɝˈtin",
    "fɔɹˈtin",
    "fˈɪftin",
    "sˈɪkstin",
    "sˈɛvəntin",
    "ˈeɪtin",
    "nˈaɪntin",
)
_TENS = (
    None,
    None,
    "twˈɛnti",
    "θˈɝdi",
    "fˈɔɹti",
    "fˈɪfti",
    "sˈɪksti",
    "sˈɛvənti",
    "ˈeɪti",
    "nˈaɪnti",
)
_DIGITS = ("ˈzɪroʊ", "ˈwʌn", "ˈtu", "ˈθɹi", "ˈfɔɹ", "ˈfaɪv", "ˈsɪks", "ˈsɛvən", "ˈeɪt", "ˈnaɪn")
_SCALES = (
    (1000000000000, "ˌtrˈɪljən"),
    (1000000000, "ˌbˈɪljən"),
    (1000000, "ˌmˈɪljən"),
    (1000, "ˌθˈaʊzənd"),
)
_ZERO = "ˈzɪroʊ"
_ASCII_DIGITS = "0123456789"


def _digit_sequence(digits):
    return SECONDARY.join(_DIGITS[ord(c) - 48] for c in digits if c in _ASCII_DIGITS)


def _under100(n):
    if n < 10:
        return _UNITS[n]
    if n < 20:
        return _TEENS[n - 10]
    t = _TENS[n // 10]
    u = n % 10
    return t if u == 0 else t + SECONDARY + _UNITS[u]


def _under1000(n):
    if n < 100:
        return _under100(n)
    head = _UNITS[n // 100] + "ˌhˈʌndrɪd"
    r = n % 100
    return head if r == 0 else head + SECONDARY + _under100(r)


def _cardinal(n):
    if n < 0 or n >= 1000000000000000:
        return None
    if n == 0:
        return _ZERO
    rem = n
    parts = []
    for mag, sfx in _SCALES:
        if rem >= mag:
            q = rem // mag
            rem %= mag
            if q > 0:
                parts.append(_under1000(q) + sfx)
    if rem > 0:
        parts.append(_under1000(rem))
    return SECONDARY.join(parts)


def _to_int64(digits):
    # C++ accumulates into a signed long long; keep its wraparound.
    n = 0
    for c in digits:
        n = (n * 10 + (ord(c) - 48) + (1 << 63)) % (1 << 64) - (1 << 63)
    return n


def number_to_ipa(token):
    """IPA for a plain numeral ("123", "-4", "3.5", "007", "1,000"), else None."""
    s = token.strip(" \t\n\r\f\v")
    s = "".join(c for c in s if c not in ",_ ")
    if not s:
        return None
    neg = False
    if s[0] in "+-":
        neg = s[0] == "-"
        s = s[1:]
    if not s or s.count(".") > 1:
        return None

    def with_sign(v):
        return "nˈɛɡətɪvˌ" + v if neg else v

    def all_digits(x):
        for c in x:
            if c not in _ASCII_DIGITS:
                return False
        return True

    dot = s.find(".")
    if dot >= 0:
        whole = s[:dot]
        frac = s[dot + 1 :]
        if not (all_digits(whole) and all_digits(frac)):
            return None
        if not whole:
            left = _ZERO
        elif len(whole) > 1 and whole[0] == "0":
            left = _digit_sequence(whole)
        else:
            left = _cardinal(_to_int64(whole)) or _digit_sequence(whole)
        if not frac:
            return with_sign(left)
        return with_sign(left + "ˌˈpɔɪntˌ" + _digit_sequence(frac))

    if not all_digits(s):
        return None
    if len(s) > 1 and s[0] == "0":
        return with_sign(_digit_sequence(s))
    return with_sign(_cardinal(_to_int64(s)) or _digit_sequence(s))


# ---------------------------------------------------------------------------
# Letter-to-sound rules (g2p_rules.cc)
# ---------------------------------------------------------------------------

_VOWELS = "aeiouy"

_LITERALS = (
    ("tch", "tʃ"),
    ("dge", "dʒ"),
    ("tion", "ʃən"),
    ("sion", "ʒən"),
    ("sure", "ʒɚ"),
    ("ture", "tʃɚ"),
    ("ough", "oʊ"),
    ("augh", "ɔː"),
    ("eigh", "eɪ"),
    ("igh", "aɪ"),
    ("oar", "ɔɹ"),
    ("our", "aʊɹ"),
    ("oor", "ɔɹ"),
    ("ear", "ɪɹ"),
    ("eer", "ɪɹ"),
    ("ier", "ɪɹ"),
    ("air", "ɛɹ"),
    ("are", "ɛɹ"),
    ("ire", "aɪɹ"),
    ("ure", "jʊɹ"),
    ("ai", "eɪ"),
    ("ay", "eɪ"),
    ("au", "ɔː"),
    ("aw", "ɔː"),
    ("ea", "iː"),
    ("ee", "iː"),
    ("ei", "eɪ"),
    ("ey", "eɪ"),
    ("eu", "juː"),
    ("ew", "juː"),
    ("ie", "iː"),
    ("oa", "oʊ"),
    ("oe", "oʊ"),
    ("oi", "ɔɪ"),
    ("oy", "ɔɪ"),
    ("oo", "uː"),
    ("ou", "aʊ"),
    ("ow", "oʊ"),
    ("ph", "f"),
    ("gh", ""),
    ("ng", "ŋ"),
    ("ch", "tʃ"),
    ("sh", "ʃ"),
    ("th", "θ"),
    ("wh", "w"),
    ("qu", "kw"),
    ("ck", "k"),
    ("sch", "sk"),
    ("ss", "s"),
    ("ll", "l"),
    ("mm", "m"),
    ("nn", "n"),
    ("ff", "f"),
    ("pp", "p"),
    ("tt", "t"),
    ("zz", "z"),
    ("rr", "ɹ"),
    ("dd", "d"),
    ("bb", "b"),
    ("gg", "ɡ"),
)

_FUNCTION_WORDS = {
    "the": "ðə",
    "a": "ə",
    "an": "æn",
    "to": "tə",
    "of": "əv",
    "and": "ænd",
    "or": "ɔɹ",
    "are": "ɑɹ",
    "for": "fɔɹ",
    "was": "wəz",
    "were": "wɝ",
    "from": "fɹʌm",
    "have": "hæv",
    "has": "hæz",
    "been": "bɪn",
    "do": "du",
    "does": "dʌz",
    "your": "jɔɹ",
    "you": "ju",
    "they": "ðeɪ",
    "their": "ðɛɹ",
    "there": "ðɛɹ",
}

_TH_VOICED = ("the", "this", "that", "they", "then", "than", "there", "these", "those")

_IPA_VOWEL_ENDINGS = ("æ", "ɛ", "ɪ", "ɔ", "ʊ", "ɑ", "ɒ", "ə", "ɚ", "ɝ", "ɨ", "ʉ")

_VOWEL_PREFIXES = (
    "aɪɹ",
    "aɪ",
    "aʊ",
    "eɪ",
    "oʊ",
    "ɔɪ",
    "juː",
    "iː",
    "uː",
    "ɑː",
    "ɔː",
    "ɜː",
    "ɛɹ",
    "ɑɹ",
    "ɔɹ",
    "ɪɹ",
    "ʊɹ",
    "ə",
    "ɪ",
    "ɛ",
    "æ",
    "ʌ",
    "ʊ",
    "ɑ",
    "ɔ",
    "i",
    "u",
    "e",
    "o",
    "ɚ",
    "ɝ",
    "ɒ",
)

_SIMPLE_CONSONANTS = {
    "b": "b",
    "d": "d",
    "f": "f",
    "k": "k",
    "l": "l",
    "m": "m",
    "n": "n",
    "p": "p",
    "s": "s",
    "t": "t",
    "v": "v",
    "w": "w",
    "z": "z",
    "r": "ɹ",
    "h": "h",
    "j": "dʒ",
    "q": "k",
    "x": "ks",
}


def _last_ipa_unit_is_vowel(prev):
    if not prev:
        return False
    last = prev[-1]
    return last in "aeiouy" or last in _IPA_VOWEL_ENDINGS


def _next_vowel_index(w, start):
    for j in range(start, len(w)):
        if w[j] in _VOWELS:
            return j
    return -1


def _magic_e_lengthens(w, vowel_i):
    n = len(w)
    if vowel_i < 0 or vowel_i >= n:
        return False
    if not w or w[-1] != "e" or n < vowel_i + 3:
        return False
    j = vowel_i + 1
    if j >= n - 1:
        return False
    penult = w[-2]
    if not ("a" <= penult <= "z" and penult not in _VOWELS):
        return False
    mid = w[j : n - 1]
    if not mid:
        return False
    for c in mid:
        if c in _VOWELS:
            return False
    return len(mid) == 1


def _r_controlled(w, i):
    if i + 1 >= len(w) or w[i + 1] != "r":
        return None
    return {
        "a": "ɑɹ",
        "e": "ɛɹ",
        "i": "ɪɹ",
        "o": "ɔɹ",
        "u": "ʊɹ",
        "y": "aɪɹ",
    }.get(w[i])


def _single_consonant(c, w, i):
    if c in "cg":
        nxt = w[i + 1] if i + 1 < len(w) else ""
        soft = nxt in ("e", "i", "y")
        if c == "c":
            return "s" if soft else "k"
        return "dʒ" if soft else "ɡ"
    if c == "y":
        if i == 0 and _next_vowel_index(w, 1) >= 0:
            return "j"
        return "aɪ"
    return _SIMPLE_CONSONANTS.get(c, c)


def _vowel(w, i):
    v = w[i]
    rc = _r_controlled(w, i)
    if rc is not None:
        return rc, 2
    magic = _magic_e_lengthens(w, i)
    nxt = _next_vowel_index(w, i + 1)
    closed = False
    if nxt >= 0:
        between = w[i + 1 : nxt]
        if between:
            closed = True
            for c in between:
                if c in _VOWELS:
                    closed = False
                    break
    elif i + 1 < len(w) and w[i + 1] not in _VOWELS:
        closed = True
    if v == "a":
        return ("eɪ" if magic else "æ" if closed else "ɑː"), 1
    if v == "e":
        if magic:
            return "iː", 1
        return ("ɛ" if closed or i == len(w) - 1 else "iː"), 1
    if v == "i":
        return ("aɪ" if magic else "ɪ" if closed else "aɪ"), 1
    if v == "o":
        return ("oʊ" if magic else "ɒ" if closed else "oʊ"), 1
    if v == "u":
        return ("juː" if magic else "ʌ" if closed else "uː"), 1
    if v == "y":
        return ("ɪ" if closed else "aɪ"), 1
    return "ə", 1


def _add_primary_stress_if_missing(s):
    if not s:
        return s
    if s.startswith(PRIMARY) or s.startswith(SECONDARY):
        return s
    for pref in _VOWEL_PREFIXES:
        k = s.find(pref)
        if k >= 0:
            return s[:k] + PRIMARY + s[k:]
    return PRIMARY + s


def _grapheme_to_ipa(word):
    w = _letters(word)
    if not w:
        return ""
    fw = _FUNCTION_WORDS.get(w)
    if fw is not None:
        return fw
    parts = []
    i = 0
    n = len(w)
    while i < n:
        if w[i] == "e" and i == n - 1 and parts:
            i += 1
            continue
        matched = False
        for graph, ipa in _LITERALS:
            if not w.startswith(graph, i):
                continue
            if graph == "gh":
                if not (parts and _last_ipa_unit_is_vowel(parts[-1])):
                    parts.append("ɡ")
            elif graph == "th":
                parts.append("ð" if w in _TH_VOICED else "θ")
            else:
                parts.append(ipa)
            i += len(graph)
            matched = True
            break
        if matched:
            continue
        c = w[i]
        if c in _VOWELS:
            ipa, step = _vowel(w, i)
            parts.append(ipa)
            i += step
        elif "a" <= c <= "z":
            parts.append(_single_consonant(c, w, i))
            i += 1
        else:
            i += 1
    return "".join(parts)


def rules_word_to_ipa(word):
    fw = _FUNCTION_WORDS.get(_letters(word))
    if fw is not None:
        return fw
    return _add_primary_stress_if_missing(_grapheme_to_ipa(word))


# ---------------------------------------------------------------------------
# Text driver (g2p.cc)
# ---------------------------------------------------------------------------


def _has_digit(tok):
    for c in tok:
        if c in _ASCII_DIGITS:
            return True
    return False


def resolve_word(tok, dictionary=None, overrides=None):
    """IPA for one word token via overrides -> numbers -> dictionary -> rules."""
    key = normalize_word_key(tok)
    if overrides is not None and key:
        ipa = overrides.lookup(key)
        if ipa is not None:
            return ipa
    if _has_digit(tok):
        ipa = number_to_ipa(tok)
        if ipa is not None:
            return ipa
    if dictionary is not None and key:
        ipa = dictionary.lookup(key)
        if ipa is not None:
            return ipa
    return rules_word_to_ipa(tok)


def _is_word_char(c):
    return ("a" <= c <= "z") or ("A" <= c <= "Z") or c in _ASCII_DIGITS or c == "'"


def text_to_phones(text, dictionary=None, overrides=None):
    """Plain English text -> base-phone tokens, with " " word gaps and "." pauses."""
    out = []
    tok = []

    def flush():
        if tok:
            out.extend(tokenize_ipa(resolve_word("".join(tok), dictionary, overrides)))
            del tok[:]

    n = len(text)
    for i in range(n):
        c = text[i]
        is_tok = _is_word_char(c)
        if not is_tok and c in ".,":
            prev = tok[-1] if tok else ""
            nxt = text[i + 1] if i + 1 < n else ""
            if prev and prev in _ASCII_DIGITS and nxt and nxt in _ASCII_DIGITS:
                is_tok = True
        if is_tok:
            tok.append(c)
            continue
        flush()
        if c in ".!?":
            out.append(".")
        elif c in ",;: \t\n\r":
            if out and out[-1] != " " and out[-1] != ".":
                out.append(" ")
    flush()
    return out
