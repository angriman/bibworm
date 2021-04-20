from setuptools import setup, find_packages

setup(
    name='bibworm',
    version='0.1',
    packages=['bibworm'],
    include_package_data=True,
    install_requires=[
        'Click',
    ],
    entry_points='''
        [console_scripts]
        worm=bibworm.scripts.worm:cli
    ''',
)
