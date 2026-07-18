"""
Real-Time Inline Grammar Correction Toggle (US-27 / PDF GAP-04).

Reuses GrammarCorrector for the actual correction (and, for the new
audio-input path, AutomaticSpeechRecognition for transcription). This
module only adds the "chip" layer: opt-in gating, picking the single
highest-impact error, suppressing false positives, and voice-mode
suppression. No new grammar-checking or ASR logic is implemented here.

Two entry points:
  - get_correction_chip(original_text, ...)        -> original path, takes
    text directly (unchanged core logic from the previous version).
  - get_correction_chip_from_audio(audio, sample_rate, ...) -> NEW: takes
    raw audio, transcribes via AutomaticSpeechRecognition, then calls
    get_correction_chip(). No logic duplicated.
"""

import difflib
import logging
from typing import Callable, Dict, List, Optional

import numpy as np

from .asr import AutomaticSpeechRecognition
from .grammar import GrammarCorrector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InlineCorrectionChipService:
    """
    Produces a single inline correction chip from GrammarCorrector's output,
    gated by the user's toggle setting and current mode (voice vs. text).
    """

    def __init__(
        self,
        grammar_corrector: Optional[GrammarCorrector] = None,
        asr: Optional[AutomaticSpeechRecognition] = None,
        impact_key: Optional[Callable[[Dict[str, str]], int]] = None,
    ):
        """
        Args:
            grammar_corrector: Reuse an existing GrammarCorrector instance
                (e.g. the one pipeline.py already loads) instead of
                constructing a second one. Falls back to a new instance
                only if none is passed.
            asr: Reuse an existing AutomaticSpeechRecognition instance.
                Only needed for get_correction_chip_from_audio(); built
                lazily if not passed and that path is used.
            impact_key: Function scoring a candidate chip's "impact" to
                pick the single highest one (E-02). Defaults to combined
                character length of the change (see DEFAULT_IMPACT_KEY) —
                previously a hardcoded lambda inside the method, now an
                overridable parameter with the same default behavior.
        """
        self.grammar_corrector = grammar_corrector or GrammarCorrector()
        self.asr = asr
        self.impact_key = impact_key or self.DEFAULT_IMPACT_KEY

    # "Highest-impact" is NOT defined anywhere in the spec — it only says
    # "single highest-impact error" without a metric. This uses combined
    # character length of the change as a stand-in (bigger rewrites
    # assumed more significant than a 1-letter typo).
    # TODO: replace with a real severity signal (e.g. spaCy POS-tag
    # category — verb tense vs. article) once one exists.
    @staticmethod
    def DEFAULT_IMPACT_KEY(candidate: Dict[str, str]) -> int:
        return len(candidate["from"]) + len(candidate["to"])

    def get_correction_chip_from_audio(
        self,
        audio: np.ndarray,
        sample_rate: int,
        show_corrections_enabled: bool = False,
        is_voice_mode: bool = False,
        use_llm: bool = True,
    ) -> Dict[str, any]:
        """
        Audio-input entry point. Transcribes via AutomaticSpeechRecognition,
        then delegates to get_correction_chip() — no chip logic duplicated.

        Args:
            audio: Raw audio samples.
            sample_rate: Sample rate of the audio.
            show_corrections_enabled, is_voice_mode, use_llm: see
                get_correction_chip().

        Returns:
            Same shape as get_correction_chip(), plus 'transcript' (the
            recognized text, since callers no longer supply it directly).

        Raises:
            RuntimeError: propagated if ASR fails to load/transcribe —
                surfaced rather than silently faking a transcript, since
                there is no safe placeholder for recognized speech.
        """
        if self.asr is None:
            logger.info("No ASR provided — constructing AutomaticSpeechRecognition lazily.")
            self.asr = AutomaticSpeechRecognition()

        transcription = self.asr.transcribe(audio, sample_rate)
        transcript = transcription["text"]

        result = self.get_correction_chip(
            original_text=transcript,
            show_corrections_enabled=show_corrections_enabled,
            is_voice_mode=is_voice_mode,
            use_llm=use_llm,
        )
        result["transcript"] = transcript
        return result

    def get_correction_chip(
        self,
        original_text: str,
        show_corrections_enabled: bool = False,
        is_voice_mode: bool = False,
        use_llm: bool = True,
    ) -> Dict[str, any]:
        """
        Run grammar correction and return a single chip, or none, per US-27.

        Args:
            original_text: The learner's just-submitted message.
            show_corrections_enabled: The user's session-settings toggle
                for "Show corrections during chat". OFF by default per
                acceptance criteria — caller must explicitly pass True.
            is_voice_mode: True if the user is in voice mode. Per E-03,
                chips are suppressed in voice mode (corrections still
                computed and returned for the end-of-session summary).
            use_llm: Passed through to GrammarCorrector.correct_text().

        Returns:
            Dict with:
                - grammar_result: full GrammarCorrector output (always
                  present, used for the end-of-session summary regardless
                  of toggle state)
                - chip: {"from": str, "to": str} for the single
                  highest-impact correction, or None if disabled, no
                  error found, voice mode, or a regional-variant
                  false positive
                - suppressed_reason: None, or one of "toggle_off",
                  "voice_mode", "no_correction_needed"
        """
        grammar_result = self.grammar_corrector.correct_text(original_text, use_llm=use_llm)

        if not show_corrections_enabled:
            return {"grammar_result": grammar_result, "chip": None, "suppressed_reason": "toggle_off"}

        corrected_text = grammar_result.get("corrected", original_text)

        if original_text.strip() == corrected_text.strip():
            # E-01 (regional variant, e.g. valid British spelling): since
            # GrammarCorrector targets British English, a correct British
            # spelling produces no diff and no false-positive chip.
            # CAVEAT: no per-user English-variant setting exists in
            # grammar.py — it always targets British English. If a
            # learner's variant is American, this will not behave like
            # the spec's E-01. Flagged as a gap, not fixed here.
            return {
                "grammar_result": grammar_result,
                "chip": None,
                "suppressed_reason": "no_correction_needed",
            }

        chip = self._pick_highest_impact_chip(original_text, corrected_text)

        if is_voice_mode:
            # E-03: suppress inline rendering, keep grammar_result for summary.
            return {"grammar_result": grammar_result, "chip": None, "suppressed_reason": "voice_mode"}

        return {"grammar_result": grammar_result, "chip": chip, "suppressed_reason": None}

    def _pick_highest_impact_chip(self, original: str, corrected: str) -> Optional[Dict[str, str]]:
        """
        Diff original vs. corrected text word-by-word and pick ONE chip
        using self.impact_key (E-02: cap to single highest-impact error).
        """
        original_words = original.split()
        corrected_words = corrected.split()

        matcher = difflib.SequenceMatcher(a=original_words, b=corrected_words)
        candidates: List[Dict[str, str]] = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            from_phrase = " ".join(original_words[i1:i2])
            to_phrase = " ".join(corrected_words[j1:j2])
            candidates.append({"from": from_phrase, "to": to_phrase})

        if not candidates:
            return None

        return max(candidates, key=self.impact_key)