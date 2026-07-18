"""
Confidence scoring for Speeky.

Two responsibilities live here:
- ConfidenceScoreEngine: aggregates the top-line Confidence Score across sessions
  (fluency/vocabulary/pronunciation weighting), implementing the confidence-first
  philosophy that prioritizes successful communication over grammatical perfection
  (BAS-US-10 / BAS-US-11).
- ConfidenceGrammarAnalyzer: per-turn confidence-vs-grammar scoring and feedback
  (US-21 / PDF US-053 / BAS-US-11). Computes confidence_score from FluencyAnalyzer's
  delivery signals and grammar_score from GrammarCorrector's error_density.

BREAKING CHANGE: ConfidenceGrammarAnalyzer's is_high_stakes_context (bool) is replaced
by formality_tier (FormalityTier, from the shared formality.py). WEC-US-03 requires
reusing the same 3 context tiers already defined for grammar tone adjustment
(BAS-US-11) — Casual / Professional / Formal-High-Stakes — which a boolean can't
represent.
"""

import logging
from collections import Counter
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

import numpy as np

from .fluency import FluencyAnalyzer
from .grammar import GrammarCorrector
from .formality import FormalityTier, DEFAULT_TIER_WHEN_UNTAGGED

logger = logging.getLogger(__name__)


@dataclass
class ScoringWeights:
    """Configurable weights for confidence score calculation."""
    fluency: float = 50.0
    vocabulary: float = 30.0
    pronunciation: float = 20.0
    
    def __post_init__(self):
        """Validate weights sum to 100%."""
        total = self.fluency + self.vocabulary + self.pronunciation
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"Weights must sum to 100%, got {total}%")
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'fluency': self.fluency,
            'vocabulary': self.vocabulary,
            'pronunciation': self.pronunciation
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ScoringWeights':
        """Create from dictionary."""
        return cls(
            fluency=data.get('fluency', 50.0),
            vocabulary=data.get('vocabulary', 30.0),
            pronunciation=data.get('pronunciation', 20.0)
        )


@dataclass
class WeightChangeLog:
    """Audit log for weight configuration changes."""
    timestamp: datetime
    admin_id: str
    previous_weights: ScoringWeights
    new_weights: ScoringWeights
    reason: str = ""


@dataclass
class SessionScore:
    """Individual session score data."""
    timestamp: datetime
    fluency_score: float
    vocabulary_score: float
    pronunciation_score: Optional[float] = None
    is_text_only: bool = False
    is_complete: bool = True
    is_outlier: bool = False
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'fluency_score': self.fluency_score,
            'vocabulary_score': self.vocabulary_score,
            'pronunciation_score': self.pronunciation_score,
            'is_text_only': self.is_text_only,
            'is_complete': self.is_complete,
            'is_outlier': self.is_outlier
        }


