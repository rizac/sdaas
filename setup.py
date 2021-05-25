from setuptools import setup, find_packages

_README = """
Python program to compute amplitude anomaly score on one or more seismic
waveforms (data and metadata)
"""

setup(
    name='sdaas',
    version='1.2.0',
    description=_README,
    url='https://github.com/rizac/sdaas',
    packages=find_packages(exclude=['tests', 'tests.*']),
    python_requires='>=3.7.3',
    # Minimal requirements, for a complete list see requirements-*.txt
    install_requires=[
        'numpy>=1.15.4',
        'obspy>=1.1.1',
        'scikit-learn>=0.21.3'
    ],
    # List additional groups of dependencies here (e.g. development
    # dependencies). You can install these using the following syntax,
    # for example:
    # $ pip install -e .[jupyter,test]
    extras_require={
        # 'jupyter': [
        #     'jupyter>=1.1.0'
        # ],
        'test': []
    },
    author='riccardo zaccarelli',
    author_email='',  # FIXME: what to provide?
    maintainer='Section 2.6 (Seismic Hazard and Risk Dynamics), GFZ Potsdam',  # FIXME
    maintainer_email='',
    classifiers=(
        'Development Status :: 1 - Beta',
        'Intended Audience :: Education',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU General Public License v3',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Topic :: Scientific/Engineering',
    ),
    keywords=[
        "seismic waveform",
        "isolation forest",
        "outlier score",
        "anomaly detection",
        "machine learning"
    ],
    license="GPL3",
    platforms=["any"],  # FIXME: shouldn't be unix/macos? (shallow google search didn't help)
    # package_data={"smtk": [
    #    "README.md", "LICENSE"]},

    # make the installation process copy also the iforest models (see MANIFEST.in)
    # for info see https://python-packaging.readthedocs.io/en/latest/non-code-files.html
    include_package_data=True,
    zip_safe=False,
    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points={
        'console_scripts': [
            'sdaas=sdaas.run:cli_entry_point',
        ],
    },
)
