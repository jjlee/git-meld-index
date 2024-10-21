# The following line has to be the first non-blank / non-comment line after the
# last __future__ import, for setup.py to read it.
__version__ = "0.0.0"

from dataclasses import dataclass
import argparse
import atexit
import functools
import itertools
import logging
import os
import pprint
import shlex
import shutil
import subprocess
import sys
import tempfile


# This module exports no public API
__all__ = []


log = logging.getLogger()


class UnknownURISchemeError(ValueError):

    pass


class CalledProcessError(subprocess.CalledProcessError):
    def __init__(self, returncode, cmd, output=None, stderr_output=None):
        subprocess.CalledProcessError.__init__(self, returncode, cmd, output)
        self.stderr_output = stderr_output

    def __str__(self):
        return """\
Command %r returned non-zero exit status %d:
stdout:
%s
stderr:
%s
""" % (self.cmd, self.returncode, self.output, self.stderr_output)


def in_dir(dir_path):
    return ["sh", "-c", 'cd "$1" && shift && exec "$@"', "inline_cd", dir_path]


def try_cmd(env, args):
    try:
        env.cmd(args)
    except CalledProcessError:
        return False
    else:
        return True


class BasicEnv:

    """An environment in which to run a program.
    """

    def cmd(self, args, input=None, tty=False):
        """Run a program, read its output and wait for it to exit.

        Args:
            input (bytes): data to send to program's stdin
            tty (bool): program requires a tty to run correctly (e.g. vimdiff).
              In this case, input is ignored and output is not read.
        """
        if tty:
            process = subprocess.Popen(args)
            process.wait()
        else:
            if input is not None:
                stdin = subprocess.PIPE
            else:
                stdin = None
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=stdin)
            output, stderr_output = process.communicate(input)
            retcode = process.poll()
            if retcode:
                raise CalledProcessError(retcode, args, output, stderr_output)
            process.stdout_output = output
            process.stderr_output = stderr_output
        return process

    @classmethod
    def make_readable(cls):
        env = cls()
        return ReadableEnv(env, env)


class ReadableEnv:

    """An env that supports .read_cmd

    If you run all commands that might have side effects using .cmd, and all
    other commands using .read_cmd, then --pretend (i.e. NullWrapper) will work
    correctly but you can still read information from the env even with
    --pretend in effect (e.g. use cat to read file contents).
    """

    def __init__(self, env, read_env):
        self._env = env
        self._read_env = read_env

    def cmd(self, args, input=None, tty=False):
        return self._env.cmd(args, input, tty)

    def read_cmd(self, args, input=None, tty=False):
        """Run a program as for .cmd(), but for use by side effect-free commands."""
        return self._read_env.cmd(args, input, tty)

    def wrap(self, wrapper):
        """Return a ReadableEnv wrapped with given wrapper.

        Args:
            wrapper (callable): An env wrapper

        An env wrapper takes an env and returns an env.
        """
        return type(self)(wrapper(self._env), wrapper(self._read_env))


class PrefixCmdEnv:

    def __init__(self, prefix_cmd, env):
        self._prefix_cmd = prefix_cmd
        self._env = env

    def cmd(self, args, input=None, tty=False):
        return self._env.cmd(self._prefix_cmd + args, input, tty)

    @classmethod
    def make_readable(cls, prefix_cmd, readable_env):
        return readable_env.wrap(functools.partial(cls, prefix_cmd))


class VerboseWrapper:

    def __init__(self, env):
        self._env = env

    def cmd(self, args, input=None, tty=False):
        if input is not None:
            print("input:")
            print(input)
        pprint.pprint(args)
        return self._env.cmd(args, input, tty)

    @classmethod
    def make_readable(cls, readable_env):
        return readable_env.wrap(cls)


