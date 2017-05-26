from setuptools import setup

setup(
    name='inventory',
    packages=['inventory'],
    install_requires=[
        'flask~=0.12',
        'flask-sqlalchemy~=2.2',
        'oauth2client~=4.1.0',
        'pyyaml~=3.12',
    ],
    package_data={'inventory': [
        'sample_data.yaml',
        'static/*.*',
        'static/**/*.*',
        'templates/*.*',
        'templates/**/*.*',
    ]},
)
