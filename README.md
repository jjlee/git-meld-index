# git-meld-index

This is new code, please exercise caution (See Important Caveats below).

git-meld-index runs [meld](http://meldmerge.org/) -- or any other git
difftool (kdiff3, diffuse, etc.) -- to allow you to interactively
stage changes to the git index (also known as the git staging area).

This is similar to the functionality of `git add -p`, and `git add
--interactive`.  In some cases meld is easier / quicker to use than
`git add -p`.  That's because meld allows you, for example, to:

* see more context
* see intra-line diffs
* edit by hand and see 'live' diff updates (updated after every keypress)
* navigate to a change without saying 'n' to every change you want to skip


## Configuration

Configuration is the same as for git difftool.  See the [git docs][git-docs]

  [git-docs]: https://git-scm.com/documentation


## Requirements

I'm using git 1.9.1 and meld 1.8.4.  I expect later versions will
work.

There is no support for MS Windows.  I have only tested on Linux but
it should work on BSDs or OS X.


## Install

```
pip install https://github.com/jjlee/git-meld-index/archive/master.zip
```

Or for a specific release:

```
pip install https://github.com/jjlee/git-meld-index/archive/0.1.0.zip
```


## Usage

In a git repository, run:

```
git meld-index
```

You'll see meld (or your configured git difftool) pop up with:

LEFT: temporary directory contining files copied from your working
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


## Important Caveats

Patches welcome.

1. This is new, beta quality code and will have bugs.

For example, the following have not received any attention whatsoever:

* In-progress merges and rebases
* Symbolic links
* Git submodules

File moves haven't received much attention either.  There are probably
other cases which haven't received proper testing also.

Code loss is conceivable but unlikely since it only changes the index,
not the working tree, and changes in the index are normally present
also in the working tree.  You should be a bit more cautious if you
have changes in your index that you've removed from your working tree
(this is not a common thing to do).

I expect but haven't tested that submodules are ignored, and symlinks,
file moves, and in-progress merges and rebases are not treated
specially, which is probably at least somewhat reasonable.

2. If this functionality gets implemented in git itself I'll likely
stop maintaining this.  I have no involvement with development of git,
but I'd guess it's not unlikely somebody might add a 'git addtool'.

3. Command line usage and behaviour are subject to change.


## Less Important Caveats

Again, patches welcome.

It would make sense to add support for the equivalent of `git reset
-p`.  One way to do this would be a 3-way diff with from left to
right: working tree, index, HEAD.  Another way would be a --reset
switch to do a 2-way diff from left to right: HEAD, index.  It might
be best to have both options available.

It would make sense to be able to update the view of the working copy
also (by copying back edited files from the temporary directory into
the working copy).  This is a bit riskier (bugs could more easily
cause code loss) so I don't want to implement it until it has seen
some use and has more comprehensive automated tests.

Git submodules are ignored.  This could probably be improved
(git-difftool does something with these).

Possibly symlinks should be treated the same way as git-difftool does
(writing a file containing the hash of the link target, I think).

It would probably make sense to implement updating from arbitrary
commits and arbitrary directories.


## FAQ

Q. Why not symlink files from the working copy?  Then you could edit
those files also.

A. Because that would not allow using the "Copy to right" feature of
meld (on e.g. untracked or modified files).


John Lee, 2015-06
jjl@pobox.com
