FROM archlinux:latest

# This Dockerfile's main reason for existing is to run the git-meld-index tests
# regularly against a recent git binary in order to check for regressions caused
# by upstream changes to git itself

# Releases of git-meld-index are mostly automated (see release.py) but don't
# involve docker, and the release process does not run in CI

RUN pacman --noconfirm -Syu && pacman --noconfirm -S git rsync python-pip diffutils

RUN git --version

RUN mkdir /opt/test
COPY src /opt/test/src
COPY bin /opt/test/bin
COPY doc /opt/test/doc
COPY pyproject.toml README.md release.py /opt/test

WORKDIR /opt/test
# git-meld-index has no PyPI dependencies so is unlikely to break anything; this
# just saves messing with a venv here
RUN pip install --break-system-packages .

RUN git config --global user.name "Your Name"
RUN git config --global user.email "you@example.com"

CMD [ "python3", "/opt/test/src/test_git_meld_index.py" ]
