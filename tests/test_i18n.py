"""Every text key used in the code must exist in Portuguese, English and Spanish."""
import os
import re
import string

from agriprecisa import i18n

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agriprecisa")


def used_keys():
    keys = set()
    for folder, _, files in os.walk(ROOT):
        for name in files:
            if name.endswith(".py"):
                text = open(os.path.join(folder, name), encoding="utf-8").read()
                keys |= set(re.findall(r"""\btr\(\s*["']([a-z0-9_]+)["']""", text))
                keys |= set(re.findall(r"""help_key\s*=\s*["']([a-z0-9_]+)["']""", text))
    return keys


def placeholders(text):
    return {f for _, f, _, _ in string.Formatter().parse(text) if f}


def test_all_used_keys_exist():
    missing = used_keys() - set(i18n.STRINGS)
    assert not missing, f"Missing translation keys: {sorted(missing)}"


def test_all_languages_present_and_placeholders_match():
    for key, entry in i18n.STRINGS.items():
        assert set(entry) == {"pt", "en", "es"}, key
        ref = placeholders(entry["en"])
        for lang in ("pt", "es"):
            assert placeholders(entry[lang]) == ref, f"{key} [{lang}]"


def test_language_switch():
    i18n.set_language("es")
    assert i18n.tr("help") == "Ayuda"
    i18n.set_language("pt")
    assert i18n.tr("help") == "Ajuda"
    i18n.set_language("en")
    assert i18n.tr("p2_found", n=3) == "3 point layer(s) found in the area."
    assert i18n.tr("unknown_key") == "unknown_key"
