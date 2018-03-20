import os
import sys
from setuptools import find_packages, setup

from lbryum import __version__

if sys.version_info[:3] < (2, 7, 0):
    sys.exit("Error: lbryum requires Python version >= 2.7.0...")

data_files = []

requires = [
    'slowaes',
    'ecdsa',
    'pbkdf2',
    'requests',
    'jsonrpclib',
    'six',
    'appdirs',
    'keyring==10.4.0',
    'lbryschema==0.0.15',
]

console_scripts = [
    'lbryum = lbryum.main:main',
]

base_dir = os.path.abspath(os.path.dirname(__file__))

setup(
    name="lbryum",
    version=__version__,
    install_requires=requires,
    packages=find_packages(exclude=['tests']),
    package_data={'lbryum': ['wordlist/*.txt']},
    entry_points={'console_scripts': console_scripts},
    description="Lightweight LBRYcrd Wallet",
    author="LBRY Inc.",
    author_email="hello@lbry.io",
    license="GNU GPLv3",
    url="https://lbry.io",
    long_description="""Lightweight LBRYcrd Wallet""",
    zip_safe=False
)
