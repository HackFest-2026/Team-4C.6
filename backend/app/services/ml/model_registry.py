import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import joblib

from app.core.config import settings

logger = logging.getLogger(__name__)


class ModelRegistry:
    """
    Manages loading, status inspection, and metadata retrieval for trained ML models.
    """
    def __init__(self, artifacts_dir: Optional[str] = None):
        self.artifacts_dir = Path(artifacts_dir or settings.ARTIFACTS_DIR)
        self._loaded_models: Dict[str, Any] = {}
        self._metadata: Optional[Dict[str, Any]] = None

    def get_metadata(self) -> Dict[str, Any]:
        meta_path = self.artifacts_dir / "model_metadata.json"
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read model metadata: {e}")
        return {
            "status": "uninitialized",
            "models": {},
            "provenance": "Synthetic simulated dataset (CostPilot_AI_Training_Dataset.xlsx)",
        }

    def is_model_available(self, target_name: str) -> bool:
        meta = self.get_metadata()
        models_meta = meta.get("models", {})
        if target_name in models_meta:
            artifact_file = models_meta[target_name].get("artifact_file")
            if artifact_file and (self.artifacts_dir / artifact_file).exists():
                return True
        return False

    def load_model(self, target_name: str) -> Optional[Any]:
        if target_name in self._loaded_models:
            return self._loaded_models[target_name]

        meta = self.get_metadata()
        models_meta = meta.get("models", {})
        if target_name not in models_meta:
            logger.info(f"Target '{target_name}' not registered in model metadata.")
            return None

        artifact_file = models_meta[target_name].get("artifact_file")
        if not artifact_file:
            return None

        model_path = self.artifacts_dir / artifact_file
        if not model_path.exists():
            logger.warning(f"Model artifact file not found: {model_path}")
            return None

        try:
            model = joblib.load(model_path)
            self._loaded_models[target_name] = model
            logger.info(f"Successfully loaded model for target: {target_name}")
            return model
        except Exception as e:
            logger.error(f"Error loading model from {model_path}: {e}")
            return None

    def get_status(self) -> Dict[str, Any]:
        meta = self.get_metadata()
        models_status = {}
        for target, m_info in meta.get("models", {}).items():
            artifact = m_info.get("artifact_file")
            exists = (self.artifacts_dir / artifact).exists() if artifact else False
            models_status[target] = {
                "available": exists,
                "version": m_info.get("version", "unknown"),
                "trained_at": m_info.get("trained_at", "unknown"),
                "algorithm": m_info.get("algorithm", "RandomForestRegressor"),
                "r2_score": m_info.get("metrics", {}).get("test_r2"),
                "mae": m_info.get("metrics", {}).get("test_mae"),
                "mmre": m_info.get("metrics", {}).get("test_mmre"),
                "provenance": "Trained on simulated synthetic data",
            }

        return {
            "status": "ready" if any(s["available"] for s in models_status.values()) else "needs_training",
            "artifacts_dir": str(self.artifacts_dir),
            "models": models_status,
            "overall_provenance": "SIMULATED / SYNTHETIC DATASET. Real-world commercial actuals require future collection.",
        }


model_registry = ModelRegistry()