class NullWrapper:

    def __init__(self, env):
        self._env = env

    def cmd(self, args, input=None, tty=False):
        return self._env.cmd(["true"])

    @classmethod
    def make_readable(cls, readable_env):
        return ReadableEnv(env=NullWrapper(readable_env), read_env=readable_env)


def shell_escape(args):
    return " ".join(shlex.quote(arg) for arg in args)


class WorkArea:

    def __init__(self, env, work_dir):
        self._env = env
        self._work_dir = work_dir

    def _write(self, view):
        suggested_dir = os.path.join(self._work_dir, view.label)
        self._env.cmd(["mkdir", "-p", suggested_dir])
        dir_ = view.write(self._env, suggested_dir)
        if dir_ is None:
            dir_ = suggested_dir
        return dir_

    def _meld(self, left_dir, right_dir, tool, extcmd):
        # usually working tree on left, index on right
        env = PrefixCmdEnv.make_readable(in_dir(self._work_dir), self._env)
        if tool:
            env = PrefixCmdEnv.make_readable(
                ["env", "GIT_DIFF_TOOL=" + tool], env)
        cmd = extcmd if extcmd is not None else "git-meld-index-run-merge-tool"
        env.cmd([cmd, left_dir, right_dir], tty=True)

    def _apply(self, view, dir_):
        view.apply(self._env, dir_)

    def meld(self, left_view, right_view, tool=None, extcmd=None):
        left_dir = self._write(left_view)
        right_dir = self._write(right_view)
        self._meld(left_dir, right_dir, tool, extcmd)
        self._apply(left_view, left_dir)
        self._apply(right_view, right_dir)


@dataclass
class DiffRecord:
    mode_after: str
    mode_before: str
    hash_after: str
    hash_before: str
    status: str
    path: str


def pairwise(iterable):
    iter_ = iter(iterable)
    return zip(iter_, iter_)


def parse_raw_diff(diff, path):
    mode_after, mode_before, hash_after, hash_before, status = diff.split(" ")
    mode_after = mode_after.removeprefix(":")
    return DiffRecord(
        mode_after, mode_before, hash_after, hash_before, status, path)


def iter_diff_records(repo_env, cmd):
    process = repo_env.read_cmd(cmd)
    parts = [part.decode() for part in process.stdout_output.split(b"\0")]
    assert parts[-1] == ""
    for diff, path in pairwise(parts[:-1]):
        yield parse_raw_diff(diff, path)


def iter_diff_records_undeleted(repo_env, cmd):
    for diff in iter_diff_records(repo_env, cmd):
        if diff.status != "D":
            yield diff


class AbstractViewInterface:

    def write(self, env, dest_dir):
        """Write view to dest_dir.

        The work should be done by running commands in env.

        Usually:

        * This will copy files to dest_dir from a repository.

        * env will be such that commands run in it will have their working
          directory set to the top level of that repo.
        """

    def apply(self, env, dir_):
        """Read view from dir_ and apply it to something.

        The work should be done by running commands in env.

        Usually:

        * This will apply changes to a repository (e.g. to the index), from a
          set of files in dir_ that were copied from that repo by .write().

        * env will be such that commands run in it will have their working
          directory set to the top level of that repo.
        """


class StageableWorkingTreeSubsetView:

    label = "working_tree"

    def __init__(self, repo_path):
        self._repo_path = repo_path

    def _untracked(self, env):
        process = env.read_cmd(
            ["git", "ls-files", "-z", "--others", "--exclude-standard"])
        return [f.decode() for f in process.stdout_output.split(b"\0")[:-1]]

    def _modified(self, env):
        for diff in iter_diff_records_undeleted(
                env, ["git", "diff-index", "-z", "HEAD"]):
            yield diff.path

    def write(self, env, dest_dir):
        repo_env = PrefixCmdEnv.make_readable(in_dir(self._repo_path), env)
        abs_repo_path = os.path.abspath(self._repo_path)
        dest_env = PrefixCmdEnv.make_readable(in_dir(dest_dir), env)
        paths = itertools.chain(
            self._untracked(repo_env),
            self._modified(repo_env))
        for path in paths:
            dir_path = os.path.dirname(path)
            if dir_path != "":
                dest_env.cmd(["mkdir", "-p", dir_path])
            dest_env.cmd([
                "cp", "-Pp", os.path.join(abs_repo_path, path), path])
        # make it obvious that git-meld-index working does not apply this
        # (left side) view back to the working copy changes (meld refuses
        # to let you edit non-writeable files)
        dest_env.cmd(["chmod", "-R", "a-w", dest_dir])

    def apply(self, env, dir_):
        pass


