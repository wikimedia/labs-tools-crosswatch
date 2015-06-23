import os
from setuptools import setup, find_packages


def read(fname):
    path = os.path.join(os.path.dirname(__file__), fname)
    return open(path).read()


setup(
    name="crosswatch",
    version="0.0.1",
    author="Jan Lebert",
    author_email="jan.lebert@online.de",
    description="backend webserver and celery tasks for crosswatch",
    license="ISC",
    keywords="private backend tornado celery",
    url="https://tools.wmflabs.org/crosswatch",
    packages=find_packages(exclude='frontend'),
    install_requires=['gevent',
                      'kombu',
                      'requests-oauthlib',
                      'requests[security]',
                      'mwoauth',
                      'MySQL-python',
                      'flask-oauth',
                      'sockjs-tornado',
                      'tornado-redis',
                      'tornado',
                      'celery',
                      'redis'
                      ],
    dependency_links=[
        "git+https://gerrit.wikimedia.org/r/p/labs/tools/crosswatch.git@kombu#egg=kombu-3.0.26"  # NOQA
    ],
    long_description=read('README.md'),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: ISC License (ISCL)",
    ]
)
