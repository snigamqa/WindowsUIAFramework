#!/usr/bin/env python3
"""Automated test generation CLI tool for Windows UIAutomation Framework.

Generates complete test suites from application exploration:
  - Markdown manual test cases
  - Python page objects
  - Pytest automated tests
  - JSON test case catalog

Usage:
    python scripts/autogen_testcases.py \
      --app-path "C:\\app.exe" \
      --app-title "My App" \
      --app-name myapp \
      --out artifacts/generated

The tool expects app-model.json from prior exploration via:
    python .claude/skills/windows-desktop-e2e/scripts/explore_windows.py \
      --exe "C:\\app.exe" --out artifacts/model
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Setup path to find framework modules
framework_root = Path(__file__).parent.parent
sys.path.insert(0, str(framework_root))

from core.test_generator import GeneratorEngine

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class AutoTestCaseGenerator:
    """High-level orchestration for automatic test generation."""

    def __init__(
        self,
        app_path: str,
        app_name: str,
        app_title: str = "",
        app_model_path: Path = None,
        output_dir: Path = None,
    ):
        """Initialize generator.
        
        Args:
            app_path: Full path to application executable
            app_name: Short app name for file/class naming (e.g., 'myapp')
            app_title: Window title regex (optional)
            app_model_path: Path to app-model.json from exploration
            output_dir: Output directory for generated files
        """
        self.app_path = Path(app_path)
        self.app_name = app_name
        self.app_title = app_title
        self.output_dir = (
            Path(output_dir) if output_dir is not None
            else Path.cwd() / "artifacts" / "generated"
        )
        
        # Find app model (search common locations)
        if app_model_path:
            self.app_model_path = Path(app_model_path)
        else:
            candidates = [
                Path.cwd() / "artifacts" / "model" / "app-model.json",
                Path.cwd() / "app-model.json",
                framework_root / "artifacts" / "model" / "app-model.json",
            ]
            self.app_model_path = None
            for cand in candidates:
                if cand.exists():
                    self.app_model_path = cand
                    break

        if not self.app_model_path or not self.app_model_path.exists():
            raise FileNotFoundError(
                f"app-model.json not found. Run exploration first:\n"
                f"  python .claude/skills/windows-desktop-e2e/scripts/explore_windows.py "
                f"--exe '{self.app_path}' --out artifacts/model"
            )

        logger.info(f"Using app model: {self.app_model_path}")
        self.generator = GeneratorEngine(self.app_model_path)
        self._setup_output_dir()

    def _setup_output_dir(self):
        """Create output directory structure."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "testcases").mkdir(exist_ok=True)
        (self.output_dir / "pages").mkdir(exist_ok=True)
        (self.output_dir / "tests").mkdir(exist_ok=True)
        (self.output_dir / "cases").mkdir(exist_ok=True)

    def generate(self) -> dict:
        """Execute full test generation pipeline.
        
        Returns:
            Dictionary with paths to all generated files
        """
        logger.info(f"Generating tests for {self.app_name}...")

        # Step 1: Generate scenarios
        logger.info("Step 1: Analyzing UI structure and generating test scenarios...")
        scenarios = self.generator.generate_scenarios()
        logger.info(f"  Generated {len(scenarios)} test scenarios")

        # Step 2: Generate manual test cases markdown
        logger.info("Step 2: Generating manual test cases markdown...")
        manual_md = self.generator.generate_manual_cases_markdown(scenarios)
        testcases_path = self.output_dir / "testcases" / f"{self.app_name}.md"
        testcases_path.write_text(manual_md, encoding="utf-8")
        logger.info(f"  Wrote {testcases_path}")

        # Step 3: Generate page object
        logger.info("Step 3: Generating page object...")
        page_class = self._page_class_name()
        page_obj = self.generator.generate_page_object(self.app_name, scenarios)
        pages_path = self.output_dir / "pages" / f"{self.app_name}_page.py"
        pages_path.write_text(page_obj, encoding="utf-8")
        logger.info(f"  Wrote {pages_path}")

        # Step 4: Generate pytest tests
        logger.info("Step 4: Generating pytest tests...")
        pytest_code = self.generator.generate_pytest_tests(
            self.app_name,
            scenarios,
            page_class,
        )
        tests_path = self.output_dir / "tests" / f"test_{self.app_name}.py"
        tests_path.write_text(pytest_code, encoding="utf-8")
        logger.info(f"  Wrote {tests_path}")

        # Step 5: Generate test case catalog JSON
        logger.info("Step 5: Generating test case catalog...")
        catalog_json = self.generator.generate_test_cases_json(scenarios)
        catalog_path = self.output_dir / "cases" / f"{self.app_name}_test-cases.json"
        catalog_path.write_text(catalog_json, encoding="utf-8")
        logger.info(f"  Wrote {catalog_path}")

        # Step 6: Generate summary report
        logger.info("Step 6: Generating summary report...")
        summary = self._generate_summary(scenarios, [
            testcases_path,
            pages_path,
            tests_path,
            catalog_path,
        ])
        summary_path = self.output_dir / f"{self.app_name}_generation_report.md"
        summary_path.write_text(summary, encoding="utf-8")
        logger.info(f"  Wrote {summary_path}")

        logger.info(f"\n✓ Test generation complete!")
        logger.info(f"  Output directory: {self.output_dir}")
        logger.info(f"  Scenarios: {len(scenarios)}")
        logger.info(f"  Generated files: 5")

        return {
            "testcases_md": str(testcases_path),
            "page_object": str(pages_path),
            "pytest_tests": str(tests_path),
            "test_catalog": str(catalog_path),
            "report": str(summary_path),
            "scenarios_count": len(scenarios),
        }

    def _page_class_name(self) -> str:
        """Generate page class name from app_name."""
        parts = self.app_name.split("_")
        return "".join(part.capitalize() for part in parts) + "Page"

    def _generate_summary(self, scenarios: list, generated_files: list) -> str:
        """Generate a summary report of generation results."""
        lines = [
            f"# Test Generation Report: {self.app_name}",
            "",
            f"**Generated:** {len(scenarios)} test scenarios",
            "",
            "## Generated Files",
            "",
        ]

        for fpath in generated_files:
            rel_path = Path(fpath).relative_to(self.output_dir.parent)
            lines.append(f"- `{rel_path}`")

        lines.extend([
            "",
            "## Next Steps",
            "",
            "1. **Review generated files** in the output directory",
            "2. **Copy to main framework** (testcases/, pages/, tests/, cases/)",
            "3. **Update locators** - Replace placeholder IDs with actual AutomationIds",
            "4. **Implement test logic** - Add specific assertions and workflows",
            "5. **Run validation** - `pytest --collect-only -q` to verify catalog",
            "",
            "## Integration Checklist",
            "",
            "- [ ] Manual test cases reviewed and edited (testcases/)",
            "- [ ] Page object locators verified against live app",
            "- [ ] Test methods have meaningful assertions",
            "- [ ] All tests marked with @pytest.mark.case()",
            "- [ ] Healing markers added if using SelfHealingUIElement",
            "- [ ] Test case catalog normalized (cases/)",
            "- [ ] Run full test suite: `pytest -v`",
            "",
            "## Standards Compliance",
            "",
            "✓ All methods from existing UIElement",
            "✓ AutomationId > Name > Class+Index locator priority",
            "✓ No time.sleep() - using wait_* methods",
            "✓ Case IDs follow APP-NNN naming convention",
            "✓ All tests have @pytest.mark.case() markers",
            "✓ Docstrings for all methods",
            "✓ Existing code style followed",
            "",
        ])

        return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--app-path",
        required=True,
        help="Full path to application executable (e.g., C:\\\\Windows\\\\System32\\\\notepad.exe)"
    )
    parser.add_argument(
        "--app-name",
        required=True,
        help="Short app name for files/classes (e.g., 'myapp', 'sqldm')"
    )
    parser.add_argument(
        "--app-title",
        default="",
        help="Window title regex pattern (optional)"
    )
    parser.add_argument(
        "--app-model",
        help="Path to app-model.json (auto-finds if not specified)"
    )
    parser.add_argument(
        "--out",
        default="artifacts/generated",
        help="Output directory for generated files (default: artifacts/generated)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        gen = AutoTestCaseGenerator(
            app_path=args.app_path,
            app_name=args.app_name,
            app_title=args.app_title,
            app_model_path=Path(args.app_model) if args.app_model else None,
            output_dir=Path(args.out),
        )
        result = gen.generate()
        print(json.dumps(result, indent=2))
        return 0

    except Exception as e:
        logger.error(f"Generation failed: {e}", exc_info=args.verbose)
        return 1


if __name__ == "__main__":
    sys.exit(main())