def ensure_trailing_slash(path):
    if path.endswith("/"):
        return path
    return path + "/"


def make_git_permission_string(is_link, is_executable):
    if is_link:
        return "120000"
    else:
        return "100755" if is_executable else "100644"


class IndexOrHeadView:

    """View of files:

    * in index
    * not in index but modified in working copy (unless deleted there)
    * not in index but untracked in working copy

    For files not in the index, this uses HEAD, because that is useful to
    (partially or fully) stage modified and untracked files.

    All files in the view's directory are apply()ied to the index, regardless
    of whether they were there at .write() time.
    """

    label = "index"

    def __init__(self, repo_path):
        self._repo_path = repo_path

    def check_out_head(self, repo_env, path, dest_path):
        # check out HEAD to dest_path
        ls_tree = repo_env.read_cmd(["git", "ls-tree", "HEAD", path])
        mode, type_, hash_path = ls_tree.stdout_output.decode().split(" ")
        hash_, _ = hash_path.split("\t")
        dest_dir_path = os.path.dirname(dest_path)
        if dest_dir_path != "":
            repo_env.cmd(["mkdir", "-p", dest_dir_path])
        if mode == "160000":
            # submodule
            # git meld-index doesn't operate on submodules. if you want to meld
            # a submodule, run git meld-index on the submodule itself, not on
            # the repository that contains the submodule.
            return
        if mode == "120000":
            # symlink
            cat_file_cmd = ["git", "cat-file", "blob", hash_]
            link = dest_path
            target = repo_env.cmd(cat_file_cmd).stdout_output.decode()
            repo_env.cmd(["ln", "-sT", target, link])
        else:
            # regular file
            cat_file_cmd = ["git", "cat-file", "blob", hash_]
            shell_cmd = " > ".join([
                shell_escape(cat_file_cmd), shlex.quote(dest_path)])
            repo_env.cmd(["sh", "-c", shell_cmd])
            if mode == "100755":
                repo_env.cmd(["chmod", "+x", dest_path])

    def write(self, env, dest_dir):
        repo_env = PrefixCmdEnv.make_readable(in_dir(self._repo_path), env)
        dest_prefix = ensure_trailing_slash(dest_dir)
        index_diffs = iter_diff_records_undeleted(
            env, ["git", "diff-index", "-z", "--cached", "HEAD"])
        index_paths = set()
        for diff in index_diffs:
            # Note that in the unmerged state, typically the index contains
            # *three* versions of your file (which you can see using `git
            # ls-files -u`): the common ancestor, HEAD, and MERGE_HEAD.  We
            # don't want to lose that unmerged state unless the user explicitly
            # edits the unmerged file using meld (running git meld-index,
            # editing nothing, then exiting should always leave your repo
            # unchanged).  If we added the file to the filesystem tree we're
            # building (either with checkout-index or below with
            # .check_out_head()), that unmerged state would get blown away on
            # .apply().  The user can still explicitly stage text from the
            # working copy version with conflict markers using "copy to right"
            # and then resolve the conflict markers on the right hand side, all
            # in meld.
            if diff.status != "U":
                repo_env.cmd(["git", "checkout-index", "--prefix={}".format(dest_prefix), diff.path])
            index_paths.add(diff.path)

        # Use HEAD for modified files not already in index
        working_diffs = iter_diff_records_undeleted(
            env, ["git", "diff-index", "-z", "HEAD"])
        working_tree_paths = [d.path for d in working_diffs]
        for path in working_tree_paths:
            if path not in index_paths:
                dest_path = os.path.join(dest_dir, path)
                self.check_out_head(repo_env, path, dest_path)

    def apply(self, env, dir_):
        abs_repo_path = os.path.abspath(self._repo_path)
        repo_env = PrefixCmdEnv.make_readable(in_dir(abs_repo_path), env)
        src_env = PrefixCmdEnv.make_readable(in_dir(dir_), env)
        find = src_env.read_cmd(["find", ".", "-type", "f", "-print0"])
        paths = [p.decode() for p in find.stdout_output.split(b"\0")]
        assert paths[-1] == "", paths
        for path in paths[:-1]:
            if path.startswith("./"):
                path = path[2:]
            src_path = os.path.join(dir_, path)
            is_link = try_cmd(src_env, ["test", "-h", path])
            is_executable = try_cmd(src_env, ["test", "-x", path])
            permission = make_git_permission_string(is_link, is_executable)
            hash_object = repo_env.cmd(["git", "hash-object", "-w", src_path])
            hash_ = hash_object.stdout_output.decode().removesuffix("\n")
            index_info = "{} {}\t{}".format(permission, hash_, path)
            repo_env.cmd(
                ["git", "update-index", "--index-info"],
                input=index_info.encode())


