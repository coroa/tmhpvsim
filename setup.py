import setuptools
import versioneer

with open("README.rst", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="tmhpvsim",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    author="Jonas Hörsch",
    author_email="jonas.hoersch@posteo.de",
    description="Simple PV simulation and network streaming",
    long_description=long_description,
    long_description_content_type='text/x-rst',
    url="https://github.com/coroa/tmhpvsim",
    packages=setuptools.find_packages(exclude=['docs', 'test']),
    entry_points={
        'console_scripts': [
            'metersim = tmhpvsim.metersim:metersim',
        ]
    },
    include_package_data=True,
    install_requires=[
        "click",
        "pvlib",
        "tables",
        "matplotlib",
        "xarray",
        "netcdf4",
        "pymc3",
        "siphon",
        "aio_pika",
        "arviz",
        "seaborn",
        "cdsapi"
    ],
    license='MIT',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
