from distutils.core import setup

install_requires = [
    'asciitable',
]


setup(
    name='pydpxapi',
    version='0.21',
    py_modules=['pydpxapi/api','pydpxapi/__init__'],
    url='',
    license='NIT',
    author='Christopher Matthews',
    author_email='matthews@campusnet.de',
)
