from setuptools import setup, find_packages


setup(
    name='django-wfs',
    packages=find_packages(),
    include_package_data=True,
    package_dir={'wfs': 'wfs'},
    version='0.0.9',
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
