""" setup """

import setuptools

with open("README.md", "r") as fh:
    LONG_DESCRIPTION = fh.read()

setuptools.setup(
    name='stereo_pyspin',
    version='0.0.3',
    author='Justin Blaber',
    author_email='justin.blaber@vanderbilt.edu',
    description='A simple stereo camera library using PySpin',
    long_description=LONG_DESCRIPTION,
    url='https://github.com/justinblaber/stereo_pyspin',
    packages=setuptools.find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'matplotlib==2.2.2',
        'numpy==1.14.2',
        'opencv-python==3.4.0.12',
        'Pillow==5.1.0',
        'PyYAML==3.12',
    ],
    classifiers=(
        'Programming Language :: Python :: 3.5',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
    ),
    py_modules=['stereo_pyspin'],
    scripts=['stereo_pyspin_gui'],
    data_files=[('', ['primary.yaml']),
                ('', ['secondary.yaml'])]
)
