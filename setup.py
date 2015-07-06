from setuptools import find_packages
from setuptools import setup
import os

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()
CHANGES = open(os.path.join(here, 'CHANGES.rst')).read()

requires = ['Jinja2',
            'Paste',
            'futures',
            'path.py',
            'pkginfo>=1.2b1',
            'pyramid',
            'pyramid_jinja2',
            'requests',
            'pip<1.6,>1.4',
            'more-itertools']

extras_require = {
    'devpi':  ['devpi-client'],
}

version='0.4.0b5'

setup(name='CheesePrism',
      version=version,
      description='CheesePrism: your personal cheeseshop',
      long_description=README + '\n\n' +  CHANGES,
      classifiers=[
        "Programming Language :: Python",
        "Framework :: Pylons",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
      author='Whit Morriss (et al.)',
      author_email='whit-at-surveymonkey-dot-com',
      url='https://github.com/whitmo/CheesePrism',
      keywords='web pyramid pylons',
      packages=find_packages(exclude=['tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      extras_require=extras_require,
      entry_points = """\
      [paste.app_factory]
      main = cheeseprism.wsgiapp:main
      [cheeseprism.on_upload]
      devpi = cheeseprism.devpi:upload
      """
      )
