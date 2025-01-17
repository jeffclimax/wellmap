#!/usr/bin/env python3

import os
import wellmap
import shlex
import matplotlib.pyplot as plt

from docutils import nodes
from docutils.statemachine import StringList
from sphinx.util.docutils import SphinxDirective
from sphinx.util import logging

logger = logging.getLogger(__name__)

class Example(SphinxDirective):
    required_arguments = 1
    optional_arguments = 0
    has_content = True
    final_argument_whitespace = True
    option_spec = {
            'params': lambda x: x.split(','),
            'show': lambda x: int,
            'colors': lambda x: x,
            'no-figure': lambda x: x,
    }

    def run(self):
        rel_paths = shlex.split(self.arguments[0])
        example_rst = ""

        if not self.content:
            contents = [None] * len(rel_paths)
        else:
            contents = '\n'.join(self.content).split('--EOF--')

        if len(contents) != len(rel_paths):
            raise self.error(f"found {len(content)} TOML snippets, but {len(rel_paths)} paths.")

        toml_paths = []
        toml_abs_paths = []

        for rel_path, content in zip(rel_paths, contents):
            toml_path, toml_abs_path = self.env.relfn2path(rel_path)
            toml_paths.append(toml_path)
            toml_abs_paths.append(toml_abs_path)

            name = os.path.basename(toml_path)

            if content:
                update_toml_file(toml_abs_path, content)

            if not os.path.exists(toml_abs_path):
                raise self.error(f"no such file: {toml_path}")

            example_rst += f'''\
.. literalinclude:: /{toml_path}
    :language: toml
    :caption: :download:`{name} </{toml_path}>`
'''

        # Only make a figure for the last snippet.  
        if 'no-figure' not in self.options:
            i = self.options.get('show', 0)
            toml_path = toml_paths[i]
            toml_abs_path = toml_abs_paths[i]
            svg_path = change_ext(toml_path, '.svg')
            svg_abs_path = change_ext(toml_abs_path, '.svg')

            df, meta = wellmap.load(toml_abs_path, meta=True)

            if any_deps_stale(svg_abs_path, meta.dependencies):
                logger.info(f"[example] rendering: {svg_path}")
                params = self.options.get('params', [])
                if 'color' in self.options:
                    meta.style = self.options['color']
                fig = wellmap.show_df(df, params, style=meta.style)
                fig.savefig(svg_abs_path, bbox_inches='tight')
                plt.close(fig)

            example_rst += f'''\
.. figure:: /{svg_path}
'''
        example_str_list = StringList(example_rst.splitlines())

        wrapper = nodes.container(classes=['wellmap-example'])
        self.state.nested_parse(example_str_list, 0, wrapper)
        return [wrapper]

def change_ext(path, new_ext):
    return os.path.splitext(path)[0] + new_ext

def update_toml_file(toml_abs_path, content):
    # Don't write the file if its contents wouldn't change.  This is important, 
    # because otherwise we won't know whether or not the SVG file is stale.
    try:
        with open(toml_abs_path) as f:
            prev_content = f.read()
        if content == prev_content:
            return
    except FileNotFoundError:
        pass

    os.makedirs(os.path.dirname(toml_abs_path), exist_ok=True)
    with open(toml_abs_path, 'w') as f:
        f.write(content)

def any_deps_stale(svg_abs_path, toml_abs_paths):
    try:
        for toml_abs_path in toml_abs_paths:
            toml_mtime = os.path.getmtime(toml_abs_path)
            svg_mtime = os.path.getmtime(svg_abs_path)
            if toml_mtime > svg_mtime:
                return True

    except FileNotFoundError:
        return True

    return False

def setup(app):
    app.add_directive('example', Example)