class ConfidenceScoreEngine:
    """
    Confidence score calculation and aggregation engine.
    
    Implements the confidence-first philosophy where successful communication
    is prioritized over grammatical perfection.
    """
    
    def __init__(self, initial_weights: Optional[ScoringWeights] = None):
        """
        Initialize the confidence score engine.
        
        Args:
            initial_weights: Initial scoring weights (defaults to 50/30/20)
        """
        self.weights = initial_weights or ScoringWeights()
        self.weight_change_log: List[WeightChangeLog] = []
        self.session_history: List[SessionScore] = []
        self.current_confidence_score: float = 0.0
        
        logger.info(f"Confidence Score Engine initialized with weights: {self.weights.to_dict()}")
    
    def update_weights(self, new_weights: ScoringWeights, admin_id: str, reason: str = ""):
        """
        Update scoring weights with audit logging.
        
        Args:
            new_weights: New weight configuration
            admin_id: ID of admin making the change
            reason: Reason for the change
        """
        # Validate new weights
        try:
            ScoringWeights(**new_weights.to_dict())
        except ValueError as e:
            logger.error(f"Invalid weights: {e}")
            raise
        
        # Log the change
        change_log = WeightChangeLog(
            timestamp=datetime.now(),
            admin_id=admin_id,
            previous_weights=self.weights,
            new_weights=new_weights,
            reason=reason
        )
        self.weight_change_log.append(change_log)
        
        # Apply new weights
        self.weights = new_weights
        logger.info(f"Weights updated by {admin_id}: {self.weights.to_dict()}")
    
    def calculate_session_confidence(self, session_score: SessionScore) -> float:
        """
        Calculate confidence score for a single session.
        
        Args:
            session_score: Session score data
            
        Returns:
            Calculated confidence score (0-100)
        """
        if not session_score.is_complete:
            logger.warning("Attempting to calculate confidence for incomplete session")
            return 0.0
        
        if session_score.is_outlier:
            logger.info("Skipping outlier session in confidence calculation")
            return 0.0
        
        # Adjust weights for text-only sessions
        if session_score.is_text_only or session_score.pronunciation_score is None:
            # Normalize fluency and vocabulary to 100%
            total_weight = self.weights.fluency + self.weights.vocabulary
            fluency_weight = (self.weights.fluency / total_weight) * 100
            vocab_weight = (self.weights.vocabulary / total_weight) * 100
            
            confidence = (
                (session_score.fluency_score * fluency_weight / 100) +
                (session_score.vocabulary_score * vocab_weight / 100)
            )
        else:
            # Standard calculation with all three metrics
            confidence = (
                (session_score.fluency_score * self.weights.fluency / 100) +
                (session_score.vocabulary_score * self.weights.vocabulary / 100) +
                (session_score.pronunciation_score * self.weights.pronunciation / 100)
            )
        
        return round(confidence, 2)
    
    def detect_outlier(self, session_score: SessionScore, variance_threshold: float = 50.0) -> bool:
        """
        Detect if a session score is an statistical outlier.
        
        Args:
            session_score: Session score to check
            variance_threshold: Percentage variance threshold for outlier detection
            
        Returns:
            True if session is an outlier
        """
        if len(self.session_history) < 3:
            return False  # Need baseline data
        
        # Calculate average of recent complete sessions
        recent_scores = [
            s for s in self.session_history[-10:] 
            if s.is_complete and not s.is_outlier
        ]
        
        if not recent_scores:
            return False
        
        avg_fluency = sum(s.fluency_score for s in recent_scores) / len(recent_scores)
        avg_vocab = sum(s.vocabulary_score for s in recent_scores) / len(recent_scores)
        
        # Check if current session deviates significantly
        fluency_variance = abs(session_score.fluency_score - avg_fluency) / avg_fluency * 100 if avg_fluency else 0.0
        vocab_variance = abs(session_score.vocabulary_score - avg_vocab) / avg_vocab * 100 if avg_vocab else 0.0
        
        is_outlier = (fluency_variance > variance_threshold or vocab_variance > variance_threshold)
        
        if is_outlier:
            logger.warning(f"Outlier detected: fluency variance {fluency_variance:.1f}%, vocab variance {vocab_variance:.1f}%")
        
        return is_outlier
    
    def add_session_score(self, session_score: SessionScore):
        """
        Add a session score and update aggregate confidence score.
        
        Args:
            session_score: Session score data to add
        """
        # Detect and flag outliers
        session_score.is_outlier = self.detect_outlier(session_score)
        
        # Add to history
        self.session_history.append(session_score)
        
        # Recalculate aggregate confidence score
        self._recalculate_aggregate_confidence()
        
        logger.info(f"Session score added. New confidence score: {self.current_confidence_score}")
    
    def _recalculate_aggregate_confidence(self):
        """
        Recalculate the aggregate confidence score from session history.
        
        Uses weighted average with logarithmic cap to prevent infinite growth.
        """
        complete_sessions = [
            s for s in self.session_history 
            if s.is_complete and not s.is_outlier
        ]
        
        if not complete_sessions:
            self.current_confidence_score = 0.0
            return
        
        # Calculate weighted average of session confidence scores
        session_confidences = [
            self.calculate_session_confidence(s) 
            for s in complete_sessions
        ]
        
        # Apply logarithmic cap for long-term users
        if len(session_confidences) > 100:
            # Use logarithmic scaling to prevent score inflation
            import math
            scaling_factor = math.log(100) / math.log(len(session_confidences))
            avg_confidence = sum(session_confidences) / len(session_confidences)
            self.current_confidence_score = min(100.0, avg_confidence * scaling_factor)
        else:
            self.current_confidence_score = sum(session_confidences) / len(session_confidences)
        
        self.current_confidence_score = round(self.current_confidence_score, 2)
    
    def get_confidence_score(self) -> float:
        """Get current aggregate confidence score."""
        return self.current_confidence_score
    
    def get_confidence_breakdown(self) -> Dict:
        """
        Get plain-language breakdown of confidence score.
        
        Returns:
            Dictionary with score components and explanation
        """
        recent_sessions = self.session_history[-10:] if self.session_history else []
        
        if not recent_sessions:
            return {
                'current_score': 0.0,
                'explanation': 'Complete the Initial Communication Assessment to establish your baseline confidence score.',
                'components': {
                    'fluency': {'weight': self.weights.fluency, 'recent_average': 0},
                    'vocabulary': {'weight': self.weights.vocabulary, 'recent_average': 0},
                    'pronunciation': {'weight': self.weights.pronunciation, 'recent_average': 0}
                }
            }
        
        complete_recent = [s for s in recent_sessions if s.is_complete and not s.is_outlier]
        
        avg_fluency = sum(s.fluency_score for s in complete_recent) / len(complete_recent) if complete_recent else 0
        avg_vocab = sum(s.vocabulary_score for s in complete_recent) / len(complete_recent) if complete_recent else 0
        pron_scores = [s.pronunciation_score for s in complete_recent if s.pronunciation_score is not None]
        avg_pron = sum(pron_scores) / len(pron_scores) if pron_scores else None
        
        # Generate explanation
        if self.current_confidence_score >= 80:
            level = "high"
        elif self.current_confidence_score >= 60:
            level = "moderate"
        else:
            level = "developing"
        
        explanation = (
            f"Your confidence score reflects your {level} ability to communicate effectively. "
            f"Based on your recent sessions, you're performing {'strongly' if level == 'high' else 'well' if level == 'moderate' else 'and building foundational skills'}. "
            f"Keep practicing to improve your fluency and vocabulary usage."
        )
        
        return {
            'current_score': self.current_confidence_score,
            'explanation': explanation,
            'components': {
                'fluency': {
                    'weight': self.weights.fluency,
                    'recent_average': round(avg_fluency, 1),
                    'description': 'Flow and naturalness of speech'
                },
                'vocabulary': {
                    'weight': self.weights.vocabulary,
                    'recent_average': round(avg_vocab, 1),
                    'description': 'Word choice and variety'
                },
                'pronunciation': {
                    'weight': self.weights.pronunciation,
                    'recent_average': round(avg_pron, 1) if avg_pron is not None else None,
                    'description': 'Clarity and accuracy of pronunciation'
                }
            }
        }
    
    def get_weight_history(self) -> List[Dict]:
        """Get audit log of weight changes."""
        return [
            {
                'timestamp': log.timestamp.isoformat(),
                'admin_id': log.admin_id,
                'previous_weights': log.previous_weights.to_dict(),
                'new_weights': log.new_weights.to_dict(),
                'reason': log.reason
            }
            for log in self.weight_change_log
        ]
    
    def export_config(self) -> Dict:
        """Export current configuration for backup/analysis."""
        return {
            'current_weights': self.weights.to_dict(),
            'current_confidence_score': self.current_confidence_score,
            'session_count': len(self.session_history),
            'weight_change_count': len(self.weight_change_log),
            'weight_history': self.get_weight_history()
        }
    
    def import_config(self, config: Dict):
        """Import configuration from backup."""
        if 'current_weights' in config:
            self.weights = ScoringWeights.from_dict(config['current_weights'])
        
        if 'weight_history' in config:
            self.weight_change_log = [
                WeightChangeLog(
                    timestamp=datetime.fromisoformat(log['timestamp']),
                    admin_id=log['admin_id'],
                    previous_weights=ScoringWeights.from_dict(log['previous_weights']),
                    new_weights=ScoringWeights.from_dict(log['new_weights']),
                    reason=log.get('reason', '')
                )
                for log in config['weight_history']
            ]

        logger.info("Configuration imported successfully")


