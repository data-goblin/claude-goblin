#!/usr/bin/env python3
"""
Self-audit Claude Code memory files.
Discovers files, analyses content coverage, and identifies gaps
in style, tone, workflow, and architecture documentation.
"""

import os
import re
import sys
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


# ============================================================================
# Content Categories and Detection Patterns
# ============================================================================

CONTENT_CATEGORIES = {
    "code_style": {
        "name": "Code Style",
        "patterns": [
            r"indent(ation)?[\s:]+\d", r"tabs?\s+(vs|or)\s+spaces?", r"\d+\s*spaces?\s+(indent|tab)",
            r"naming\s*(convention|pattern|style)", r"camel\s*case", r"snake\s*case",
            r"pascal\s*case", r"kebab\s*case", r"import\s*(order|sort|group)",
            r"comment\s*(style|format)", r"docstring", r"jsdoc",
            r"eslint", r"prettier", r"black\b", r"ruff\b", r"biome",
            r"trailing\s*comma", r"semicolon", r"quote\s*(style|single|double)"
        ],
        "questions": [
            "What indentation style do you use (tabs/spaces, width)?",
            "Any naming conventions for variables, functions, files?",
            "How should imports be ordered or grouped?",
            "What comment/documentation style do you prefer?"
        ]
    },
    "tone": {
        "name": "Tone & Output Style",
        "patterns": [
            r"(be\s+)?concise", r"(be\s+)?verbose", r"(be\s+)?brief", r"(be\s+)?detailed",
            r"response\s*(style|tone|length|format)", r"output\s*(style|format)",
            r"avoid\s*(bullet|list|header)", r"use\s+prose", r"minimal\s+format",
            r"(no|avoid|without)\s*emoji", r"casual\s+tone", r"formal\s+tone",
            r"british\s+english", r"american\s+english"
        ],
        "questions": [
            "How verbose should responses be (concise vs detailed)?",
            "Formatting preferences (minimal lists, prose, headers)?",
            "Should I use emojis or keep things plain?",
            "Formal or casual tone?"
        ]
    },
    "workflows": {
        "name": "Workflows & Commands",
        "patterns": [
            r"npm\s+(run\s+)?\w+", r"yarn\s+\w+", r"pnpm\s+\w+",
            r"make\s+\w+", r"cargo\s+(build|test|run|check)",
            r"go\s+(build|test|run)", r"python\s+-m\s+\w+",
            r"pytest\b", r"jest\b", r"vitest\b", r"mocha\b",
            r"docker\s+(build|run|compose)", r"kubectl\s+\w+",
            r"`[^`]*(build|test|lint|deploy|start|dev)[^`]*`",
            r"git\s+(flow|workflow)", r"branch(ing)?\s+(strategy|model)",
            r"commit\s*message\s*(format|convention)"
        ],
        "questions": [
            "What command builds the project?",
            "How do you run tests (unit, integration, e2e)?",
            "What's the lint/format command?",
            "Any deploy or CI/CD procedures I should know?"
        ]
    },
    "architecture": {
        "name": "Architecture & Structure",
        "patterns": [
            r"(src|lib|app|packages?|components?)/\w+",
            r"directory\s*(structure|layout)", r"folder\s*(structure|layout)",
            r"file\s*(structure|organisation|organization)",
            r"(design|architecture)\s*pattern", r"composition\s+over",
            r"state\s*management", r"redux\b", r"zustand\b", r"mobx\b",
            r"api\s*(route|endpoint|convention)", r"rest\s+api", r"graphql\b",
            r"database\s*(schema|model)", r"orm\b", r"prisma\b"
        ],
        "questions": [
            "Can you describe the directory structure?",
            "Where do key files live (components, utilities, config)?",
            "Any architectural patterns I should follow?",
            "How is state managed in this project?"
        ]
    }
}

VAGUE_PATTERNS = [
    (r"format\s+(code\s+)?properly", "What specific formatting rules?"),
    (r"follow\s+best\s+practices", "Which practices specifically?"),
    (r"be\s+consistent", "Consistent with what standard?"),
    (r"write\s+(good|clean|quality)\s+code", "What makes code 'good' here?"),
    (r"use\s+appropriate\s+names?", "What naming convention?"),
    (r"keep\s+it\s+simple", "Any specific simplicity guidelines?"),
    (r"document\s+(well|properly)", "What documentation style?")
]


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class MemoryFile:
    """Represents a discovered memory file."""
    path: Path
    file_type: str
    content: str = ""
    imports: list[str] = field(default_factory=list)
    line_count: int = 0
    category_coverage: dict = field(default_factory=dict)
    vague_instructions: list[tuple[str, str]] = field(default_factory=list)
    scope_issues: list[str] = field(default_factory=list)


@dataclass
class AuditResult:
    """Complete audit results."""
    project_path: Path
    memory_files: list[MemoryFile] = field(default_factory=list)
    missing_imports: list[tuple[str, str]] = field(default_factory=list)
    coverage_summary: dict = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)
    clarifying_questions: list[str] = field(default_factory=list)