class Cleanups:

    def __init__(self):
        self._cleanups = []

    def add_cleanup(self, func):
        """Add a cleanup function.

        It is possible for the function to be called more than once on
        .clean_up(), though that shouldn't normally happen.
        """
        self._cleanups.append(func)

    def clean_up(self):
        """Call cleanup functions.

        It is OK to call this more than once.
        """
        failed = False
        while self._cleanups:
            func = self._cleanups[-1]
            try:
                func()
            except:
                log.exception("Exception cleaning up: {}".format(func))
                failed = True
            self._cleanups.pop()
        if failed:
            raise

    def __enter__(self):
        return self

    def __exit__(self, type_, value, tb):
        self.clean_up()


class NullCleanups:

    def add_cleanup(self, func):
        pass

    def __enter__(self):
        return self

    def __exit__(self, type_, value, tb):
        pass


class TempMaker:

    def __init__(self, rmtree, add_cleanup, prefix=""):
        self._add_cleanup = add_cleanup
        self._prefix = prefix
        self._rmtree = rmtree

    def make_temp_dir(self):
        prefix = "tmp-git_meld_index{}-".format(self._prefix)
        temp_dir = tempfile.mkdtemp(prefix=prefix)

        def clean_up():
            self._rmtree(temp_dir)

        self._add_cleanup(clean_up)
        return temp_dir


def make_view(url_or_refspec):
    scheme, sep, dir_path = url_or_refspec.partition(":")
    if dir_path == "":
        dir_path = "."
    scheme_colon = scheme + sep
    # Q. Why this fancy business rather than hard-coding left and right sides?
    # A. I intend to add other views, e.g. arbitrary commit
    if scheme_colon == "working:":
        # TODO: at the moment there is not much point in having this on the
        # right, because the .apply() method does not copy edited files
        # back to the working copy (so any edits are discarded on exit).
        return StageableWorkingTreeSubsetView(dir_path)
    elif scheme_colon == "index:":
        # TODO: this may not make much sense on the left at the moment.
        return IndexOrHeadView(dir_path)
    else:
        raise UnknownURISchemeError(
            "unknown URI scheme: {} "
            "(try running git-meld-index without arguments)".format(scheme))


def add_basic_env_arguments(add_argument):
    add_argument("-v", "--verbose", action="store_true",
                 help="Print commands")
    add_argument("-n", "--pretend", action="store_true",
                 help="Don't actually run commands")


