import glob
import os
import re

from odoo.tests import TransactionCase, tagged

MODEL_LITERAL_RE = re.compile(
    r"""\b(?:self|request|\w+)\.env\[\s*["']([\w.]+)["']\s*\]"""
)
# Models from non-required addons that are intentionally referenced by a
# literal. Keep this empty and justify every addition with a comment.
OPTIONAL_MODELS = frozenset()

MODULE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCANNED_SUBDIRS = ("models", "wizard", "controllers")


@tagged("post_install", "-at_install")
class TestModelNameLiterals(TransactionCase):
    def test_all_self_env_literals_resolve_to_registered_models(self):
        """Every ``<var>.env["..."]``/``<var>.env['...']`` literal (e.g.
        ``self.env[...]`` or ``request.env[...]``) in ``models/``,
        ``wizard/`` and ``controllers/`` (scanned recursively) MUST
        reference a model present in the registry after install, or be
        explicitly listed in OPTIONAL_MODELS.

        This is the permanent regression gate for model renames (e.g. the
        ``.oca`` suffix used by this module's OCA-derived models): any stale
        literal left after a rename fails here instead of surfacing as a
        runtime ``KeyError`` deep in a report action.

        Blind spot: dynamic lookups such as
        ``report.custom_handler_model_name or "..."``
        (``models/account_move.py:360``) build the model name from a
        variable/expression rather than a string literal, so the regex
        above cannot see them. That fallback branch is covered separately
        by
        ``TestAccountMoveTaxClosing.test_refresh_tax_entry_uses_fallback_handler``
        in ``tests/test_account_move.py``.
        """
        misses = []
        for subdir in SCANNED_SUBDIRS:
            pattern = os.path.join(MODULE_ROOT, subdir, "**", "*.py")
            for path in sorted(glob.glob(pattern, recursive=True)):
                with open(path, encoding="utf-8") as source_file:
                    text = source_file.read()
                for match in MODEL_LITERAL_RE.finditer(text):
                    model_name = match.group(1)
                    if model_name in self.env.registry or model_name in OPTIONAL_MODELS:
                        continue
                    line_number = text[: match.start()].count("\n") + 1
                    misses.append(f"{path}:{line_number}: {model_name!r}")

        self.assertFalse(
            misses,
            "Found self.env[...] literal(s) referencing model(s) absent from "
            "the registry (file:line: literal):\n" + "\n".join(misses),
        )
