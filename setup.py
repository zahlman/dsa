import setuptools, subprocess


VERSION = (1, 0)


def commit_count():
    return str(
        subprocess.check_output('git rev-list head --count'),
        'ascii'
    ).strip()


setuptools.setup(
    name='dsa',
    version=f'{VERSION[0]}.{VERSION[1]}.{commit_count()}',
    author='Karl Knechtel',
    author_email='karl.a.knechtel@gmail.com',
    description='Data Structure Assembler',
    packages=['dsa', 'dsa.util'],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'License :: Free To Use But Restricted',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development :: Assemblers',
        'Topic :: Software Development :: Disassemblers'
    ],
    package_data={'dsa': ('structgroups/*.txt', 'types/*.txt')},
    entry_points={
        'console_scripts': [
            'dsa=dsa.ui:dsa_cli',
            'dsd=dsa.ui:dsd_cli'
        ]
    }
)
