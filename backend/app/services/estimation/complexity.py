from typing import Dict, Any, Tuple
from app.core.config import settings


class ComplexityAnalyzer:
    """
    Analyzes and calculates feature and project complexity using:
    1. Automatic keyword/type heuristic
    2. Manual override
    3. 9-factor weighted evaluation (0-5 scale, 0-100 score)
    """

    def __init__(self):
        self.weights = settings.COMPLEXITY_FACTOR_WEIGHTS
        self.thresholds = settings.COMPLEXITY_THRESHOLDS

    def score_to_level(self, score: float) -> str:
        s = max(0.0, min(100.0, float(score)))
        for level, (low, high) in self.thresholds.items():
            if low <= s <= high:
                return level
        return "Medium"

    def evaluate_9_factors(self, factor_scores: Dict[str, float]) -> Tuple[float, str, Dict[str, Any]]:
        """
        Calculates weighted complexity score and level from the 9 configured factors.
        Each factor should be between 0 and 5.
        """
        sanitized_scores = {}
        weighted_sum = 0.0

        for factor, weight in self.weights.items():
            val = float(factor_scores.get(factor, 2.0))  # Default 2 (moderate)
            clamped = max(0.0, min(5.0, val))
            sanitized_scores[factor] = clamped
            weighted_sum += clamped * weight

        # ComplexityScore = (WeightedScore / 5) * 100
        score = round((weighted_sum / 5.0) * 100.0, 1)
        level = self.score_to_level(score)

        return score, level, {
            "factor_scores": sanitized_scores,
            "weighted_score": score,
            "complexity_level": level,
            "weights_used": self.weights,
        }

    def suggest_complexity(self, title: str, description: str = "") -> str:
        """
        Automatic suggestion based on domain keywords when user does not enter factors.
        """
        text = f"{title} {description}".lower()

        # Very high signals
        if any(w in text for w in ["custom ml", "blockchain", "multi-tenant", "compliance", "hipaa", "distributed", "video streaming"]):
            return "Very High"
        # High signals
        if any(w in text for w in ["payment", "booking", "real-time", "websocket", "ai", "llm", "security", "rbac", "encryption"]):
            return "High"
        # Low signals
        if any(w in text for w in ["static", "faq", "footer", "contact form", "about", "landing", "terms"]):
            return "Low"

        # Default moderate
        return "Medium"


complexity_analyzer = ComplexityAnalyzer()
