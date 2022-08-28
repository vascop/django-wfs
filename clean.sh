#!/bin/sh
#
# Clean the django-wfs project.
#
cd $(dirname $0)

projectdir=$(pwd)

echo '***** '"Cleaning project directory [$projectdir]..."

nremoved=0

for dir in dist build django_wfs.egg-info .pybuild
do
	test -d $dir && echo "Removing [$dir]" && rm -rf $dir && nremoved=$(expr $nremoved + 1)
done

for dir in $(find . -name __pycache__ )
do
	echo "Removing [$dir]" && rm -rf $dir && nremoved=$(expr $nremoved + 1)
done

if test $nremoved -eq 0
then
	echo '***** '"Nothing to remove, [$projectdir] was already clean."
else
	echo '***** '"Removed [$nremoved] directories from [$projectdir]."
fi
	
exit 0
