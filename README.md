# git-meld-index

git-meld-index runs [meld](http://meldmerge.org/) -- or any other git
difftool (kdiff3, diffuse, etc.) -- to allow you to interactively
stage changes to the git index (also known as the git staging area).

This is similar to the functionality of `git add -p`, and `git add
--interactive`.  In some cases meld is easier / quicker to use than
`git add -p` or the staging feature in tools like `git gui`.  That's
because meld allows you, for example, to:

* see more context
* see intra-line diffs
* edit by hand and see 'live' diff updates (updated after every keypress)
* navigate to a change without saying 'n' to every change you want to skip


## Requirements

Python 3.9 or newer.

git-meld-index is probably a little bit fragile to what git version you have
(fragile as in maybe breaking completely sometimes, not fragile as in subtle
bugs).  CI builds against git versions from the Arch Linux rolling release (git
2.41.0 at the time of writing), and Debian bullseye (git 2.30.2).  If you notice
it's not working for some other old git version, please create an issue.

I have only tested on Linux.  Probably it isn't working on anything else (should
be easy to fix for other unix-y systems -- I'd guess it will only fail because
of its use of the `-T` option of the `ln` command).


## Install

To install via [uv](https://github.com/astral-sh/uv):

```
uv tool install --from https://github.com/jjlee/git-meld-index/archive/0.2.6.zip git-meld-index
```

To install via [pipx](https://github.com/pypa/pipx):

```
pipx install https://github.com/jjlee/git-meld-index/archive/0.2.6.zip
```

### Installing via pip

```
pip install https://github.com/jjlee/git-meld-index/archive/0.2.6.zip
```

### Installing other versions

To install from the master branch:

```
uv tool install https://github.com/jjlee/git-meld-index/archive/0.2.5.zip git-meld-index
```

To install a specific release:

```
uv tool install --from https://github.com/jjlee/git-meld-index/archive/<release tag here>.zip git-meld-index
```

### Running without installation

If you want to avoid installers you can clone the repo and run the
script directly:

```
git clone https://github.com/jjlee/git-meld-index.git
cd git-meld-index
env PATH="$PATH":bin python src/git_meld_index.py
```

## Configuration

Configuration is the same as for [git difftool][git-difftool-config-docs].

Quick start: run:

```
git config --global diff.tool meld
```

  [git-difftool-config-docs]: http://git-scm.com/docs/git-difftool#_config_variables


## Usage

In a git repository, run:

```
git meld-index
```

You'll see meld (or your configured git difftool) pop up with:

LEFT: temporary directory containing files copied from your working
tree

RIGHT: temporary directory with the contents of the index.  This also
includes files that are not yet in the index but are modified or
untracked in the working copy -- in this case you'll see the file
contents from HEAD.

Edit the index (right hand side) until happy.  Remember to save when
needed.

When you're done, close meld, and git-meld-index will update the index
to match the contents of the temporary directory on the right hand
side of meld that you just edited.

At present changes to the left hand side (working copy) are discarded.

For more information see the manpage:

```
git meld-index --help
```

## Important Caveats

1. Be a bit cautious if you have changes in your index that you've
removed from your working tree (this is not a common thing to do and I
don't personally do this much).

2. If this functionality gets implemented in git itself I'll likely
stop maintaining this.  I have no involvement with development of git,
but I'd guess it's not unlikely somebody might add a 'git addtool'.

3. Command line usage and behaviour are subject to change.


## Ideas

Patches welcome.

It would make sense to add support for the equivalent of `git reset
-p`.  One way to do this would be a 3-way diff with from left to
right: working tree, index, HEAD.  Another way would be a --reset
switch to do a 2-way diff from left to right: HEAD, index.  It might
be best to have both options available.

It would make sense to be able to update the view of the working copy
also (by copying back edited files from the temporary directory into
the working copy).  This is a bit riskier (bugs could more easily
cause code loss) so would need more comprehensive automated tests.

Git submodules are ignored.  This could probably be improved
(git-difftool does something with these).

Symlinks are not treated specially at present.  They could be treated
the same way as git-difftool does: writing a file containing the link
target.  Then the link could be edited in meld and updated by
git-meld-index to point to the edited link target.

It would probably make sense to implement updating from arbitrary
commits and arbitrary directories.


## FAQ

Q. Why not symlink files from the working copy?  Then you could edit
those files also.

A. Because that would not allow using the "Copy to right" feature of
meld (on e.g. untracked or modified files).

Q. How can I abort my changes?

A. Type Control-C at the command line from which you launched `git
meld-index`, or close meld and select "Close without Saving". For
`vimdiff` you can type `:cq` to quit with abort.

Q. Why not just use &lt;favourite staging tool&gt;?

A. Different tools have different pros and cons.  You should use what
works best for you for a given task!  However, I do find tools like
meld have some advantages -- see the list at the top of this README
for some of them.  Try it and see what works for you.
