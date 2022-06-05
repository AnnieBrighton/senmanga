#!/usr/bin/env bash

OLDIFS=$IFS
IFS=$'\t\n'

while true ; do
  find img* -name '*.url' 2>/dev/null | while read url ; do
    URL="$(basename ${url/.url})"
    DIR="$(dirname ${url})"
    echo "./rawkuma.py \"'https://rawkuma.com/manga/${URL}'\" \"'${DIR}'\""
    echo "./senmanga.py \"'https://raw.senmanga.com/${URL}'\" \"'${DIR}'\""
  done | IFS=${OLDIFS} /usr/bin/xargs -P20 -L1 -I{} -S4096 bash -c '{}'

  date
  sleep $(( 3600 * 4 ))
done
