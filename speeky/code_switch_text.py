"""
Text-Mode Code-Switch Detection (WEC-US-01 / PDF GAP-01).

FINAL APPROACH — no Ollama, no local LLM, no hardcoded lexicon:
  - spaCy: NER proper-noun exclusion (E-01) — unchanged.
  - langdetect: used ONLY for whole-message language ID (E-05). This is
    langdetect's actual designed use case (sentence-level) and testing
    confirmed it works well here.
  - deep-translator (GoogleTranslator): does BOTH detection AND
    translation for word-level flagging, via round-trip diffing —
    translate the token to English; if the result differs from the
    original (case-insensitively), the token was non-English and the
    translation IS the suggestion. langdetect was tested and PROVEN
    unreliable on single words (see test results: "send"->Danish,
    "week"->Afrikaans, etc.) — this replaces that broken word-level path.

Add to requirements.txt: langdetect, deep-translator

REAL LIMITATIONS, stated plainly:
  - No per-word source-LANGUAGE identification exists in this approach
    (deep-translator's free/keyless mode returns translated text only,
    not a detected source language). This means WEC-US-02 cannot truly
    scope detection BY the learner's selected language(s) — see that
    module's own docstring for how it's handled instead.
  - Round-trip diffing can FALSE-POSITIVE on legitimate English input if
    Google's translator paraphrases it instead of returning it unchanged
    (e.g. returns a synonym). No dictionary exists to cross-check this
    against anymore. Mitigated only by requiring an exact
    case-insensitive match to count as "already English" — not a full fix.
  - deep-translator needs live network access (Google's endpoint,
    unofficial, no key/SLA). No offline mode. Network failure surfaces
    per-token in translation_errors, not silently swallowed.
  - Neither library was executable in the environment this was written
    in (no network access) — written against documented APIs, verified
    only via labeled stand-in stubs for control-flow, not real accuracy.
"""

import logging
from typing import Callable, Dict, List, Optional

from langdetect import DetectorFactory, detect_langs
from langdetect.lang_detect_exception import LangDetectException
from deep_translator import GoogleTranslator
from deep_translator.exceptions import BaseError as DeepTranslatorError

DetectorFactory.seed = 0  # reproducible sentence-level langdetect results

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Below this token length, round-trip translation is treated as too
# unreliable to act on (short strings are noisy for translation systems
# too, not just langdetect). Not spec-defined — practical guard.
MIN_TOKEN_LENGTH_FOR_DETECTION = 4

# E-05: confidence langdetect must report for the WHOLE message before
# treating it as entirely non-English. Not spec-defined — judgment call.
FULL_SENTENCE_CONFIDENCE_THRESHOLD = 0.70


