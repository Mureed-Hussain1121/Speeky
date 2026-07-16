"""
Confidence vs. Grammar module (US-21 / PDF US-053 / BAS-US-11).

BREAKING CHANGE from the previous version: is_high_stakes_context (bool)
is replaced by formality_tier (FormalityTier, from the new shared
formality.py). Reason: WEC-US-03's acceptance criteria requires reusing
"the same context tiers already defined for grammar tone adjustment
(BAS-US-11)" — a boolean can't represent the 3-tier system WEC-US-03
needs (Casual / Professional / Formal-High-Stakes), so this had to
become the real shared tier system rather than staying a 2-way flag.

Computes confidence_score from FluencyAnalyzer's audio delivery signals
and grammar_score from GrammarCorrector's error_density, then generates
the confidence-first feedback strategy defined by US-21.
"""

import logging
from collections import Counter
from typing import Callable, Dict, List, Optional

import numpy as np

from .fluency import FluencyAnalyzer
from .grammar import GrammarCorrector
from .formality import FormalityTier, DEFAULT_TIER_WHEN_UNTAGGED

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConfidenceGrammarAnalyzer:
    """
    Confidence-vs-grammar scoring and feedback for US-21/BAS-US-11.
    """

    # Grammar-score threshold per formality tier is NOT specified anywhere
    # in the PDF spec (US-053 gives no numeric cutoffs, and none of the
    # three-tier values are given either). All fully overridable via the
    # constructor — nothing here is a fixed/hardcoded requirement.
    DEFAULT_GRAMMAR_THRESHOLDS = {
        FormalityTier.CASUAL: 50.0,
        FormalityTier.PROFESSIONAL: 60.0,
        FormalityTier.FORMAL_HIGH_STAKES: 75.0,
    }

    DEFAULT_ERROR_TAG_TIPS = {
        "past_tense": "Review Past Tense Verbs",
        "subject_verb_agreement": "Review Subject-Verb Agreement",
        "article_usage": "Review Article Usage (a/an/the)",
        "preposition": "Review Preposition Choice",
        "plural_form": "Review Plural Noun Forms",
    }

    def __init__(
        self,
        fluency_analyzer: Optional[FluencyAnalyzer] = None,
        grammar_corrector: Optional[GrammarCorrector] = None,
        unintelligible_grammar_threshold: float = 20.0,
        grammar_thresholds: Optional[Dict[FormalityTier, float]] = None,
        repeat_offender_threshold: int = 10,
        error_tag_tips: Optional[Dict[str, str]] = None,
    ):
        """
        Args:
            fluency_analyzer: Reuse an existing FluencyAnalyzer instance.
                Only needed for analyze_from_audio(); lazily constructed
                if not passed.
            grammar_corrector: Same, for GrammarCorrector.
            unintelligible_grammar_threshold: Below this grammar_score,
                treat input as unintelligible (E-01). Not spec-defined —
                previous hardcoded value (20.0), now overridable.
            grammar_thresholds: Maps each FormalityTier to its grammar
                threshold. Defaults to DEFAULT_GRAMMAR_THRESHOLDS above,
                fully overridable/extendable.
            repeat_offender_threshold: Occurrences of the same error tag
                before E-03's tip fires (spec's own example: 10).
            error_tag_tips: Maps an error tag to its actionable tip.
                Defaults to DEFAULT_ERROR_TAG_TIPS, fully overridable.
        """
        self.fluency_analyzer = fluency_analyzer
        self.grammar_corrector = grammar_corrector

        self.unintelligible_grammar_threshold = unintelligible_grammar_threshold
        self.grammar_thresholds = grammar_thresholds or dict(self.DEFAULT_GRAMMAR_THRESHOLDS)
        self.repeat_offender_threshold = repeat_offender_threshold
        self.error_tag_tips = error_tag_tips or dict(self.DEFAULT_ERROR_TAG_TIPS)

    def analyze_from_audio(
        self,
        audio: np.ndarray,
        sample_rate: int,
        word_timings: List[Dict[str, any]],
        transcript: str,
        formality_tier: FormalityTier = DEFAULT_TIER_WHEN_UNTAGGED,
        error_history: Optional[List[str]] = None,
        current_error_tags: Optional[List[str]] = None,
        use_llm: bool = True,
    ) -> Dict[str, any]:
        """Audio-input entry point. See analyze() for the scoring logic itself."""
        if self.fluency_analyzer is None:
            logger.info("No FluencyAnalyzer provided — constructing one lazily.")
            self.fluency_analyzer = FluencyAnalyzer()
        if self.grammar_corrector is None:
            logger.info("No GrammarCorrector provided — constructing one lazily.")
            self.grammar_corrector = GrammarCorrector(use_llm=use_llm)

        fluency_details = self.fluency_analyzer.analyze_fluency(
            audio, sample_rate, word_timings, transcript
        )
        grammar_result = self.grammar_corrector.correct_text(transcript, use_llm=use_llm)

        return self.analyze(
            fluency_details,
            grammar_result,
            formality_tier=formality_tier,
            error_history=error_history,
            current_error_tags=current_error_tags,
        )

    def analyze(
        self,
        fluency_details: Dict[str, any],
        grammar_result: Dict[str, any],
        formality_tier: FormalityTier = DEFAULT_TIER_WHEN_UNTAGGED,
        error_history: Optional[List[str]] = None,
        current_error_tags: Optional[List[str]] = None,
    ) -> Dict[str, any]:
        """
        Score confidence vs. grammar and produce US-21 feedback.

        Args:
            fluency_details: Output of FluencyAnalyzer.analyze_fluency().
            grammar_result: Output of GrammarCorrector.correct_text().
            formality_tier: FormalityTier (shared with WEC-US-03). Defaults
                to Professional per that story's own E-01 resolution.
            error_history: Error tags accumulated so far this session.
            current_error_tags: Error tag(s) detected this turn.

        Returns:
            Dict with confidence_score, grammar_score, primary_metric
            (always "confidence_score"), grammar_tier, needs_clarification,
            feedback_hint, repeat_offender_tip, error_history, formality_tier.
        """
        confidence_score = self._calculate_confidence_score(fluency_details or {})
        error_density = (grammar_result or {}).get("error_density", 0.0)
        grammar_score = round(100.0 * (1.0 - min(1.0, max(0.0, error_density))), 1)

        grammar_threshold = self.grammar_thresholds.get(
            formality_tier, self.DEFAULT_GRAMMAR_THRESHOLDS[FormalityTier.PROFESSIONAL]
        )

        if grammar_score < self.unintelligible_grammar_threshold:
            grammar_tier = "unintelligible"
            needs_clarification = True
            feedback_hint = "I didn't quite understand that. Are you trying to say...?"
        else:
            needs_clarification = False
            grammar_tier = "minor_polish" if grammar_score >= grammar_threshold else "needs_attention"
            feedback_hint = self._build_feedback_hint(grammar_tier, formality_tier)

        updated_history = list(error_history) if error_history else []
        if current_error_tags:
            updated_history.extend(current_error_tags)

        repeat_offender_tip = self._detect_repeat_offender(updated_history)

        result = {
            "confidence_score": confidence_score,
            "grammar_score": grammar_score,
            "primary_metric": "confidence_score",
            "grammar_tier": grammar_tier,
            "needs_clarification": needs_clarification,
            "feedback_hint": feedback_hint,
            "repeat_offender_tip": repeat_offender_tip,
            "error_history": updated_history,
            "formality_tier": formality_tier,
        }

        logger.info(
            "Confidence/grammar: confidence=%.1f grammar=%.1f tier=%s formality=%s",
            confidence_score,
            grammar_score,
            grammar_tier,
            formality_tier,
        )
        return result

    def _detect_repeat_offender(self, error_history: List[str]) -> Optional[str]:
        if not error_history:
            return None
        counts = Counter(error_history)
        tag, count = counts.most_common(1)[0]
        if count < self.repeat_offender_threshold:
            return None
        return self.error_tag_tips.get(tag, f"Review {tag.replace('_', ' ').title()}")

    def _calculate_confidence_score(self, fluency_details: Dict[str, any]) -> float:
        """Reuses FluencyAnalyzer's own speech_rate/pause/filled_pause point bands (unchanged from prior version)."""
        if not fluency_details:
            return 0.0

        raw = 0.0
        speech_rate = fluency_details.get("speech_rate", 0.0)
        if 2.0 <= speech_rate <= 4.0:
            raw += 40.0
        elif 1.5 <= speech_rate <= 5.0:
            raw += 30.0
        elif speech_rate > 0:
            raw += 20.0

        pause_count = fluency_details.get("pause_count", 0)
        if pause_count == 0:
            raw += 20.0
        elif pause_count <= 2:
            raw += 15.0
        elif pause_count <= 5:
            raw += 10.0
        else:
            raw += 5.0

        filled_pauses = fluency_details.get("filled_pauses", 0)
        if filled_pauses == 0:
            raw += 20.0
        elif filled_pauses <= 1:
            raw += 15.0
        elif filled_pauses <= 3:
            raw += 10.0
        else:
            raw += 5.0

        return round(min(100.0, max(0.0, raw / 80.0 * 100.0)), 1)

    def _build_feedback_hint(self, grammar_tier: str, formality_tier: FormalityTier) -> str:
        if grammar_tier == "minor_polish":
            return "Your message came through clearly. Grammar is solid too — keep it up."
        hint = "Your message came through clearly, with a few grammar points as minor polish."
        if formality_tier == FormalityTier.FORMAL_HIGH_STAKES:
            hint += " In this high-stakes context, tighten these up before sending."
        return hint
