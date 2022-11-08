from setuptools import setup,find_packages

setup(
    name='projectTron',
    packages=['projectTron','projectTron.auth','projectTron.game',"projectTron.rooms","projectTron.user","projectTron.utils"],
    include_package_data=True,
    install_requires=[
        'quart',
    ],
)
