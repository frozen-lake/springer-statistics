# Toolchain image for the Matches tool: gcc (builds Springer), fastchess (runs matches) and Stockfish.
FROM python:3.12-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG FASTCHESS_URL=https://github.com/Disservin/fastchess/releases/download/v1.8.2-alpha/fastchess-linux-x86-64.tar
ARG FASTCHESS_SHA256=1003f920bebe841acdab5e6d7871e93171a4586857b3ec91c21ef5777f26ff96
RUN curl -fsSL "$FASTCHESS_URL" -o /tmp/fastchess.tar \
    && echo "$FASTCHESS_SHA256  /tmp/fastchess.tar" | sha256sum -c - \
    && mkdir /tmp/fastchess \
    && tar -xf /tmp/fastchess.tar -C /tmp/fastchess \
    && install -m 0755 "$(find /tmp/fastchess -type f -name 'fastchess' | head -n 1)" /usr/local/bin/fastchess \
    && rm -rf /tmp/fastchess /tmp/fastchess.tar \
    && test -x /usr/local/bin/fastchess

ARG STOCKFISH_URL=https://github.com/official-stockfish/Stockfish/releases/download/sf_19/stockfish-linux-x86-64-universal.tar.gz
ARG STOCKFISH_SHA256=9defc0d4e55d49c65a6d042f3e571a39fcea499ade6dbe741b53b8c65e03611f
RUN curl -fsSL "$STOCKFISH_URL" -o /tmp/stockfish.tar.gz \
    && echo "$STOCKFISH_SHA256  /tmp/stockfish.tar.gz" | sha256sum -c - \
    && mkdir /opt/stockfish \
    && tar -xzf /tmp/stockfish.tar.gz -C /opt/stockfish \
    && rm /tmp/stockfish.tar.gz \
    && ln -s "$(find /opt/stockfish -type f -name 'stockfish*' -perm -u+x | head -n 1)" /usr/local/bin/stockfish \
    && printf 'uci\nquit\n' | stockfish | head -n 1
