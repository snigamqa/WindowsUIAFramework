"""Test case generation engine: pattern recognition and intelligent code generation."""

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum


class TestPattern(Enum):
    """Test design pattern categories."""
    UI_STATE = "ui_state"  # Verify controls visible/enabled
    TEXT_INPUT = "text_input"  # Type text and verify
    BUTTON_CLICK = "button_click"  # Click and verify result
    DIALOG = "dialog"  # Open, interact, close
    ERROR_HANDLING = "error_handling"  # Invalid input → error
    NAVIGATION = "navigation"  # Workflow transitions


@dataclass
class ControlInfo:
    """Information about a UI control from exploration."""
    id: str
    control_type: str
    name: str
    automation_id: str
    class_name: str
    enabled: bool
    visible: bool


@dataclass
class TestScenario:
    """Generated test scenario."""
    case_id: str
    title: str
    pattern: TestPattern
    steps: List[str]
    assertions: List[str]
    setup: List[str]
    cleanup: List[str]


class GeneratorEngine:
    """Generate test cases from UI structure and patterns."""

    # Pattern templates for different test scenarios
    PATTERN_TEMPLATES = {
        "UI_STATE": {
            "template": """def test_{test_id}({fixture}):
    \"\"\"Verify {title}\"\"\"
    # Setup
    {setup}
    
    # Action
    {action}
    
    # Assert
    {assertions}
""",
            "assert_visible": "assert {element}.is_visible()",
            "assert_enabled": "assert {element}.is_enabled()",
        },
        "TEXT_INPUT": {
            "template": """def test_{test_id}({fixture}):
    \"\"\"Verify {title}\"\"\"
    test_text = "Test input {index}"
    {setup}
    
    # Type text
    page.type_text({element}, test_text)
    
    # Verify
    assert page.get_text({element}) == test_text
    {assertions}
""",
        },
        "BUTTON_CLICK": {
            "template": """def test_{test_id}({fixture}):
    \"\"\"Verify {title}\"\"\"
    {setup}
    
    # Click button
    page.click({element})
    page.wait_until(lambda: {verify_condition})
    
    # Assert result
    {assertions}
""",
        },
    }

    def __init__(self, app_model_path: Path):
        """Initialize generator with exploration model."""
        self.app_model_path = Path(app_model_path)
        self.app_model = self._load_model()
        self.controls = self._extract_controls()

    def _load_model(self) -> Dict[str, Any]:
        """Load app-model.json from exploration."""
        if self.app_model_path.exists():
            return json.loads(self.app_model_path.read_text(encoding="utf-8"))
        return {"screens": [], "controls": {}}

    def _extract_controls(self) -> Dict[str, ControlInfo]:
        """Extract all controls from model."""
        controls = {}
        for screen in self.app_model.get("screens", []):
            for ctl in screen.get("controls", []):
                if not ctl.get("interactive"):
                    continue
                info = ControlInfo(
                    id=ctl.get("id", ""),
                    control_type=ctl.get("control_type", ""),
                    name=ctl.get("name", ""),
                    automation_id=ctl.get("automation_id", ""),
                    class_name=ctl.get("class_name", ""),
                    enabled=ctl.get("enabled", True),
                    visible=ctl.get("visible", True),
                )
                controls[info.id] = info
        return controls

    def generate_scenarios(self) -> List[TestScenario]:
        """Generate test scenarios from UI structure."""
        scenarios = []

        # Group controls by type
        buttons = [c for c in self.controls.values() if c.control_type == "Button"]
        edits = [c for c in self.controls.values() if c.control_type == "Edit"]
        checkboxes = [c for c in self.controls.values() if c.control_type == "CheckBox"]

        # UI State tests
        scenarios.extend(self._generate_ui_state_tests(buttons, edits, checkboxes))

        # Text Input tests
        scenarios.extend(self._generate_text_input_tests(edits))

        # Button Click tests
        scenarios.extend(self._generate_button_click_tests(buttons))

        return scenarios

    def _generate_ui_state_tests(
        self, buttons: List[ControlInfo], edits: List[ControlInfo], checks: List[ControlInfo]
    ) -> List[TestScenario]:
        """Generate UI state verification tests."""
        scenarios = []
        all_controls = buttons + edits + checks

        for idx, control in enumerate(all_controls[:5], start=1):  # Limit to 5
            if not control.visible or not control.automation_id:
                continue

            case_id = f"GEN-{idx:03d}"
            title = f"Verify {control.name or control.automation_id} is visible and enabled"

            steps = [
                f"Locate {control.name}",
                f"Verify it is visible",
                f"Verify it is enabled",
            ]

            assertions = [
                f"assert element.is_visible()",
                f"assert element.is_enabled()",
            ]

            scenarios.append(
                TestScenario(
                    case_id=case_id,
                    title=title,
                    pattern=TestPattern.UI_STATE,
                    steps=steps,
                    assertions=assertions,
                    setup=[],
                    cleanup=[],
                )
            )

        return scenarios

    def _generate_text_input_tests(self, edits: List[ControlInfo]) -> List[TestScenario]:
        """Generate text input verification tests."""
        scenarios = []

        for idx, control in enumerate(edits[:3], start=101):
            if not control.visible:
                continue

            case_id = f"GEN-{idx:03d}"
            title = f"Verify text input in {control.name or control.automation_id}"

            steps = [
                f"Locate {control.name}",
                "Enter test text",
                "Read and verify text matches input",
            ]

            assertions = [
                "text matches input",
            ]

            scenarios.append(
                TestScenario(
                    case_id=case_id,
                    title=title,
                    pattern=TestPattern.TEXT_INPUT,
                    steps=steps,
                    assertions=assertions,
                    setup=[],
                    cleanup=[],
                )
            )

        return scenarios

    def _generate_button_click_tests(self, buttons: List[ControlInfo]) -> List[TestScenario]:
        """Generate button click tests."""
        scenarios = []

        # Skip dangerous button names
        deny_pattern = re.compile(
            r"(close|exit|cancel|delete|remove|ok\s*$)",
            re.IGNORECASE
        )

        for idx, control in enumerate(buttons[:5], start=201):
            if not control.visible or deny_pattern.search(control.name or ""):
                continue

            case_id = f"GEN-{idx:03d}"
            title = f"Verify clicking {control.name or control.automation_id} works"

            steps = [
                f"Locate {control.name}",
                f"Click the button",
                "Verify action completes",
            ]

            assertions = [
                "action completes without error",
            ]

            scenarios.append(
                TestScenario(
                    case_id=case_id,
                    title=title,
                    pattern=TestPattern.BUTTON_CLICK,
                    steps=steps,
                    assertions=assertions,
                    setup=[],
                    cleanup=[],
                )
            )

        return scenarios

    def generate_manual_cases_markdown(self, scenarios: List[TestScenario]) -> str:
        """Generate Markdown manual test cases."""
        lines = ["# Auto-generated test cases\n"]

        for scenario in scenarios:
            lines.append(f"## Test case: {scenario.title} (id: {scenario.case_id}, tag: auto-gen)")
            lines.append("- Oracle: inferred")
            for idx, step in enumerate(scenario.steps, start=1):
                lines.append(f"{idx}. {step}")
            if scenario.assertions:
                lines.append(f"- Expected: {'; '.join(scenario.assertions)}")
            lines.append("")

        return "\n".join(lines)

    def generate_page_object(
        self,
        app_name: str,
        scenarios: List[TestScenario],
    ) -> str:
        """Generate page object Python code."""
        code = [
            f'"""Page object for {app_name} automation."""',
            "",
            "from core.ui_element import UIElement",
            "",
            "",
            f"class {self._camel_case(app_name)}Page(UIElement):",
            f'    """Page object for {app_name}."""',
            "",
        ]

        # Add properties for key controls
        for scenario in scenarios[:5]:
            prop_name = scenario.case_id.lower()
            code.append(f"    @property")
            code.append(f"    def {prop_name}(self):")
            code.append(f'        """Locator for {scenario.title}."""')
            code.append(f"        return self.by_descendant_id('{scenario.case_id}')")
            code.append("")

        # Add helper methods
        code.append("    def verify_ui_ready(self):")
        code.append('        """Verify app UI is ready for testing."""')
        for scenario in scenarios[:3]:
            code.append(f"        self.wait_visible(self.{scenario.case_id.lower()})")
        code.append("")

        return "\n".join(code)

    def generate_pytest_tests(
        self,
        app_name: str,
        scenarios: List[TestScenario],
        page_class: str,
    ) -> str:
        """Generate pytest test code."""
        code = [
            f'"""Auto-generated tests for {app_name}."""',
            "",
            "import pytest",
            f"from pages.{app_name.lower()}_page import {page_class}",
            "",
            "",
        ]

        for scenario in scenarios[:10]:
            test_name = self._make_test_name(scenario.title)
            code.append(f"@pytest.mark.case(id='{scenario.case_id}', title='{scenario.title}')")
            code.append(f"def test_{test_name}(app):")
            code.append(f'    """Test: {scenario.title}"""')
            code.append(f"    page = {page_class}(app)")
            code.append(f"    page.verify_ui_ready()")
            code.append(f"    # TODO: implement test logic from scenario")
            code.append("")

        return "\n".join(code)

    def generate_test_cases_json(
        self,
        scenarios: List[TestScenario],
    ) -> str:
        """Generate JSON test case catalog."""
        cases = []
        for scenario in scenarios:
            cases.append({
                "id": scenario.case_id,
                "title": scenario.title,
                "steps": scenario.steps,
                "expected": "; ".join(scenario.assertions) if scenario.assertions else "Test passes",
                "oracle": "inferred",
                "automation": "todo",
                "pattern": scenario.pattern.value,
                "notes": f"Auto-generated from UI exploration"
            })

        return json.dumps({"cases": cases}, indent=2)

    @staticmethod
    def _camel_case(text: str) -> str:
        """Convert text to CamelCase."""
        return "".join(word.capitalize() for word in re.split(r"[_\s-]+", text))

    @staticmethod
    def _make_test_name(title: str) -> str:
        """Convert title to test function name."""
        name = re.sub(r"[^a-z0-9]+", "_", title.lower())
        return name.strip("_")


# Compatibility alias for imports from scripts/autogen_testcases.py
TestCaseGenerator = GeneratorEngine
