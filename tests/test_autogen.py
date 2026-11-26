"""Tests for auto-generation and self-healing framework components."""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from core.test_generator import TestPattern as Pattern, GeneratorEngine
from core.self_healing_element import SelfHealingUIElement
from scripts.autogen_testcases import AutoTestCaseGenerator

pytestmark = pytest.mark.framework


class TestGeneratorEngine:
    """Test the GeneratorEngine class."""

    @pytest.fixture
    def model_file(self, tmp_path):
        """Create a test app model file."""
        model = {
            "screens": [
                {
                    "id": "SCR-00001",
                    "title": "Main Window",
                    "controls": [
                        {
                            "id": "CTL-001",
                            "control_type": "Button",
                            "name": "Save",
                            "automation_id": "SaveButton",
                            "enabled": True,
                            "visible": True,
                            "interactive": True,
                        },
                        {
                            "id": "CTL-002",
                            "control_type": "Edit",
                            "name": "Name",
                            "automation_id": "NameEdit",
                            "enabled": True,
                            "visible": True,
                            "interactive": True,
                        },
                        {
                            "id": "CTL-003",
                            "control_type": "CheckBox",
                            "name": "Enabled",
                            "automation_id": "EnabledCheck",
                            "enabled": True,
                            "visible": True,
                            "interactive": True,
                        },
                    ]
                }
            ]
        }
        path = tmp_path / "app-model.json"
        path.write_text(json.dumps(model), encoding="utf-8")
        return path

    def test_load_model(self, model_file):
        """Test loading app model from file."""
        gen = GeneratorEngine(model_file)
        assert gen.app_model is not None
        assert len(gen.app_model["screens"]) == 1
        assert gen.app_model["screens"][0]["id"] == "SCR-00001"

    def test_extract_controls(self, model_file):
        """Test extracting controls from model."""
        gen = GeneratorEngine(model_file)
        assert len(gen.controls) == 3
        assert "CTL-001" in gen.controls
        assert gen.controls["CTL-001"].control_type == "Button"
        assert gen.controls["CTL-002"].automation_id == "NameEdit"

    def test_generate_scenarios(self, model_file):
        """Test scenario generation from UI structure."""
        gen = GeneratorEngine(model_file)
        scenarios = gen.generate_scenarios()
        assert len(scenarios) > 0
        assert all(hasattr(s, "case_id") for s in scenarios)
        assert all(hasattr(s, "pattern") for s in scenarios)

    def test_generate_ui_state_tests(self, model_file):
        """Test UI state test generation."""
        gen = GeneratorEngine(model_file)
        scenarios = gen.generate_scenarios()
        ui_state_scenarios = [s for s in scenarios if s.pattern == Pattern.UI_STATE]
        assert len(ui_state_scenarios) > 0
        for s in ui_state_scenarios:
            assert "is_visible" in " ".join(s.assertions).lower()

    def test_generate_text_input_tests(self, model_file):
        """Test text input test generation."""
        gen = GeneratorEngine(model_file)
        scenarios = gen.generate_scenarios()
        text_scenarios = [s for s in scenarios if s.pattern == Pattern.TEXT_INPUT]
        assert len(text_scenarios) > 0

    def test_generate_button_click_tests(self, model_file):
        """Test button click test generation."""
        gen = GeneratorEngine(model_file)
        scenarios = gen.generate_scenarios()
        button_scenarios = [s for s in scenarios if s.pattern == Pattern.BUTTON_CLICK]
        assert len(button_scenarios) > 0

    def test_generate_markdown_cases(self, model_file):
        """Test markdown test case generation."""
        gen = GeneratorEngine(model_file)
        scenarios = gen.generate_scenarios()
        markdown = gen.generate_manual_cases_markdown(scenarios)
        assert "# Auto-generated test cases" in markdown
        assert "## Test case:" in markdown
        assert "id: GEN-" in markdown
        assert "tag: auto-gen" in markdown

    def test_generate_page_object(self, model_file):
        """Test page object generation."""
        gen = GeneratorEngine(model_file)
        scenarios = gen.generate_scenarios()
        code = gen.generate_page_object("testapp", scenarios)
        assert "class TestappPage(UIElement)" in code
        assert "@property" in code
        assert "def verify_ui_ready" in code

    def test_generate_pytest_tests(self, model_file):
        """Test pytest code generation."""
        gen = GeneratorEngine(model_file)
        scenarios = gen.generate_scenarios()
        code = gen.generate_pytest_tests("testapp", scenarios, "TestappPage")
        assert "import pytest" in code
        assert "@pytest.mark.case" in code
        assert "def test_" in code

    def test_generate_test_catalog_json(self, model_file):
        """Test test case catalog JSON generation."""
        gen = GeneratorEngine(model_file)
        scenarios = gen.generate_scenarios()
        catalog_json = gen.generate_test_cases_json(scenarios)
        catalog = json.loads(catalog_json)
        assert "cases" in catalog
        assert len(catalog["cases"]) > 0
        assert all("id" in c for c in catalog["cases"])
        assert all("title" in c for c in catalog["cases"])
        assert all("steps" in c for c in catalog["cases"])

    def test_cli_generator_uses_default_output_directory(self, model_file, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        generator = AutoTestCaseGenerator(
            app_path="app.exe", app_name="testapp", app_model_path=model_file
        )
        assert generator.output_dir == tmp_path / "artifacts" / "generated"
        result = generator.generate()
        assert result["scenarios_count"] > 0
        assert Path(result["pytest_tests"]).is_file()


class TestSelfHealingUIElement:
    """Test the SelfHealingUIElement class."""

    @pytest.fixture
    def mock_window(self):
        """Create a mock window for testing."""
        window = MagicMock()
        return window

    def test_init_creates_healing_log_dir(self, mock_window, tmp_path):
        """Test initialization creates healing log directory."""
        element = SelfHealingUIElement(mock_window, healing_log_dir=tmp_path)
        assert element.healing_log_dir == tmp_path
        assert element.healing_log_dir.exists()

    def test_healing_history_empty_on_init(self, mock_window):
        """Test healing history is empty on initialization."""
        element = SelfHealingUIElement(mock_window)
        assert element.healing_history == []
        assert element.healed_count == 0
        assert element.total_healing_attempts == 0

    def test_log_healing_attempt(self, mock_window):
        """Test logging a healing attempt."""
        element = SelfHealingUIElement(mock_window)
        element._log_healing_attempt(
            original_strategy="by_id",
            original_params={"auto_id": "Button1"},
            fallback_strategy="by_name",
            fallback_params={"name": "Button"},
            success=True,
        )
        assert element.total_healing_attempts == 1
        assert element.healed_count == 1

    def test_healed_count_success_only(self, mock_window):
        """Test healed_count counts only successful heals."""
        element = SelfHealingUIElement(mock_window)
        element._log_healing_attempt(
            original_strategy="by_id",
            original_params={"auto_id": "Button1"},
            fallback_strategy="by_name",
            fallback_params={"name": "Button"},
            success=True,
        )
        element._log_healing_attempt(
            original_strategy="by_id",
            original_params={"auto_id": "Button2"},
            fallback_strategy="by_name",
            fallback_params={"name": "Missing"},
            success=False,
            error="Not found",
        )
        assert element.total_healing_attempts == 2
        assert element.healed_count == 1

    def test_save_healing_report(self, mock_window, tmp_path):
        """Test saving healing report to JSON file."""
        element = SelfHealingUIElement(mock_window, healing_log_dir=tmp_path)
        element._log_healing_attempt(
            original_strategy="by_id",
            original_params={"auto_id": "Button1"},
            fallback_strategy="by_name",
            fallback_params={"name": "Button"},
            success=True,
        )
        
        report_path = element.save_healing_report("test_name")
        assert report_path is not None
        assert report_path.exists()
        
        report = json.loads(report_path.read_text())
        assert report["test"] == "test_name"
        assert report["total_heals"] == 1
        assert len(report["healing_attempts"]) == 1

    def test_save_healing_report_no_heals(self, mock_window, tmp_path):
        """Test saving healing report when no heals occurred."""
        element = SelfHealingUIElement(mock_window, healing_log_dir=tmp_path)
        report_path = element.save_healing_report("test_name")
        assert report_path is None


@pytest.mark.framework
def test_standards_compliance():
    """Verify framework standards compliance."""
    from core.ui_element import UIElement
    
    # Verify UIElement has expected methods
    methods = [
        "by_id", "by_name", "by_descendant_id", "by_descendant_name",
        "by_class", "wait_visible", "wait_gone", "wait_window",
        "wait_until", "click", "type_text", "get_text"
    ]
    for method_name in methods:
        assert hasattr(UIElement, method_name), f"UIElement missing {method_name}"


@pytest.mark.framework
def test_case_id_format():
    """Test case ID format compliance."""
    import re
    
    # Valid case IDs
    valid_ids = [
        "APP-001", "APP-999", "NOTEPAD-001", "SQLDM-050",
        "GEN-001", "TEST-1000"
    ]
    
    # Invalid case IDs
    invalid_ids = [
        "app-001",  # lowercase
        "APP001",   # missing dash
        "APP-",     # incomplete
        "APP-00",   # wrong length
        "TEST-NNN",  # non-numeric suffix
    ]
    
    pattern = re.compile(r"^[A-Z][A-Z0-9]*-\d{3,}$")
    
    for valid_id in valid_ids:
        assert pattern.match(valid_id), f"{valid_id} should be valid"
    
    for invalid_id in invalid_ids:
        assert not pattern.match(invalid_id), f"{invalid_id} should be invalid"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
