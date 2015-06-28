#!/usr/bin/env python

import ast
import codecs

from setuptools import setup


def read_text(path):
    with codecs.open(path, "r", "utf-8") as fh:
        return fh.read()


def read_version(path):
    with open(path) as fh:
        for line in fh:
            stripped = line.strip()
            if stripped == "" or stripped.startswith("#"):
                continue
            elif line.startswith("from __future__ import"):
                continue
            else:
                if not line.startswith("__version__ = "):
                    raise Exception("Can't find __version__ line in " + path)
                break
        else:
            raise Exception("Can't find __version__ line in " + path)
        _, _, quoted = line.rstrip().partition("= ")
        return ast.literal_eval(quoted)


classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
    "Operating System :: POSIX",
    "Programming Language :: Python",
    # "Programming Language :: Python :: 3",  # TODO
    "Topic :: Software Development :: Version Control",
]


scripts = [
    "bin/git-meld-index-run-merge-tool",
]


setup(
    name="git-meld-index",
    url='https://github.com/jjlee/git-meld-index',

    author='John Lee',
    author_email='jjl@pobox.com',
    classifiers=classifiers,
    data_files=[("share/man/man1", ["doc/git-meld-index.1"])],
    description="Like git add -p but with meld (or any difftool)",
    license="GPL",
    long_description=read_text("README.md"),
    package_dir={"": "src"},
    platforms=["any"],
    py_modules=["git_meld_index"],
    scripts=scripts,
    version=read_version("src/git_meld_index.py"),
    zip_safe=False,

    entry_points={
        "console_scripts": [
            "git-meld-index = git_meld_index:main",
        ],
    }
)
