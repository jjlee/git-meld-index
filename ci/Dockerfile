FROM archlinux:latest

RUN pacman --noconfirm -Syu && pacman --noconfirm -S git rsync python-pip diffutils

RUN git --version

RUN mkdir /opt/test
COPY src /opt/test/src
COPY bin /opt/test/bin
COPY doc /opt/test/doc
COPY setup.py README.md release.py /opt/test

WORKDIR /opt/test
RUN pip install -e .

RUN git config --global user.name "Your Name"
RUN git config --global user.email "you@example.com"

CMD [ "python3", "/opt/test/src/test_git_meld_index.py" ]
