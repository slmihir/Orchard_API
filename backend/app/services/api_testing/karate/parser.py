"""Parser for extracting metadata from Karate .feature files."""

import re
from dataclasses import dataclass, field


@dataclass
class KarateStep:
    """Parsed step from a Karate feature file."""
    keyword: str  # Given, When, Then, And, *
    text: str
    line_number: int
    docstring: str | None = None
    data_table: list[list[str]] | None = None


@dataclass
class KarateScenario:
    """Parsed scenario from a Karate feature file."""
    name: str
    line_number: int
    tags: list[str] = field(default_factory=list)
    steps: list[KarateStep] = field(default_factory=list)
    is_outline: bool = False
    examples: list[dict] | None = None


@dataclass
class KarateBackground:
    """Parsed background from a Karate feature file."""
    line_number: int
    steps: list[KarateStep] = field(default_factory=list)


@dataclass
class KarateFeature:
    """Parsed Karate feature file."""
    name: str
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    background: KarateBackground | None = None
    scenarios: list[KarateScenario] = field(default_factory=list)
    line_count: int = 0


class KarateFeatureParser:
    """
    Parser for Karate .feature files.

    Extracts metadata without executing the tests.
    Useful for:
    - Displaying feature contents in UI
    - Validating feature structure
    - Converting between formats
    """

    # Keywords that start steps
    STEP_KEYWORDS = ("Given ", "When ", "Then ", "And ", "But ", "* ")

    def parse(self, content: str) -> KarateFeature:
        """
        Parse a .feature file and extract metadata.

        Args:
            content: The .feature file content

        Returns:
            KarateFeature with parsed structure
        """
        lines = content.split("\n")
        feature = KarateFeature(name="", line_count=len(lines))

        current_tags = []
        current_scenario = None
        current_background = None
        in_docstring = False
        docstring_lines = []
        in_examples = False
        examples_headers = None
        examples_rows = []

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            line_num = i + 1

            # Handle docstrings
            if stripped == '"""' or stripped == "'''":
                if in_docstring:
                    # End docstring
                    in_docstring = False
                    docstring = "\n".join(docstring_lines)
                    # Attach to last step
                    if current_scenario and current_scenario.steps:
                        current_scenario.steps[-1].docstring = docstring
                    elif current_background and current_background.steps:
                        current_background.steps[-1].docstring = docstring
                    docstring_lines = []
                else:
                    in_docstring = True
                i += 1
                continue

            if in_docstring:
                docstring_lines.append(line)
                i += 1
                continue

            # Skip empty lines and comments
            if not stripped or stripped.startswith("#"):
                i += 1
                continue

            # Tags
            if stripped.startswith("@"):
                tags = re.findall(r'@[\w-]+', stripped)
                current_tags.extend(tags)
                i += 1
                continue

            # Feature
            if stripped.startswith("Feature:"):
                feature.name = stripped[8:].strip()
                feature.tags = current_tags
                current_tags = []

                # Collect feature description (lines before Background/Scenario)
                desc_lines = []
                j = i + 1
                while j < len(lines):
                    desc_line = lines[j].strip()
                    if (desc_line.startswith("Background:") or
                        desc_line.startswith("Scenario:") or
                        desc_line.startswith("Scenario Outline:") or
                        desc_line.startswith("@")):
                        break
                    if desc_line and not desc_line.startswith("#"):
                        desc_lines.append(desc_line)
                    j += 1

                if desc_lines:
                    feature.description = "\n".join(desc_lines)

                i += 1
                continue

            # Background
            if stripped.startswith("Background:"):
                current_background = KarateBackground(line_number=line_num)
                in_examples = False
                i += 1
                continue

            # Scenario / Scenario Outline
            if stripped.startswith("Scenario Outline:") or stripped.startswith("Scenario:"):
                # Save previous scenario
                if current_scenario:
                    if examples_rows:
                        current_scenario.examples = self._parse_examples(examples_headers, examples_rows)
                    feature.scenarios.append(current_scenario)

                # Save background
                if current_background:
                    feature.background = current_background
                    current_background = None

                is_outline = stripped.startswith("Scenario Outline:")
                name = stripped.split(":", 1)[1].strip()

                current_scenario = KarateScenario(
                    name=name,
                    line_number=line_num,
                    tags=current_tags,
                    is_outline=is_outline,
                )
                current_tags = []
                in_examples = False
                examples_headers = None
                examples_rows = []
                i += 1
                continue

            # Examples section
            if stripped.startswith("Examples:"):
                in_examples = True
                i += 1
                continue

            # Data table row (in Examples)
            if in_examples and stripped.startswith("|"):
                row = self._parse_table_row(stripped)
                if examples_headers is None:
                    examples_headers = row
                else:
                    examples_rows.append(row)
                i += 1
                continue

            # Step
            if any(stripped.startswith(kw) for kw in self.STEP_KEYWORDS):
                step = self._parse_step(stripped, line_num)

                # Check for data table
                data_table = []
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if next_line.startswith("|"):
                        data_table.append(self._parse_table_row(next_line))
                        j += 1
                    else:
                        break

                if data_table:
                    step.data_table = data_table
                    i = j - 1  # Move past data table

                # Add step to current context
                if current_scenario:
                    current_scenario.steps.append(step)
                elif current_background:
                    current_background.steps.append(step)

                i += 1
                continue

            i += 1

        # Don't forget last scenario
        if current_scenario:
            if examples_rows:
                current_scenario.examples = self._parse_examples(examples_headers, examples_rows)
            feature.scenarios.append(current_scenario)

        # Don't forget background if no scenarios
        if current_background and not feature.background:
            feature.background = current_background

        return feature

    def _parse_step(self, line: str, line_number: int) -> KarateStep:
        """Parse a step line."""
        keyword = ""
        text = line

        for kw in self.STEP_KEYWORDS:
            if line.startswith(kw):
                keyword = kw.strip()
                text = line[len(kw):].strip()
                break

        return KarateStep(
            keyword=keyword,
            text=text,
            line_number=line_number,
        )

    def _parse_table_row(self, line: str) -> list[str]:
        """Parse a data table row."""
        # Remove leading/trailing pipes and split
        cells = line.strip("|").split("|")
        return [cell.strip() for cell in cells]

    def _parse_examples(
        self,
        headers: list[str] | None,
        rows: list[list[str]],
    ) -> list[dict]:
        """Convert Examples table to list of dicts."""
        if not headers or not rows:
            return []

        result = []
        for row in rows:
            example = {}
            for i, header in enumerate(headers):
                if i < len(row):
                    example[header] = row[i]
            result.append(example)

        return result

    def to_metadata_dict(self, feature: KarateFeature) -> dict:
        """
        Convert parsed feature to metadata dictionary for storage.

        This is used for the KarateFeatureFile.parsed_metadata field.
        """
        return {
            "feature_name": feature.name,
            "description": feature.description,
            "feature_tags": feature.tags,
            "line_count": feature.line_count,
            "has_background": feature.background is not None,
            "background_steps": len(feature.background.steps) if feature.background else 0,
            "scenarios": [
                {
                    "name": s.name,
                    "line_number": s.line_number,
                    "tags": s.tags,
                    "step_count": len(s.steps),
                    "is_outline": s.is_outline,
                    "example_count": len(s.examples) if s.examples else 0,
                }
                for s in feature.scenarios
            ],
            "total_scenarios": len(feature.scenarios),
            "total_steps": sum(len(s.steps) for s in feature.scenarios),
        }

    def extract_tags(self, feature: KarateFeature) -> list[str]:
        """Extract all unique tags from feature and scenarios."""
        tags = set(feature.tags)
        for scenario in feature.scenarios:
            tags.update(scenario.tags)
        return sorted(list(tags))

    def get_scenario_names(self, feature: KarateFeature) -> list[str]:
        """Get list of scenario names."""
        return [s.name for s in feature.scenarios]

    def validate(self, feature: KarateFeature) -> list[str]:
        """
        Validate feature structure and return list of issues.

        Returns empty list if feature is valid.
        """
        issues = []

        if not feature.name:
            issues.append("Feature name is required")

        if not feature.scenarios:
            issues.append("Feature has no scenarios")

        for scenario in feature.scenarios:
            if not scenario.name:
                issues.append(f"Scenario at line {scenario.line_number} has no name")

            if not scenario.steps:
                issues.append(f"Scenario '{scenario.name}' has no steps")

            if scenario.is_outline and not scenario.examples:
                issues.append(f"Scenario Outline '{scenario.name}' has no Examples")

        return issues
