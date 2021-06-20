#!/usr/bin/env bash

OLDIFS=$IFS
IFS=$'\t\n'

for i in $(cd img ; ls -1d */ ) ; do
  for ul in $(cd "img/${i}" ; ls -1 *.url 2>/dev/null) ; do
    URL="${ul/.url}"
    echo "\"https://raw.senmanga.com/${URL}\" \"${i/\//}\""
  done
done | tr "\n" "\0" | IFS=$OLDIFS /usr/bin/xargs -0 -P20 -L1 -I{} bash -c "./senmanga.py {}"