# ============================================================================
# Discovery Functions
# ============================================================================

def find_memory_files(project_path: Path) -> list[MemoryFile]:
    """Discover all memory files in and above the project directory."""
    files = []
    
    current = project_path.resolve()
    while current != current.parent:
        for candidate in [
            current / "CLAUDE.md",
            current / ".claude" / "CLAUDE.md",
            current / "CLAUDE.local.md"
        ]:
            if candidate.exists():
                file_type = determine_file_type(candidate, project_path)
                files.append(analyse_file(candidate, file_type))
        
        # Check .claude/rules/ directory
        rules_dir = current / ".claude" / "rules"
        if rules_dir.exists() and rules_dir.is_dir():
            for rule_file in rules_dir.glob("*.md"):
                files.append(analyse_file(rule_file, "rule"))
        
        current = current.parent
    
    # Check user memory
    user_claude = Path.home() / ".claude" / "CLAUDE.md"
    if user_claude.exists():
        files.append(analyse_file(user_claude, "user"))
    
    # Find subtree memory files
    for root, dirs, filenames in os.walk(project_path):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', '__pycache__', 'dist', 'build']]
        
        if "CLAUDE.md" in filenames:
            subtree_file = Path(root) / "CLAUDE.md"
            if subtree_file.resolve() != (project_path / "CLAUDE.md").resolve():
                files.append(analyse_file(subtree_file, "subtree"))
    
    return files


def determine_file_type(file_path: Path, project_path: Path) -> str:
    """Determine the type of memory file."""
    if "CLAUDE.local.md" in str(file_path):
        return "local"
    if file_path.parent.name == "rules":
        return "rule"
    if file_path.resolve().parent == project_path.resolve() or \
       file_path.resolve().parent == (project_path / ".claude").resolve():
        return "project"
    return "parent"


# ============================================================================
# Analysis Functions
# ============================================================================

def analyse_file(file_path: Path, file_type: str) -> MemoryFile:
    """Analyse a memory file for content coverage."""
    mf = MemoryFile(path=file_path, file_type=file_type)
    
    try:
        mf.content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        mf.scope_issues.append(f"Could not read: {e}")
        return mf
    
    mf.line_count = mf.content.count("\n") + 1
    mf.imports = extract_imports(mf.content)
    mf.category_coverage = analyse_coverage(mf.content)
    mf.vague_instructions = find_vague_instructions(mf.content)
    mf.scope_issues = check_scope_issues(mf.content, file_type)
    
    return mf


def extract_imports(content: str) -> list[str]:
    """Extract @path imports from content."""
    content_no_blocks = re.sub(r"```[\s\S]*?```", "", content)
    content_clean = re.sub(r"`[^`]+`", "", content_no_blocks)
    
    imports = []
    for match in re.findall(r"@(~?[\w\-\./]+)", content_clean):
        if "/" in match or match.startswith("~"):
            imports.append(f"@{match}")
    
    return imports


def analyse_coverage(content: str) -> dict:
    """Check which content categories are covered."""
    content_lower = content.lower()
    coverage = {}
    
    for cat_id, cat_info in CONTENT_CATEGORIES.items():
        matches = []
        for pattern in cat_info["patterns"]:
            found = re.findall(pattern, content_lower)
            if found:
                matches.extend(found)
        
        coverage[cat_id] = {
            "name": cat_info["name"],
            "covered": len(matches) > 0,
            "strength": "strong" if len(matches) >= 3 else "weak" if matches else "none",
            "match_count": len(matches)
        }
    
    return coverage


def find_vague_instructions(content: str) -> list[tuple[str, str]]:
    """Find vague instructions that need clarification."""
    content_lower = content.lower()
    found = []
    
    for pattern, question in VAGUE_PATTERNS:
        if re.search(pattern, content_lower):
            match = re.search(pattern, content_lower)
            found.append((match.group(0), question))
    
    return found


def check_scope_issues(content: str, file_type: str) -> list[str]:
    """Check for content in wrong scope."""
    issues = []
    content_lower = content.lower()
    
    if file_type == "project":
        personal_indicators = ["i prefer", "i like", "my personal", "just for me"]
        for indicator in personal_indicators:
            if indicator in content_lower:
                issues.append(f"Personal preference in shared file: '{indicator}' → consider .local.md")
                break
    
    if file_type == "local":
        team_indicators = ["team standard", "we use", "our convention", "project-wide"]
        for indicator in team_indicators:
            if indicator in content_lower:
                issues.append(f"Team standard in local file: '{indicator}' → consider promoting to project rules")
                break
    
    return issues


def validate_imports(memory_files: list[MemoryFile], project_path: Path) -> list[tuple[str, str]]:
    """Check that all imports resolve."""
    missing = []
    
    for mf in memory_files:
        base_dir = mf.path.parent
        
        for imp in mf.imports:
            imp_path = imp[1:]
            
            if imp_path.startswith("~"):
                resolved = Path.home() / imp_path[2:]
                if not resolved.exists():
                    missing.append((str(mf.path), imp))
            elif imp_path.startswith("/"):
                resolved = Path(imp_path)
                if not resolved.exists():
                    missing.append((str(mf.path), imp))
            else:
                # Try relative to file first, then relative to project root
                resolved_from_file = base_dir / imp_path
                resolved_from_project = project_path / imp_path
                
                if not resolved_from_file.exists() and not resolved_from_project.exists():
                    missing.append((str(mf.path), imp))
    
    return missing


