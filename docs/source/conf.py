import os
import sys

# Путь к корневой директории проекта
sys.path.insert(0, os.path.abspath('../..'))

# Проект и автор
project = 'Design Zavod Bot' 
copyright = '2024, Design Zavod'
author = 'Design Zavod'
release = '0.1'

# Язык
language = 'ru'

# Расширения Sphinx
extensions = [
    'sphinx.ext.duration',
    'sphinx.ext.doctest',
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.intersphinx',
    'sphinx.ext.napoleon',  # Поддержка Google/NumPy docstring
    'autoapi.extension',    # Автогенерация API
]

# Настройки autoapi
autoapi_dirs = ['../../client', '../../admin', '../../cmds', '../../data', '../../utils'] # Путь к исходному коду бота
autoapi_ignore = ['*/__pycache__/*', '*/tests/*']  # Игнорировать кэш, тесты и все .py напрямую (только подмодули)
autoapi_add_toctree_entry = True  # Автоматически добавлять в toctree 
autoapi_options = ['members', 'undoc-members', 'private-members', 'show-inheritance']  # Подробности

# Intersphinx
intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
    'sphinx': ('https://www.sphinx-doc.org/en/master/', None),
}
intersphinx_disabled_domains = ['std']

# Пути и шаблоны
templates_path = ['_templates']
exclude_patterns = []
source_suffix = '.rst'
master_doc = 'index'

# HTML-тема
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

# EPUB
epub_show_urls = 'footnote'