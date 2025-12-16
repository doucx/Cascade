from cascade.spec.task import task
from cascade.providers import LazyFactory

try:
    import jinja2
except ImportError:
    jinja2 = None


class TemplateProvider:
    name = "template"

    def create_factory(self) -> LazyFactory:
        if jinja2 is None:
            raise ImportError(
                "The 'jinja2' library is required to use the template provider. "
                "Please install it with: pip install cascade-py[template]"
            )
        return render_template


@task(name="template")
def render_template(template_string: str, **context) -> str:
    """
    Renders a Jinja2 template string with the provided context.

    Args:
        template_string: The Jinja2 template string.
        **context: Keyword arguments to be used as variables in the template.
                   These can be literals or LazyResults.

    Returns:
        The rendered string.
    """
    template = jinja2.Template(template_string)
    return template.render(**context)
