#!/usr/bin/env bash

OLDIFS=$IFS
IFS=$'\t\n'

while true ; do
for i in $(cd img ; ls -1d */ ) ; do
  for ul in $(cd "img/${i}" ; ls -1 *.url 2>/dev/null) ; do
    URL="${ul/.url}"
    echo "\"'https://raw.senmanga.com/${URL}'\" \"'${i/\//}'\""
  done
done | IFS=${OLDIFS} /usr/bin/xargs -P20 -L1 -I{} -S4096 bash -c './senmanga.py {}'
date
sleep $(( 3600 * 4 ))
done
