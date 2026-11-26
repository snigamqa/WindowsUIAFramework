"""Self-healing UI element wrapper with automatic locator fallback strategies.

When a primary locator fails, automatically tries alternative locators and
learns from failures. Logs what changed and why for diagnosis and adaptation.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any

from core.ui_element import UIElement

logger = logging.getLogger(__name__)


class LocatorStrategy:
    """Represents a single locator attempt and its result."""

    def __init__(self, strategy_name: str, **kwargs):
        self.strategy_name = strategy_name
        self.kwargs = kwargs
        self.success = False
        self.error = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy_name,
            "params": self.kwargs,
            "success": self.success,
            "error": str(self.error) if self.error else None,
        }


class SelfHealingUIElement(UIElement):
    """Self-healing wrapper for UIElement.
    
    Extends UIElement with automatic fallback strategies when locators fail.
    Records healing attempts for diagnostics and automatic test updates.
    """

    def __init__(self, window, healing_log_dir: Optional[Path] = None):
        super().__init__(window)
        self.healing_log_dir = (
            Path(healing_log_dir) if healing_log_dir is not None
            else Path.cwd() / "artifacts" / "healing"
        )
        self.healing_log_dir.mkdir(parents=True, exist_ok=True)
        self.healing_history = []

    def _log_healing_attempt(
        self,
        original_strategy: str,
        original_params: Dict[str, Any],
        fallback_strategy: Optional[str] = None,
        fallback_params: Optional[Dict[str, Any]] = None,
        success: bool = False,
        error: Optional[str] = None,
    ):
        """Record a healing attempt for later analysis."""
        entry = {
            "original": {
                "strategy": original_strategy,
                "params": original_params,
            },
            "fallback": {
                "strategy": fallback_strategy,
                "params": fallback_params or {},
            } if fallback_strategy else None,
            "success": success,
            "error": error,
        }
        self.healing_history.append(entry)
        logger.warning(
            f"Healed locator: {original_strategy}({original_params}) "
            f"→ {fallback_strategy}({fallback_params or {}}) [success={success}]"
        )

    def _try_strategies(
        self,
        primary_strategy_name: str,
        primary_params: Dict[str, Any],
        fallback_strategies: List[tuple],
    ):
        """Try primary strategy, then fallbacks in order.
        
        Args:
            primary_strategy_name: Name of primary locator method
            primary_params: Parameters for primary strategy
            fallback_strategies: List of (strategy_name, params_dict) tuples
        
        Returns:
            (element, used_strategy_name, used_params) if successful, else raises
        """
        # Try primary
        try:
            method = getattr(self, primary_strategy_name)
            element = method(**primary_params)
            return element, primary_strategy_name, primary_params
        except Exception as e:
            logger.debug(f"{primary_strategy_name} failed: {e}")

        # Try fallbacks
        for fallback_name, fallback_params in fallback_strategies:
            try:
                method = getattr(self, fallback_name)
                element = method(**fallback_params)
                self._log_healing_attempt(
                    primary_strategy_name,
                    primary_params,
                    fallback_name,
                    fallback_params,
                    success=True,
                )
                return element, fallback_name, fallback_params
            except Exception as e:
                logger.debug(f"{fallback_name} failed: {e}")
                self._log_healing_attempt(
                    primary_strategy_name,
                    primary_params,
                    fallback_name,
                    fallback_params,
                    success=False,
                    error=str(e),
                )

        # All failed
        raise LookupError(
            f"All locator strategies failed for {primary_strategy_name}({primary_params}). "
            f"Tried fallbacks: {[name for name, _ in fallback_strategies]}"
        )

    def by_id_with_fallback(self, auto_id: str, **kw):
        """Find element by AutomationId with fallback to Name → Descendant."""
        fallbacks = [
            ("by_name", {"name": auto_id, **kw}),
            ("by_descendant_id", {"auto_id": auto_id, **kw}),
        ]
        return self._try_strategies("by_id", {"auto_id": auto_id, **kw}, fallbacks)[0]

    def by_name_with_fallback(self, name: str, **kw):
        """Find element by Name with fallback to AutomationId → Descendant."""
        fallbacks = [
            ("by_id", {"auto_id": name, **kw}),
            ("by_descendant_name", {"name": name, **kw}),
        ]
        return self._try_strategies("by_name", {"name": name, **kw}, fallbacks)[0]

    def by_class_with_fallback(self, cls: str, index: int = 0, **kw):
        """Find element by class with fallback to other strategies."""
        fallbacks = [
            ("by_name", {"name": cls, **kw}),
            ("by_id", {"auto_id": cls, **kw}),
        ]
        return self._try_strategies(
            "by_class", {"cls": cls, "index": index, **kw}, fallbacks
        )[0]

    def save_healing_report(self, test_name: str) -> Path:
        """Save healing history to a JSON report."""
        if not self.healing_history:
            return None

        report_path = self.healing_log_dir / f"{test_name}_healing.json"
        report = {
            "test": test_name,
            "total_heals": len(self.healing_history),
            "healing_attempts": self.healing_history,
        }
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        logger.info(f"Healing report saved to {report_path}")
        return report_path

    @property
    def healed_count(self) -> int:
        """Return number of successful heals."""
        return sum(1 for entry in self.healing_history if entry.get("success"))

    @property
    def total_healing_attempts(self) -> int:
        """Return total number of healing attempts."""
        return len(self.healing_history)
