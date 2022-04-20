# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys

from enum_tools.documentation import document_enum

from magmatic import __author__, __version__
import magmatic.enums as magmatic_enums

sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('..'))

for attr in magmatic_enums.__all__:
    document_enum(getattr(magmatic_enums, attr))

# -- Project information -----------------------------------------------------

project = 'magmatic'
copyright = '2022 - present, ' + __author__
author = __author__

# The full version, including alpha/beta/rc tags
release = __version__


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.extlinks',
    'sphinx.ext.intersphinx',
    'sphinx.ext.napoleon',
    'enum_tools.autoenum',
]

autodoc_typehints = 'none'
napoleon_google_docstring = False
napoleon_numpy_docstring = True

# Add any paths that contain templates here, relative to this directory.
templates_path = []

rst_prolog = """
.. |coro| replace:: This function is a |coroutine_link|_.
.. |enum| replace:: This is an |enum_link|_.
.. |coroutine_link| replace:: *coroutine*
.. |enum_link| replace:: *enum*
.. _coroutine_link: https://docs.python.org/3/library/asyncio-task.html#coroutine
.. _enum_link: https://docs.python.org/3/library/enum.html#enum.Enum
"""

intersphinx_mapping = {
    'py': ('https://docs.python.org/3', None),
    'aio': ('https://docs.aiohttp.org/en/stable/', None),
    'discord': ('https://discordpy.readthedocs.io/en/master/', None),
    'dpy': ('https://discordpy.readthedocs.io/en/master/', None),
}

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []

pygments_style = "friendly"


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'furo'

html_theme_options = {}



# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# html_static_path = ["./_static"]
