from typing import Any

import jinja2
from jinja2.sandbox import SandboxedEnvironment


class PromptRenderError(Exception):
    """Raised when prompt template rendering fails."""

    pass


class SandboxedPromptRenderer:
    """Renders prompt templates safely using Jinja2 SandboxedEnvironment."""

    def __init__(self):
        # Configure sandboxed environment with strict undefined handling
        self.env = SandboxedEnvironment(
            autoescape=False,
            undefined=jinja2.StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_str: str, variables: dict[str, Any]) -> str:
        """
        Safely render template string with input variables.
        Raises PromptRenderError if undefined variables or syntax errors occur.
        """
        try:
            template = self.env.from_string(template_str)
            return template.render(**variables)
        except jinja2.UndefinedError as exc:
            raise PromptRenderError(f"Missing required prompt input variable: {exc}") from exc
        except jinja2.TemplateSyntaxError as exc:
            raise PromptRenderError(
                f"Template syntax error at line {exc.lineno}: {exc.message}"
            ) from exc
        except Exception as exc:
            raise PromptRenderError(f"Failed to render prompt: {exc}") from exc


_default_renderer = SandboxedPromptRenderer()


def render_prompt(template_str: str, variables: dict[str, Any]) -> str:
    """Helper to render a prompt with variables."""
    return _default_renderer.render(template_str, variables)
