"""Jinja2 environment configured for TeX templates.

LaTeX uses ``{`` and ``}`` for its own grouping, so Jinja2's default
``{{ ... }}`` and ``{% ... %}`` delimiters would clash with every line
of TeX.  We swap to LaTeX-safe delimiters instead::

    <<% statement %>>
    << expression >>
    <% comment %>

A ``tex`` escape filter and a ``num`` number-formatting filter are
registered globally.
"""
from __future__ import annotations

import importlib.resources as ir
from pathlib import Path

import jinja2


def templates_dir() -> Path:
    """Resolve the packaged templates/ folder on disk (shared by every report)."""
    with ir.as_file(ir.files("powerpy.output").joinpath("templates")) as p:
        return Path(p)


def escape_tex(s) -> str:
    """Escape user text so pdflatex never breaks on it.

    Handles the seven canonical specials plus backslash and tilde.
    """
    if s is None:
        return ""
    s = str(s)
    # The backslash, tilde and caret escapes themselves contain braces, so we
    # cannot do naive sequential .replace() (the later "{"/"}" passes would
    # double-escape them).  Map every special to a unique placeholder first,
    # then expand the placeholders in a final pass.
    replacements = [
        ("\\", "\0BSL\0",  r"\textbackslash{}"),
        ("&",  "\0AMP\0",  r"\&"),
        ("%",  "\0PCT\0",  r"\%"),
        ("$",  "\0DLR\0",  r"\$"),
        ("#",  "\0HSH\0",  r"\#"),
        ("_",  "\0USC\0",  r"\_"),
        ("{",  "\0LBR\0",  r"\{"),
        ("}",  "\0RBR\0",  r"\}"),
        ("~",  "\0TLD\0",  r"\textasciitilde{}"),
        ("^",  "\0CRT\0",  r"\textasciicircum{}"),
    ]
    for char, placeholder, _ in replacements:
        s = s.replace(char, placeholder)
    for _, placeholder, latex in replacements:
        s = s.replace(placeholder, latex)
    return s


def num(x, fmt: str = ".3f") -> str:
    """Numeric formatting filter -- friendly to None / NaN."""
    if x is None:
        return "--"
    try:
        f = float(x)
    except (TypeError, ValueError):
        return escape_tex(x)
    if f != f:                        # NaN
        return "--"
    return format(f, fmt)


def make_environment(template_dirs: list[Path]) -> jinja2.Environment:
    """Return a Jinja2 environment configured for TeX rendering."""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader([str(d) for d in template_dirs]),
        block_start_string="<<%",
        block_end_string="%>>",
        variable_start_string="<<",
        variable_end_string=">>",
        comment_start_string="<%",
        comment_end_string="%>",
        # NB: no line_statement_prefix -- TeX uses '%' freely for
        # comments and assigning a Jinja line-statement prefix collides
        # with it.  Use <<% ... %>> for all statements instead.
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,                  # tex is not html
        keep_trailing_newline=True,
        undefined=jinja2.StrictUndefined,  # fail loudly on typos
    )
    env.filters["tex"] = escape_tex
    env.filters["num"] = num
    return env
