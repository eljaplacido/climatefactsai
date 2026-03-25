"""
Integration tests for Claude Code/Flow templates
Tests template structure, variable validation, and agent coordination
"""

import json
import os
import pytest
from pathlib import Path


class TestTemplateStructure:
    """Test template JSON structure and required fields"""

    @pytest.fixture
    def template_dir(self):
        """Get path to templates directory"""
        return Path(__file__).parent.parent.parent / ".claude" / "templates"

    @pytest.fixture
    def templates(self, template_dir):
        """Load all templates"""
        templates = {}
        for template_file in template_dir.glob("*.json"):
            with open(template_file) as f:
                templates[template_file.stem] = json.load(f)
        return templates

    def test_all_templates_exist(self, template_dir):
        """Verify all expected templates exist"""
        expected_templates = [
            "checkpoint-refactor.json",
            "compliance-sweep.json",
            "doc-update.json",
            "multi-service-deploy.json"
        ]

        for template_name in expected_templates:
            assert (template_dir / template_name).exists(), \
                f"Template {template_name} not found"

    def test_template_required_fields(self, templates):
        """Verify all templates have required fields"""
        required_fields = ["name", "description", "version", "tags", "workflow", "variables"]

        for template_name, template in templates.items():
            for field in required_fields:
                assert field in template, \
                    f"Template {template_name} missing required field: {field}"

    def test_workflow_structure(self, templates):
        """Verify workflow section structure"""
        required_workflow_fields = ["preTask", "agents", "postTask"]

        for template_name, template in templates.items():
            workflow = template.get("workflow", {})
            for field in required_workflow_fields:
                assert field in workflow, \
                    f"Template {template_name} workflow missing field: {field}"

            # Verify agents is a list
            assert isinstance(workflow["agents"], list), \
                f"Template {template_name} agents must be a list"

            # Verify at least one agent
            assert len(workflow["agents"]) > 0, \
                f"Template {template_name} must have at least one agent"

    def test_agent_structure(self, templates):
        """Verify agent configuration structure"""
        required_agent_fields = ["type", "name", "task"]

        for template_name, template in templates.items():
            agents = template.get("workflow", {}).get("agents", [])

            for idx, agent in enumerate(agents):
                for field in required_agent_fields:
                    assert field in agent, \
                        f"Template {template_name} agent {idx} missing field: {field}"

    def test_variables_structure(self, templates):
        """Verify variables section structure"""
        for template_name, template in templates.items():
            variables = template.get("variables", {})

            for var_name, var_config in variables.items():
                assert "type" in var_config, \
                    f"Template {template_name} variable {var_name} missing type"
                assert "description" in var_config, \
                    f"Template {template_name} variable {var_name} missing description"

    def test_todos_structure(self, templates):
        """Verify todos section structure"""
        required_todo_fields = ["id", "content", "status", "priority"]

        for template_name, template in templates.items():
            todos = template.get("todos", [])

            for todo in todos:
                for field in required_todo_fields:
                    assert field in todo, \
                        f"Template {template_name} todo missing field: {field}"

                # Verify status is valid
                assert todo["status"] in ["pending", "in_progress", "completed"], \
                    f"Template {template_name} todo has invalid status: {todo['status']}"

    def test_checkpoints_structure(self, templates):
        """Verify checkpoints configuration"""
        for template_name, template in templates.items():
            checkpoints = template.get("checkpoints", {})

            assert "auto" in checkpoints, \
                f"Template {template_name} checkpoints missing 'auto' field"
            assert "labels" in checkpoints, \
                f"Template {template_name} checkpoints missing 'labels' field"
            assert "rollback_instructions" in checkpoints, \
                f"Template {template_name} checkpoints missing 'rollback_instructions' field"