class TextCodeSwitchDetector:
    """
    Detects code-switched words in typed text via round-trip translation
    diffing (word level) and langdetect (sentence level), with spaCy NER
    excluding proper nouns.
    """

    def __init__(
        self,
        nlp=None,
        word_list_logger: Optional[Callable[[str, str], None]] = None,
    ):
        """
        Args:
            nlp: loaded spaCy Language pipeline (reuse the project's
                existing instance) for NER proper-noun exclusion. If
                None, exclusion is skipped with a logged warning.
            word_list_logger: callback(word, source) for wiring to the
                real Code-Switch Word List (CSC-US-02, not built).
        """
        self.nlp = nlp
        self.word_list_logger = word_list_logger

        if self.nlp is None:
            logger.warning(
                "No spaCy pipeline provided — NER proper-noun exclusion (E-01) will be skipped."
            )

    def detect(self, text: str, session_context: Optional[List[str]] = None) -> Dict[str, any]:
        """
        Scan typed text for code-switched words.

        Returns:
            Dict with:
                - flagged: list of {"token", "suggestion", "source": "text"}
                  (no "detected_language" — not available with this
                  approach, see module docstring)
                - full_sentence_local_language: bool (E-05)
                - prompt: str or None
                - translation_errors: tokens where translation failed
                  (network/API error) — surfaced, not silently dropped
        """
        empty = {
            "flagged": [],
            "full_sentence_local_language": False,
            "prompt": None,
            "translation_errors": [],
        }

        if not text or not text.strip():
            return empty

        tokens = text.split()

        # E-07: single very short message — too unreliable to judge alone.
        if len(tokens) == 1 and len(tokens[0]) <= MIN_TOKEN_LENGTH_FOR_DETECTION:
            logger.info("Single short token '%s' — deferring.", tokens[0])
            return empty

        # BUG FOUND IN TESTING: with the original len(tokens) >= 3 guard,
        # a 3-word message like "send it jaldi" (only ONE non-English
        # word) got misclassified as a full local-language sentence —
        # langdetect is unreliable on short whole-messages too, not just
        # single words. Raised to >= 5 based on that failure; the
        # working full-sentence test case had 8 words, well above this.
        # Still a heuristic guess, not a guaranteed fix.
        if len(tokens) >= 5 and self._looks_like_full_local_sentence(text):
            return {
                "flagged": [],
                "full_sentence_local_language": True,
                "prompt": "It looks like that whole message is in another language. "
                "Could you try writing the full sentence in English?",
                "translation_errors": [],
            }

        proper_nouns = self._get_proper_nouns(text)

        flagged = []
        translation_errors = []

        for raw_token in tokens:
            normalized = self._normalize_token(raw_token)
            if not normalized or len(normalized) < MIN_TOKEN_LENGTH_FOR_DETECTION:
                continue
            if normalized.lower() in proper_nouns:
                continue  # E-01

            suggestion, error = self._translate_and_diff(normalized)
            if error:
                translation_errors.append(raw_token)
                continue
            if suggestion is None:
                continue  # translation matched original -> already English

            flagged.append({"token": raw_token, "suggestion": suggestion, "source": "text"})
            if self.word_list_logger:
                self.word_list_logger(normalized, "text")

        return {
            "flagged": flagged,
            "full_sentence_local_language": False,
            "prompt": None,
            "translation_errors": translation_errors,
        }

    def _normalize_token(self, token: str) -> str:
        """E-06: strip emoji/numbers/decorations before translation."""
        return "".join(ch for ch in token if ch.isalpha())

    def _translate_and_diff(self, token: str) -> (Optional[str], bool):
        """
        Round-trip diff: translate token to English via GoogleTranslator.
        If result differs (case-insensitive) from the original, the
        token was non-English and the translation is the suggestion.

        Returns:
            (suggestion_or_None, had_error). suggestion is None if the
            token was already English (no diff) OR if had_error is True.
        """
        try:
            translated = GoogleTranslator(source="auto", target="en").translate(token)
        except DeepTranslatorError as e:
            logger.error("deep-translator failed on '%s': %s", token, e)
            return None, True
        except Exception as e:
            logger.error("Unexpected error translating '%s': %s", token, e)
            return None, True

        if not translated:
            return None, True

        if translated.strip().lower() == token.strip().lower():
            return None, False  # already English

        return translated, False

    def _looks_like_full_local_sentence(self, text: str) -> bool:
        """E-05: langdetect on the WHOLE message — its actual reliable use case."""
        try:
            candidates = detect_langs(text)
        except LangDetectException:
            return False
        if not candidates:
            return False
        top = candidates[0]
        return top.lang != "en" and top.prob >= FULL_SENTENCE_CONFIDENCE_THRESHOLD

    def _get_proper_nouns(self, text: str) -> set:
        """E-01: proper-noun exclusion via spaCy NER — unchanged."""
        if self.nlp is None:
            return set()
        try:
            doc = self.nlp(text)
            return {
                token.text.lower()
                for ent in doc.ents
                if ent.label_ in {"PERSON", "GPE", "LOC", "ORG", "NORP"}
                for token in ent
            }
        except Exception as e:
            logger.error("NER proper-noun check failed: %s", e)
            return set()