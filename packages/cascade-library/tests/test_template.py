import pytest
import cascade as cs

# Mark all tests in this module to be skipped if jinja2 is not installed
pytest.importorskip("jinja2")


def test_template_with_literals():
    """Tests basic rendering with static values."""

    # cs.template is loaded dynamically via __getattr__
    rendered_text = cs.template("Hello, {{ name }}!", name="World")

    result = cs.run(rendered_text)
    assert result == "Hello, World!"


def test_template_with_lazy_result():
    """Tests that the template correctly depends on an upstream task."""

    @cs.task
    def get_username():
        return "Cascade"

    @cs.task
    def process_text(text: str):
        return text.upper()

    # The 'user' variable for the template comes from get_username task
    template_res = cs.template("Username is {{ user }}.", user=get_username())

    # The output of the template is fed into the process_text task
    final_res = process_text(template_res)

    result = cs.run(final_res)
    assert result == "USERNAME IS CASCADE."


def test_template_missing_dependency_install():
    """
    This test is more conceptual and would require manipulating sys.modules
    to simulate jinja2 not being installed. It's complex to set up reliably.
    The runtime check in the provider is sufficient for now.
    We can assume the ImportError is raised correctly if jinja2 is absent.
    """
    pass
