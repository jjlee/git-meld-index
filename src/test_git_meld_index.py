from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import os
import subprocess
import sys
import unittest

import git_meld_index
from git_meld_index import trim
import list_tree


def read_file(path):
    with open(path) as fh:
        return fh.read()


def write_file(path, data):
    with open(path, "w") as fh:
        fh.write(data)


def write_file_cmd(filename, data):
    return ["bash", "-c", 'echo -n "$1" >"$2"', "inline_script", data, filename]


def append_file_cmd(filename, data):
    return ["bash", "-c", 'echo -n "$1" >>"$2"', "inline_script", data, filename]


class Repo(object):

    # TODO: Don't use porcelain (init/add/commit/rm)?  Seems fairly safe /
    # appropriate (for test realism) here though.

    def __init__(self, env):
        self._env = env
        self._cmd("git", "init")

    def _cmd(self, *args):
        self._env.cmd(list(args))

    def add_untracked(self, name, content):
        if "/" in name:
            dirpath = os.path.dirname(name)
            self._env.cmd(["mkdir", "-p", dirpath])
        self._env.cmd(write_file_cmd(name, content))

    def add_new_staged(self, name, content):
        self.add_untracked(name, content)
        self._cmd("git", "add", name)

    def add_unmodified(self, name, content):
        self.add_new_staged(name, content)
        self._cmd("git", "commit", "-m", name, name)

    def add_new_partially_staged(self, name, content, unstaged_content):
        self.add_new_staged(name, content)
        self._env.cmd(append_file_cmd(name, unstaged_content))

    def add_modified(self, name, initial_content, unstaged_content):
        self.add_unmodified(name, initial_content)
        self._env.cmd(append_file_cmd(name, unstaged_content))

    def add_modified_staged(self, name, initial_content, staged_content):
        self.add_modified(name, initial_content, staged_content)
        self._cmd("git", "add", name)

    def add_deleted_from_working_tree(self, name, initial_content):
        self.add_unmodified(name, initial_content)
        self._cmd("rm", name)

    def add_deleted_from_index(self, name, initial_content):
        self.add_unmodified(name, initial_content)
        self._cmd("git", "rm", "--cached", name)

    def add_deleted_from_index_and_working_tree(self, name, initial_content):
        self.add_unmodified(name, initial_content)
        self._cmd("git", "rm", name)


def make_standard_repo(env, path_prefix=""):
    repo = Repo(env)
    repo.add_untracked(path_prefix + "untracked", "untracked\n")
    repo.add_new_staged(path_prefix + "new_staged", "new staged\n")
    repo.add_unmodified(path_prefix + "unmodified", "unmodified\n")
    repo.add_new_partially_staged(path_prefix + "partially_staged",
                                  "partially staged\n", "more\n")
    repo.add_modified(path_prefix + "modified",
                      "modified (initial)\n",
                      "modified (modified)\n")
    repo.add_modified_staged(
        path_prefix + "modified_staged",
        "modified staged (initial)\n",
        "modified staged (modified)\n")
    repo.add_deleted_from_working_tree(path_prefix + "deleted", "deleted\n")
    repo.add_deleted_from_index(
        path_prefix + "deleted_from_index", "deleted from index\n")
    repo.add_deleted_from_index_and_working_tree(
        path_prefix + "deleted_from_index_and_working_tree",
        "deleted from index and working tree\n")
    return repo


