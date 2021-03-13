#!/usr/bin/env bash

OLDIFS=$IFS
IFS=$'\t\n'

for i in $(cd img ; ls -d */ ) ; do
  for ul in $(cd "img/${i}" ; ls *.url 2>/dev/null) ; do
    echo "$i"
    URL="${ul/.url}"
    ./senmanga.py "https://raw.senmanga.com/${URL}" "${i/\//}"
  done
done

IFS=$OLDIFS