def aggregate_coverage(memory_files: list[MemoryFile]) -> dict:
    """Aggregate coverage across all files."""
    combined = {cat_id: {"name": info["name"], "covered": False, "sources": []} 
                for cat_id, info in CONTENT_CATEGORIES.items()}
    
    for mf in memory_files:
        for cat_id, cov in mf.category_coverage.items():
            if cov["covered"]:
                combined[cat_id]["covered"] = True
                combined[cat_id]["sources"].append(str(mf.path.name))
    
    return combined


def generate_questions(coverage: dict, vague_all: list) -> list[str]:
    """Generate clarifying questions for gaps."""
    questions = []
    
    for cat_id, cov in coverage.items():
        if not cov["covered"]:
            cat_questions = CONTENT_CATEGORIES[cat_id]["questions"]
            questions.append(f"**{cov['name']}**: {cat_questions[0]}")
    
    for vague_text, question in vague_all[:3]:
        questions.append(f"**Clarify**: Found '{vague_text}' — {question}")
    
    return questions


# ============================================================================
# Reporting
# ============================================================================

def print_report(result: AuditResult) -> None:
    """Print audit report."""
    print(f"\n{'='*60}")
    print("MEMORY AUDIT REPORT")
    print(f"Project: {result.project_path}")
    print(f"{'='*60}\n")
    
    # Files
    print("FILES DISCOVERED:")
    print("-" * 40)
    if not result.memory_files:
        print("  (none)")
    else:
        for mf in result.memory_files:
            icon = "📄" if mf.file_type in ("project", "rule") else "📝" if mf.file_type == "local" else "📁"
            print(f"  {icon} [{mf.file_type:7}] {mf.path.name} ({mf.line_count} lines)")
            if mf.imports:
                print(f"              imports: {', '.join(mf.imports)}")
    
    # Coverage
    print(f"\nCONTENT COVERAGE:")
    print("-" * 40)
    for cat_id, cov in result.coverage_summary.items():
        status = "✓" if cov["covered"] else "✗"
        sources = f" ({', '.join(cov['sources'])})" if cov["sources"] else ""
        print(f"  {status} {cov['name']}{sources}")
    
    # Issues
    all_vague = []
    all_scope = []
    for mf in result.memory_files:
        all_vague.extend(mf.vague_instructions)
        all_scope.extend([(mf.path.name, issue) for issue in mf.scope_issues])
    
    if all_vague or all_scope or result.missing_imports:
        print(f"\nISSUES:")
        print("-" * 40)
        for vague_text, question in all_vague:
            print(f"  ⚠ Vague: '{vague_text}'")
        for source, issue in all_scope:
            print(f"  ⚠ Scope ({source}): {issue}")
        for source, imp in result.missing_imports:
            print(f"  ✗ Missing import: {imp} (from {source})")
    
    # Questions
    if result.clarifying_questions:
        print(f"\nCLARIFYING QUESTIONS:")
        print("-" * 40)
        for q in result.clarifying_questions:
            print(f"  → {q}")
    
    print(f"\n{'='*60}\n")


def output_json(result: AuditResult) -> str:
    """Output as JSON."""
    data = {
        "project": str(result.project_path),
        "files": [
            {
                "path": str(mf.path),
                "type": mf.file_type,
                "lines": mf.line_count,
                "imports": mf.imports,
                "coverage": mf.category_coverage,
                "vague": mf.vague_instructions,
                "scope_issues": mf.scope_issues
            }
            for mf in result.memory_files
        ],
        "coverage_summary": result.coverage_summary,
        "missing_imports": [{"source": s, "import": i} for s, i in result.missing_imports],
        "clarifying_questions": result.clarifying_questions
    }
    return json.dumps(data, indent=2)


# ============================================================================
# Main
# ============================================================================

def audit(project_path: Path) -> AuditResult:
    """Run complete audit."""
    result = AuditResult(project_path=project_path)
    
    result.memory_files = find_memory_files(project_path)
    result.missing_imports = validate_imports(result.memory_files, project_path)
    result.coverage_summary = aggregate_coverage(result.memory_files)
    
    all_vague = []
    for mf in result.memory_files:
        all_vague.extend(mf.vague_instructions)
    
    result.clarifying_questions = generate_questions(result.coverage_summary, all_vague)
    
    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: audit_memory.py <project-path> [--json]")
        sys.exit(1)
    
    project_path = Path(sys.argv[1])
    json_output = "--json" in sys.argv
    
    if not project_path.exists():
        print(f"Error: Path does not exist: {project_path}")
        sys.exit(1)
    
    result = audit(project_path)
    
    if json_output:
        print(output_json(result))
    else:
        print_report(result)


if __name__ == "__main__":
    main()
