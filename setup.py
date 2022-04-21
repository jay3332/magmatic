import re
from warnings import warn

from setuptools import setup


with open('requirements.txt') as fp:
    requirements = fp.read().splitlines()

with open('README.md') as fp:
    readme = fp.read()

with open('magmatic/__init__.py', encoding='utf-8') as fp:
    extra = {}

    for match in re.finditer(
        r'^__(?P<name>\w+)__(?:\s*:\s*\w+\s*)?\s*=\s*([\'\"])(?P<value>.+)\2\s*$',
        fp.read(),
        flags=re.MULTILINE,
    ):
        data = match.groupdict()
        extra[data['name']] = data['value']

try:
    version = extra['version']
except KeyError:
    raise RuntimeError('Unable to determine version number')

if version.endswith(('a', 'b', 'rc')):
    try:
        import subprocess

        proc = subprocess.Popen(
            ['git', 'rev-list', '--count', 'HEAD'], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.DEVNULL,
        )
        stdout, _ = proc.communicate()

        if stdout:
            extra['version'] += stdout.decode('utf-8').strip()

        proc = subprocess.Popen(
            ['git', 'rev-parse', '--short', 'HEAD'],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        stdout, _ = proc.communicate()

        if stdout:
            extra['version'] += '+g' + stdout.decode('utf-8').strip()
    except Exception as exc:
        warn(f'Encountered error while trying to retrieve Git commit hash: {exc}')

setup(
    name='magmatic',
    url='https://github.com/jay3332/magmatic',
    packages=['magmatic'],
    description='A robust and asynchronous Lavalink wrapper for discord.py.',
    project_urls={
        'Discord': 'https://discord.gg/FqtZ6akWpd',
        'Github': 'https://github.com/jay3332/magmatic',
        'Issue tracker': 'https://github.com/jay3332/magmatic/issues',
        'Documentation': 'https://magmatic.readthedocs.io/en/latest/',
    },
    long_description=readme,
    include_package_data=True,
    install_requires=requirements,
    extras_require={
        'docs': [
            'sphinx>=4.5',
            'furo',
            'discord.py @ git+https://github.com/rapptz/discord.py',
            'sphinx-toolbox',
            'enum-tools',
        ],
    },
    python_requires='>=3.8',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Topic :: Internet',
        'Topic :: Multimedia :: Sound/Audio',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Utilities',
        'Typing :: Typed',
    ],
    **extra,  # should contain author, license, version
)
