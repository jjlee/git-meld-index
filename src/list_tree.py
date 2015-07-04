# Based on code I contributed to nose -- John Lee

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import itertools
import os
import re


skip_pattern = r"(?:\.svn)|(?:[^.]+\.py[co])|(?:.*~)|(?:.*\$py\.class)|(?:__pycache__)"


def ls_tree(dir_path="",
            skip_pattern=skip_pattern,
            indent="|-- ", branch_indent="|   ",
            last_indent="`-- ", last_branch_indent="    "):
    return "\n".join(_ls_tree_lines(dir_path, skip_pattern,
                                    indent, branch_indent,
                                    last_indent, last_branch_indent)) + "\n"


def _ls_tree_lines(dir_path, skip_pattern,
                   indent, branch_indent, last_indent, last_branch_indent):
    if dir_path == "":
        dir_path = os.getcwd()

    names = os.listdir(dir_path)
    names.sort()
    dirs, nondirs = [], []
    for name in names:
        if re.match(skip_pattern, name):
            continue
        full_path = os.path.join(dir_path, name)
        if not os.path.islink(full_path) and os.path.isdir(full_path):
            dirs.append(name)
        else:
            nondirs.append(name)

    # list non-directories first
    entries = list(itertools.chain([(name, False) for name in nondirs],
                                   [(name, True) for name in dirs]))
    def ls_entry(name, is_dir, ind, branch_ind):
        path = os.path.join(dir_path, name)
        if is_dir:
            if not os.path.islink(path):
                yield ind + name + "/"
                subtree = _ls_tree_lines(path, skip_pattern,
                                         indent, branch_indent,
                                         last_indent, last_branch_indent)
                for x in subtree:
                    yield branch_ind + x
        else:
            if os.path.islink(path):
                yield ind + name + " -> " + os.readlink(path)
            else:
                yield ind + name
    for name, is_dir in entries[:-1]:
        for line in ls_entry(name, is_dir, indent, branch_indent):
            yield line
    if entries:
        name, is_dir = entries[-1]
        for line in ls_entry(name, is_dir, last_indent, last_branch_indent):
            yield line
