FROM python:3.11-bullseye

RUN apt update && apt full-upgrade && apt install git rsync

RUN mkdir /opt/build
COPY src /opt/build/src
COPY bin /opt/build/bin
COPY doc /opt/build/doc
COPY setup.py README.md /opt/build

WORKDIR /opt/build
RUN pip install -e .

RUN git config --global user.email "you@example.com"

CMD [ "python3", "/opt/build/src/test_git_meld_index.py" ]
