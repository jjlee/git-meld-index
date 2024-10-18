"""%(prog)s RELEASE_DIR [action ...]

Perform needed actions to release, doing the work in directory RELEASE_DIR.

If no actions are given, print the tree of actions and do nothing.
"""

# This script depends on the code from this git repository:
# git://github.com/jjlee/mechanize-build-tools.git
# It requires asciidoc and xmlto to build the manpage.

import argparse
import os
import sys

from buildtools import release
import action_tree
import build_log
import cmd_env


class Releaser(object):

    def __init__(self, env, release_dir, upstream_repo,
                 work_repo=None,
                 tag_name=None,
                 github_access_token=None):
        self._release_dir = release_dir
        self._repo = upstream_repo
        self._work_repo = work_repo
        self._github_access_token = github_access_token
        self._requested_tag_name = tag_name
        if work_repo is None:
            self._clone_path = os.path.join(release_dir, "clone")
        else:
            self._clone_path = work_repo
        self._base_env = env
        self._env = release.CwdEnv(env, self._clone_path)
        self._set_tag_name()

    def _get_next_tag_from_repo(self):
        # Dry run or no tags
        next_ = "dummy"
        try:
            tag_lines = release.get_cmd_stdout(
                self._env, ["git", "show-ref", "--tags"]).decode()
            tags = []
            for line in tag_lines.splitlines():
                tag = line.split()[1].split("refs/tags/")[1]
                tags.append(tag)
        except cmd_env.CommandFailedError:
            pass
        else:
            versions = [release.parse_version(t) for t in tags]
            if len(versions) != 0:
                most_recent = max(versions)
                next_ = str(most_recent.next_version())
            return next_

    def _set_tag_name(self):
        if self._requested_tag_name is not None:
            self._tag_name = self._requested_tag_name
        else:
            self._tag_name = self._get_next_tag_from_repo()

    def destroy(self, log):
        release.clean_dir(self._base_env, self._release_dir)

    def clone(self, log):
        # from github
        self._base_env.cmd(["mkdir", "-p", self._clone_path])
        self._env.cmd(["git", "clone", self._repo, self._clone_path])

    def checkout_master(self, log):
        self._env.cmd(["git", "checkout", "-B", "master", "origin/master"])

    def guess_next_tag(self, log):
        # Obviously if you've already tagged in this repo you don't want this
        self._set_tag_name()

    def print_tag(self, log):
        print(self._tag_name)

    def merge_to_release(self, log):
        self._env.cmd(["git", "checkout", "-b", "release", "origin/release"])
        self._env.cmd(["git", "merge", "-X", "theirs", "--no-edit", "master"])

    def _update_magic_version(self, version, message):
        version_path = "src/git_meld_index.py"
        # Replace just the first occurrence
        replacement = (
            '0,/__version__ = /'
            '{{s/\\(__version__ = \\)".*"$/\\1"{0}"/}}'.format(version))
        self._env.cmd(["sed", "-i", "-e", replacement, version_path])
        self._env.cmd(["git", "commit", "-am", message])

    def set_version(self, log):
        message = "New release {}".format(self._tag_name)
        self._update_magic_version(self._tag_name, message)

    def build_manpage(self, log):
        xml = os.path.join(self._release_dir, "git-meld-index.xml")
        self._env.cmd([
            "asciidoc", "-b", "docbook", "-d", "manpage",
            "-f", "doc/asciidoc.conf",
            "-a", "git-asciidoc-no-roff",
            "-o" + xml,
            "doc/git-meld-index.txt"])
        self._env.cmd([
            "xmlto",
            "-m", "doc/manpage-normal.xsl",
            "-m", "doc/manpage-quote-apos.xml",
            "-o", "doc",
            "man",
            xml])

    def commit_manpage(self, log):
        self._env.cmd(["git", "add", "doc/git-meld-index.1"])
        try:
            self._env.cmd(["git", "diff", "--cached", "--exit-code"])
        except cmd_env.CommandFailedError:
            self._env.cmd(["git", "commit", "-m", "Built manpage",
                           "doc/git-meld-index.1"])
        else:
            pass

    def tag(self, log):
        self._env.cmd(["git", "tag", self._tag_name])

    def test(self, log):
        self._env.cmd(["python", "src/test_git_meld_index.py", "--verbose"])

    def diff(self, log):
        self._env.cmd(["git", "diff", "master"])

    def gitk(self, log):
        self._env.cmd(["gitk", "--all"])

    def push(self, log):
        self._env.cmd(["git", "push", self._repo, "master"])
        self._env.cmd(["git", "push", self._repo, "release"])
        self._env.cmd(["git", "push", self._repo, self._tag_name])

    @action_tree.action_node
    def prepare(self):
        return [
            self.destroy,
            self.clone,
            self.checkout_master,
            self.guess_next_tag,
            self.print_tag,
            self.build_manpage,
            self.commit_manpage,
            self.merge_to_release,
            self.build_manpage,
            self.commit_manpage,
            self.set_version,
            self.tag,
            self.test,
            self.diff,
            self.gitk,
        ]

    @action_tree.action_node
    def release(self):
        return [
            self.prepare,
            self.push,
        ]


def parse_args(prog, args):
    parser = argparse.ArgumentParser(
        prog=os.path.basename(prog), description=__doc__.strip())
    release.add_basic_env_arguments(parser)
    action_tree.add_arguments(parser)
    parser.add_argument(
        "--tag-name", metavar="TAG_NAME",
        help=("Pass this if you don't run the guess_next_tag action or you "
              "want to override the next tag"))
    parser.add_argument(
        "--repo", metavar="REPO",
        default="git@github.com:jjlee/git-meld-index.git",
        help="Upstream repository to clone from")
    parser.add_argument(
        "--work-repo", metavar="WORK_REPO",
        help=("Use this repo instead of clone of upstream repo -- useful for "
              "e.g. testing building manpage.  Use with care as likely not "
              "all actions make sense with this."))
    parser.add_argument("--github-access-token", metavar="FILE")
    parser.add_argument("release_dir")
    return parser.parse_known_args(args)


def main(prog, args):
    if not hasattr(action_tree, "action_main"):
        sys.exit("failed to import required modules")
    arguments, action_tree_args = parse_args(prog, args)
    env = release.get_env_from_options(arguments)
    if arguments.github_access_token is not None:
        token = cmd_env.read_file(
            os.path.expanduser(arguments.github_access_token))[:-1]
    else:
        token = None
    releaser = Releaser(
        env, arguments.release_dir, arguments.repo,
        work_repo=arguments.work_repo,
        tag_name=arguments.tag_name,
        github_access_token=token)
    log = build_log.PrintTitlesLogWriter(sys.stdout,
                                         build_log.DummyLogWriter())
    action_tree.action_main_(
        releaser.release, arguments, action_tree_args, log=log)


if __name__ == "__main__":
    main(sys.argv[0], sys.argv[1:])