class ConfidenceGrammarAnalyzer:
    """
    Confidence-vs-grammar scoring and feedback (US-21 / PDF US-053 / BAS-US-11).

    Reuses FluencyAnalyzer output (speech_rate, pause_count, mean_pause_duration,
    filled_pauses) and GrammarCorrector output (error_density, optional error_tags).
    Does not re-derive any audio/text signal itself. Separate from ConfidenceScoreEngine
    above: that class tracks the aggregate top-line Confidence Score across sessions,
    while this one scores a single turn's delivery vs. grammar to decide the feedback
    tier (BAS-US-11's "confidence over grammar" philosophy). Grammar deliberately does
    NOT feed the aggregate Confidence Score.
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
        fluency_details: Dict[str, Any],
        grammar_result: Dict[str, Any],
        formality_tier: FormalityTier = DEFAULT_TIER_WHEN_UNTAGGED,
        error_history: Optional[List[str]] = None,
        current_error_tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Score confidence vs. grammar and produce BAS-US-11 feedback.

        Args:
            fluency_details: Output of FluencyAnalyzer.analyze_fluency().
            grammar_result: Output of GrammarCorrector.correct_text().
            formality_tier: FormalityTier (shared with WEC-US-03). Defaults
                to Professional per that story's own E-01 resolution.
            error_history: Error tags accumulated so far this session.
            current_error_tags: Error tag(s) detected this turn.

        Returns:
            Dict with confidence_score, grammar_score, primary_metric
            (always "confidence_score" per BAS-US-11 acceptance criteria),
            grammar_tier, needs_clarification, feedback_hint, repeat_offender_tip
            (None unless E-03 threshold is hit this call), error_history (updated,
            for the caller to persist), and formality_tier.
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

    def _calculate_confidence_score(self, fluency_details: Dict[str, Any]) -> float:
        """
        Derive confidence_score (0-100) from audio delivery signals only.

        Reuses the exact point bands FluencyAnalyzer._calculate_overall_score
        already uses for speech_rate (40 pts), pause frequency (20 pts), and
        filled_pauses (20 pts) — no new weights invented. FluencyAnalyzer's
        4th component, lexical_diversity (20 pts), is excluded here per the
        BAS-US-11 design decision: confidence must come from delivery signals,
        not vocabulary/text richness. The remaining 80-point raw total is
        rescaled to 0-100.
        """
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