class TestTemplateValidation:
    """Test template validation logic"""

    @pytest.fixture
    def template_dir(self):
        return Path(__file__).parent.parent.parent / ".claude" / "templates"

    def test_json_syntax_valid(self, template_dir):
        """Verify all templates have valid JSON syntax"""
        for template_file in template_dir.glob("*.json"):
            try:
                with open(template_file) as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                pytest.fail(f"Template {template_file.name} has invalid JSON: {e}")

    def test_variable_references(self, template_dir):
        """Verify variable placeholders match defined variables"""
        for template_file in template_dir.glob("*.json"):
            with open(template_file) as f:
                template = json.load(f)

            # Get defined variables
            defined_vars = set(template.get("variables", {}).keys())

            # Find variable references in agent tasks
            referenced_vars = set()
            for agent in template.get("workflow", {}).get("agents", []):
                task = agent.get("task", "")
                # Simple regex to find {{var}} patterns
                import re
                matches = re.findall(r'\{\{(\w+)\}\}', task)
                referenced_vars.update(matches)

            # Check memoryKey references
            for agent in template.get("workflow", {}).get("agents", []):
                memory_key = agent.get("memoryKey", "")
                matches = re.findall(r'\{\{(\w+)\}\}', memory_key)
                referenced_vars.update(matches)

            # Verify all referenced variables are defined
            undefined = referenced_vars - defined_vars
            assert len(undefined) == 0, \
                f"Template {template_file.name} has undefined variables: {undefined}"


class TestTemplateAgentTypes:
    """Test agent type references"""

    VALID_AGENT_TYPES = {
        "coder", "reviewer", "tester", "planner", "researcher",
        "code-analyzer", "system-architect", "api-docs",
        "security-manager", "cicd-engineer",
        "hierarchical-coordinator", "mesh-coordinator"
    }

    @pytest.fixture
    def templates(self):
        template_dir = Path(__file__).parent.parent.parent / ".claude" / "templates"
        templates = {}
        for template_file in template_dir.glob("*.json"):
            with open(template_file) as f:
                templates[template_file.stem] = json.load(f)
        return templates

    def test_valid_agent_types(self, templates):
        """Verify all agent types are valid"""
        for template_name, template in templates.items():
            agents = template.get("workflow", {}).get("agents", [])

            for agent in agents:
                agent_type = agent.get("type", "")
                assert agent_type in self.VALID_AGENT_TYPES, \
                    f"Template {template_name} uses invalid agent type: {agent_type}"


class TestTemplateIntegration:
    """Test template integration features"""

    @pytest.fixture
    def templates(self):
        template_dir = Path(__file__).parent.parent.parent / ".claude" / "templates"
        templates = {}
        for template_file in template_dir.glob("*.json"):
            with open(template_file) as f:
                templates[template_file.stem] = json.load(f)
        return templates

    def test_reasoningbank_integration(self, templates):
        """Verify ReasoningBank memory keys are properly formatted"""
        for template_name, template in templates.items():
            agents = template.get("workflow", {}).get("agents", [])

            for agent in agents:
                if "memoryKey" in agent:
                    memory_key = agent["memoryKey"]
                    assert memory_key.startswith("reasoningbank://"), \
                        f"Template {template_name} agent {agent['name']} has invalid memory key format"

    def test_checkpoint_enabled(self, templates):
        """Verify checkpoints are enabled for critical templates"""
        critical_templates = ["checkpoint-refactor", "compliance-sweep", "multi-service-deploy"]

        for template_name in critical_templates:
            if template_name in templates:
                template = templates[template_name]
                checkpoints = template.get("checkpoints", {})
                assert checkpoints.get("auto") is True, \
                    f"Critical template {template_name} must have auto checkpoints enabled"

    def test_hooks_integration(self, templates):
        """Verify hooks are properly configured"""
        for template_name, template in templates.items():
            agents = template.get("workflow", {}).get("agents", [])

            for agent in agents:
                if "hooks" in agent:
                    hooks = agent["hooks"]
                    assert isinstance(hooks, list), \
                        f"Template {template_name} agent {agent['name']} hooks must be a list"

                    valid_hooks = ["pre-task", "post-task", "post-edit", "notify"]
                    for hook in hooks:
                        assert hook in valid_hooks, \
                            f"Template {template_name} agent {agent['name']} has invalid hook: {hook}"

    def test_pre_post_tasks(self, templates):
        """Verify preTask and postTask commands are valid"""
        for template_name, template in templates.items():
            workflow = template.get("workflow", {})

            # Check preTask
            pre_tasks = workflow.get("preTask", [])
            assert isinstance(pre_tasks, list), \
                f"Template {template_name} preTask must be a list"

            # Verify git status is in preTask for safety
            pre_task_str = " ".join(pre_tasks)
            if "refactor" in template_name or "deploy" in template_name:
                assert "git status" in pre_task_str, \
                    f"Template {template_name} should include 'git status' in preTask"

            # Check postTask
            post_tasks = workflow.get("postTask", [])
            assert isinstance(post_tasks, list), \
                f"Template {template_name} postTask must be a list"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