class TestCase(unittest.TestCase):

    def make_temp_dir(self):
        prefix = "-" + self.__class__.__name__
        maker = git_meld_index.TempMaker(self.addCleanup, prefix=prefix)
        return maker.make_temp_dir()

    # This meld functionality is unrelated to the function of git-meld-index,
    # except that it uses meld!  It is here to verify test output.

    # Set this True to see golden assertion failure differences in meld
    run_meld = False

    # Set this True to see commands run by tests
    print_commands = False

    this_dir = os.path.dirname(os.path.abspath(__file__))

    GOLDEN_FAILURE_TEXT = """\
Differences from golden files found.
Try running with --meld to update golden files.
"""

    def _assert_golden_dir(self, got_dir, expect_dir):
        assert os.path.exists(expect_dir), expect_dir
        proc = subprocess.Popen(["diff", "--recursive", "-u", "-N",
                                 "--exclude=.*", expect_dir, got_dir],
                                stdout=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        if len(stdout) > 0:
            if self.run_meld:
                # Put expected output on the right because that is the
                # side we usually edit.
                subprocess.call(["meld", got_dir, expect_dir])
            raise AssertionError(
                self.GOLDEN_FAILURE_TEXT + "\n{}".format(stdout))
        self.assertEquals(proc.wait(), 0)

    def assert_golden(self, got_dir, expect_dirname):
        expect_dir = os.path.join(self.this_dir, "golden", expect_dirname)
        self._assert_golden_dir(got_dir, expect_dir)

    def _assert_golden_file(self, got_path, expect_path):
        got_text = read_file(got_path)
        try:
            expect_text = read_file(expect_path)
        except IOError as exc:
            if exc.errno != errno.ENOENT:
                raise
            # file does not exist
            expect_text = None

        if got_text != expect_text:
            if self.run_meld:
                subprocess.call(["meld", got_path, expect_path])
                raise AssertionError(self.GOLDEN_FAILURE_TEXT)
            else:
                proc = subprocess.Popen(["diff", "-u", expect_path, got_path],
                                        stdout=subprocess.PIPE)
                stdout, stderr = proc.communicate()
                raise AssertionError(self.GOLDEN_FAILURE_TEXT + "\n%s" % stdout)

    def assert_golden_file(self, got_text, expect_filename):
        got_path = os.path.join(self.make_temp_dir(), expect_filename)
        write_file(got_path, got_text)
        expect_path = os.path.join(
            self.this_dir, "golden", "assert_golden_file", expect_filename)
        self._assert_golden_file(got_path, expect_path)

    def make_env(self):
        if self.print_commands:
            basic = git_meld_index.VerboseWrapper.make_readable(
                git_meld_index.BasicEnv.make_readable())
        else:
            basic = git_meld_index.BasicEnv.make_readable()
        return git_meld_index.PrefixCmdEnv.make_readable(
            git_meld_index.in_dir(self.make_temp_dir()), basic)


def add_to_path_cmd(values):
    set_path_script = """\
if [ -n "$PATH" ]
  then
    export PATH=%(value)s:"$PATH"
  else
    export PATH=%(value)s
fi
exec "$@"
""" % dict(value=":".join(values))
    return ["sh", "-c", set_path_script, "inline_script"]


class WriteViewMixin(object):

    def assert_write_golden(self, make_view_from_repo_path, golden_file_name):
        env = self.make_env()
        make_standard_repo(env)
        path = trim(
            env.cmd(["readlink", "-e", "."]).stdout_output, suffix="\n")
        view = make_view_from_repo_path(path)
        out = self.make_temp_dir()
        view.write(env, out)
        listing = list_tree.ls_tree(out)
        listing = listing.replace(path, '<repo>')
        self.assert_golden_file(listing, golden_file_name)


class TestStageableWorkingTreeSubsetView(TestCase, WriteViewMixin):

    def test_write_golden(self):
        make_view = git_meld_index.StageableWorkingTreeSubsetView
        self.assert_write_golden(
            make_view, "test_write_stageable_working_tree_subset")


class TestIndexOrHeadView(TestCase, WriteViewMixin):

    def test_raw_diff(self):
        env = self.make_env()
        make_standard_repo(env)
        records = git_meld_index.iter_diff_records(
            env, ["git", "diff-files", "-z"])
        self.assertEqual(
            [record.path for record in records],
            ['deleted', "modified", "partially_staged"])

    def test_write_golden(self):
        make_view = git_meld_index.IndexOrHeadView
        self.assert_write_golden(
            make_view, "test_write_stageable_index_subset")


class TestEndToEnd(TestCase):

    # TODO: Cover these
    # symlinks
    # file / dir moves

    # DONE: A: addition of a file
    # TODO: C: copy of a file into a new one
    # DONE: D: deletion of a file
    # DONE: M: modification of the contents or mode of a file
    # TODO: R: renaming of a file
    # TODO: T: change in the type of the file
    # TODO: U: file is unmerged (you must complete the merge before it can be committed)

    def write_fake_meld(self, env, new_content_dir):
        left_listing_path = os.path.join(self.make_temp_dir(), "left")
        right_listing_path = os.path.join(self.make_temp_dir(), "right")
        script = """\
#!/bin/sh
left="$1"
right="$2"
find_relative () {{
    (cd "$1" && find . -type f) | cut -c3-
}}
find_relative "$left" > {listing_left}
find_relative "$right" > {listing_right}

rsync -a {new_content}/ "$right"
""".format(new_content=new_content_dir,
           listing_left=left_listing_path,
           listing_right=right_listing_path)
        meld_dir = self.make_temp_dir()
        meld_path = os.path.join(meld_dir, "meld")
        env.cmd(write_file_cmd(meld_path, script))
        env.cmd(["chmod", "+x", meld_path])
        def get_recorded_listings():
            l = read_file(left_listing_path).splitlines()
            r = read_file(right_listing_path).splitlines()
            return l, r
        git_meld_index_bin = os.path.abspath(
            os.path.join(self.this_dir, "../bin"))
        meld_env = git_meld_index.PrefixCmdEnv.make_readable(
            add_to_path_cmd([meld_dir, git_meld_index_bin]), env)
        return meld_env, get_recorded_listings

    def write_diffs(self, env):
        diff_output = self.make_temp_dir()
        # TODO: porcelain
        env.cmd(["sh", "-c", "git diff > {}/diff".format(diff_output)])
        # TODO: porcelain
        env.cmd(
            ["sh", "-c", "git diff --cached > {}/cached".format(diff_output)])
        env.cmd(
            ["sh", "-c",
             "git ls-files --others --exclude-standard > {}/untracked".format(
                 diff_output)])
        return diff_output

    def check(self, golden_dir, env, prefix=""):
        repo_path = trim(
            env.read_cmd(["readlink", "-e", "."]).stdout_output, suffix="\n")

        self.assert_golden(
            self.write_diffs(env), os.path.join(golden_dir, "unmelded"))

        # Modified or untracked files in the working tree
        working_tree_sources = ["untracked", "partially_staged", "modified",
                                "modified_staged", "new_staged",
                                "deleted_from_index"]
        # Everything in the index that is also modified in working tree
        # (including new or untracked) -- and therefore has something that
        # could be staged
        index_destinations = [
            "modified", "modified_staged", "new_staged", "partially_staged"]

        def add_prefix(paths):
            return [prefix + path for path in paths]
        working_tree_sources = add_prefix(working_tree_sources)
        index_destinations = add_prefix(index_destinations)

        # Write a fake meld command that will edit every file in the index to
        # have the same content as its file name.  Files that are fully staged
        # or unmodified won't be melded so are omitted.
        edited = self.make_temp_dir()
        for name in working_tree_sources:
            content = name + " edited by meld\n"
            path = os.path.join(edited, name)
            env.cmd(["mkdir", "-p", os.path.dirname(path)])
            env.cmd(write_file_cmd(path, content))
        meld_env, get_recorded_listings = self.write_fake_meld(env, edited)

        work_dir = self.make_temp_dir()
        work_area = git_meld_index.WorkArea(meld_env, work_dir)
        left_view = git_meld_index.make_view("working:" + repo_path)
        right_view = git_meld_index.make_view("index:" + repo_path)
        work_area.meld(left_view, right_view, tool="meld")

        left, right = get_recorded_listings()
        self.assertEqual(sorted(left), sorted(working_tree_sources))
        self.assertEqual(sorted(right), sorted(index_destinations))
        self.assert_golden(
            self.write_diffs(env), os.path.join(golden_dir, "melded"))

    def test(self):
        env = self.make_env()
        make_standard_repo(env)
        self.check("test", env)

    def test_dirs(self):
        env = self.make_env()
        prefix = "sub/dir/"
        make_standard_repo(env, prefix)
        self.check("test_dirs", env, prefix=prefix)


class TestExecutable(TestCase):

    def write_do_nothing_fake_meld(self, env):
        meld_dir = self.make_temp_dir()
        meld_path = os.path.join(meld_dir, "meld")
        env.cmd(write_file_cmd(meld_path, "#!/bin/sh\ntrue\n"))
        env.cmd(["chmod", "+x", meld_path])
        git_meld_index_bin = os.path.abspath(
            os.path.join(self.this_dir, "../bin"))
        return git_meld_index.PrefixCmdEnv.make_readable(
            add_to_path_cmd([meld_dir, git_meld_index_bin]), env)

    def test_executable_bit_is_preserved(self):
        env = self.make_env()
        repo = Repo(env)
        repo.add_untracked("executable", "executable\n")
        env.cmd(["chmod", "a+x", "executable"])
        env.cmd(["git", "add", "executable"])
        env.cmd(["git", "commit", "-m", "message", "executable"])
        repo_path = trim(
            env.read_cmd(["readlink", "-e", "."]).stdout_output, suffix="\n")
        meld_env = self.write_do_nothing_fake_meld(env)
        work_dir = self.make_temp_dir()

        work_area = git_meld_index.WorkArea(meld_env, work_dir)
        left_view = git_meld_index.make_view("working:" + repo_path)
        right_view = git_meld_index.make_view("index:" + repo_path)
        work_area.meld(left_view, right_view, tool="meld")

        is_executable = git_meld_index.try_cmd(env, ["test", "-x", "executable"])
        self.assertTrue(is_executable)


def create_standard_repo(path, prefix=""):
    basic_env = git_meld_index.BasicEnv()
    basic_env.cmd(["mkdir", "-p", path])
    env = git_meld_index.PrefixCmdEnv(
        git_meld_index.in_dir(path),
        basic_env)
    make_standard_repo(env, prefix)


def main(prog, args):
    if args[:1] == ["--create-test-repo"]:
        repo_path = args[1]
        create_standard_repo(repo_path, prefix="sub/dir/")
    else:
        if args[:1] == ["--meld"]:
            TestCase.run_meld = True
            sys.argv.pop(1)
        unittest.main()


if __name__ == "__main__":
    main(sys.argv[0], sys.argv[1:])
