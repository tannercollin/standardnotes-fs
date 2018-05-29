import sys

if sys.version_info[0] < 3:
    print('\nPython 3 or higher required. Try:\n'
          '$ sudo pip3 install standardnotes-fs')
    sys.exit(1)

import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='standardnotes-fs',
    version='0.0.1',
    author='Tanner Collin',
    author_email='pypi@tannercollin.com',
    maintainer='Tanner Collin',
    maintainer_email='pypi@tannercollin.com',
    description='Mount your Standard Notes as a filesystem.',
    keywords='standard-notes standard-file fuse standardnotes secure encrypted notes fusepy',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/tannercollin/standardnotes-fs',
    license='GPLv3',
    install_requires=[
        'appdirs',
        'fusepy',
        'iso8601',
        'pycryptodome',
        'requests',
    ],
    python_requires='>=3',
    packages=setuptools.find_packages(),
    classifiers=(
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Natural Language :: English',
        'Operating System :: MacOS',
        'Operating System :: POSIX :: Linux',
        'Operating System :: Unix',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: System :: Filesystems',
        'Topic :: Text Editors :: Text Processing',
    ),
    entry_points={'console_scripts': ['snfs=standardnotes_fs.standardnotes_fs:main']},
)