def get_env_from_arguments(arguments):
    env = BasicEnv.make_readable()
    if arguments.pretend:
        env = NullWrapper.make_readable(env)
    if arguments.verbose:
        env = VerboseWrapper.make_readable(env)
    return env


def repo_dir_cmd():
    return ["git", "rev-parse", "--show-toplevel"]


def chmod_and_rmtree(env, dirpath):
    env.cmd(["chmod", "-R", "u+w", dirpath])
    shutil.rmtree(dirpath)


def _main(prog, args):
    # This is not __doc__ because it's tiresome for setup.py to parse out
    # __version__ otherwise
    description = """\
Interactively stage changes to the git index (also known as the git staging
area) using any git difftool (such as meld).
"""
    parser = argparse.ArgumentParser(
        prog=os.path.basename(prog), description=description)
    add_basic_env_arguments(parser.add_argument)
    # Note there's also a manpage, which is what git meld-index --help shows
    parser.add_argument(
        "--tool", "-t", dest="tool",
        help=("Use the diff tool specified by <tool>. Valid values include "
              "meld and kdiff3. Run git meld-index --tool-help for the list "
              "of valid <tool> settings."))
    parser.add_argument(
        "--tool-help", default=False, action="store_true",
        help="Print a list of diff tools that may be used with --tool.")
    parser.add_argument(
        "--extcmd", "-x",
        help=("Specify a custom command for viewing and editing diffs.  "
              "git-meld-index ignores the configured defaults and runs "
              "$command $LEFT $RIGHT when this option is specified."))
    parser.add_argument(
        "--gui", "-g", default=False, action="store_true",
        help=("Read the default diff tool from the configured diff.guitool "
              "variable instead of diff.tool."))
    parser.add_argument(
        "--work-dir",
        help="Directory to use instead of temporary directory.  "
        "This won't be removed on exit.")
    parser.add_argument(
        "--no-cleanup", dest="cleanup",
        default=True, action="store_false",
        help="Don't remove temporary files passed to difftool")
    parser.add_argument(
        "left", nargs="?", default=None,
        help="Not really useful as yet hence undocumented")
    parser.add_argument(
        "right", nargs="?", default=None,
        help="Not really useful as yet hence undocumented")
    arguments = parser.parse_args(args)
    work_dir = arguments.work_dir
    if arguments.cleanup:
        cleanups = Cleanups()
    else:
        cleanups = NullCleanups()
    atexit.register(cleanups.clean_up)
    env = get_env_from_arguments(arguments)
    if arguments.tool_help:
        print(env.cmd(["git", "mergetool", "--tool-help"]).stdout_output.decode())
        return 0

    repo_dir = env.read_cmd(repo_dir_cmd()).stdout_output.decode().removesuffix("\n")
    left = arguments.left
    if left is None:
        left = "working:" + repo_dir
    right = arguments.right
    if right is None:
        right = "index:" + repo_dir
    tool = arguments.tool
    if arguments.gui:
        try:
            tool = (env.cmd(["git", "config", "-z", "diff.guitool"])
                    .stdout_output.removesuffix(b"\0").decode())
        except CalledProcessError:
            pass
    with cleanups:
        make_temp_dir = TempMaker(
            functools.partial(chmod_and_rmtree, env), cleanups.add_cleanup).make_temp_dir
        if work_dir is None:
            work_dir = make_temp_dir()
        work_area = WorkArea(env, work_dir)
        try:
            left_view = make_view(left)
            right_view = make_view(right)
        except UnknownURISchemeError as exc:
            parser.error(str(exc))
        work_area.meld(left_view, right_view, tool, arguments.extcmd)
    return 0


def main():
    try:
        status = _main(sys.argv[0], sys.argv[1:])
    except KeyboardInterrupt:
        status = 1
    sys.exit(status)


if __name__ == "__main__":
    main()
