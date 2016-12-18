from setuptools import setup, find_packages
import os
import re

PACKAGE="django-wfs"

MYDIR = os.path.dirname(__file__)

def read_version():
    fn  = os.path.join(os.path.join(MYDIR,"debian-unix"),"changelog")
    with open(fn) as fd:
        line = fd.readline()   
        version,n = re.subn('^'+PACKAGE+'\\s*\\(([^-]*)-[^)]\\).*\n','\\1',line)
        if n != 1:
            raise SyntaxError("debian changelog line [%s] is malformatted"%line.substring[:-1])
        return version

setup(
    name=PACKAGE,
    packages=find_packages(),
    include_package_data=True,
    package_dir={'wfs': 'wfs'},
    version=read_version(),
    install_requires = ['sqlparse>=0.2.2'],
    description='A WFS (web feature service) implementation as a Django application.',
    author='Vasco Pinho',
    author_email='vascogpinho@gmail.com',
    url='https://github.com/vascop/django-wfs',
    download_url='https://github.com/vascop/django-wfs/tarball/master',
    long_description=open('README.md', 'r').read(),
    license='Apache 2.0',
    keywords=['wfs', 'geo', 'django'],
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
    ],
)
