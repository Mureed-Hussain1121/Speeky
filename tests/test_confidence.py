"""Tests for the ConfidenceGrammarAnalyzer module (US-21)."""

import unittest

from speeky.confidence import ConfidenceGrammarAnalyzer


class TestConfidenceGrammarAnalyzer(unittest.TestCase):
    """Acceptance tests for confidence vs. grammar scoring."""

    def setUp(self):
        self.analyzer = ConfidenceGrammarAnalyzer()

    def _fluency(self, speech_rate=3.0, pause_count=0, filled_pauses=0):
        return {
            "speech_rate": speech_rate,
            "pause_count": pause_count,
            "filled_pauses": filled_pauses,
        }

    def _grammar(self, error_density=0.0):
        return {"error_density": error_density}

    def test_confident_and_accurate(self):
        result = self.analyzer.analyze(
            "I have led three projects and delivered them on time.",
            self._fluency(speech_rate=3.0, pause_count=0, filled_pauses=0),
            self._grammar(error_density=0.0),
        )
        self.assertGreaterEqual(result["confidence_score"], 70.0)
        self.assertGreaterEqual(result["grammar_score"], 70.0)
        self.assertEqual(result["label"], "Confident and Accurate")
        self.assertEqual(result["hedges_found"], [])
        self.assertEqual(result["self_corrections_found"], [])

    def test_confident_but_needs_grammar_work(self):
        result = self.analyzer.analyze(
            "I have led three projects and delivered them on time.",
            self._fluency(speech_rate=3.0, pause_count=0, filled_pauses=0),
            self._grammar(error_density=0.5),
        )
        self.assertGreaterEqual(result["confidence_score"], 70.0)
        self.assertLess(result["grammar_score"], 70.0)
        self.assertEqual(result["label"], "Confident but Needs Grammar Work")

    def test_accurate_but_hesitant(self):
        result = self.analyzer.analyze(
            "I think, um, maybe I sort of led a project, I mean, sorry, it was fine.",
            self._fluency(speech_rate=1.0, pause_count=6, filled_pauses=4),
            self._grammar(error_density=0.0),
        )
        self.assertLess(result["confidence_score"], 70.0)
        self.assertGreaterEqual(result["grammar_score"], 70.0)
        self.assertEqual(result["label"], "Accurate but Hesitant")
        self.assertIn("i think", result["hedges_found"])
        self.assertIn("maybe", result["hedges_found"])

    def test_needs_support(self):
        result = self.analyzer.analyze(
            "I think, um, maybe I sort of led a project, I mean, sorry, it was fine.",
            self._fluency(speech_rate=1.0, pause_count=6, filled_pauses=4),
            self._grammar(error_density=0.6),
        )
        self.assertLess(result["confidence_score"], 70.0)
        self.assertLess(result["grammar_score"], 70.0)
        self.assertEqual(result["label"], "Needs Support")

    def test_repeated_words_lower_text_confidence(self):
        score_with_repeat, hedges, _ = self.analyzer._score_text_confidence(
            "the the project was was difficult"
        )
        score_without_repeat, _, _ = self.analyzer._score_text_confidence(
            "the project was difficult"
        )
        self.assertLess(score_with_repeat, score_without_repeat)

    def test_missing_inputs_default_to_neutral(self):
        result = self.analyzer.analyze("", {}, {})
        self.assertEqual(result["audio_confidence_component"], 50.0)
        self.assertEqual(result["text_confidence_component"], 50.0)
        self.assertEqual(result["grammar_score"], 100.0)

    def test_error_density_clamped(self):
        result = self.analyzer.analyze(
            "text", self._fluency(), self._grammar(error_density=1.5)
        )
        self.assertEqual(result["grammar_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
