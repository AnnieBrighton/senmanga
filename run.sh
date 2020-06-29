#!/usr/bin/env bash

for i in $(cd img ; ls -d */ ) ; do
   URL=$(cd img/${i} ; ls *.url 2>/dev/null | head -1)
   if [ "${URL}" == "" ] ; then
      URL="${i/\//}"
   else
      URL="${URL/.url}"
   fi
   ./senmanga.py "https://raw.senmanga.com/${URL}" "${i/\//}"
done

