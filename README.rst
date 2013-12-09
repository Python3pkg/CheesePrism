================
 Cheese Prism
================

.. image:: https://secure.travis-ci.org/whitmo/CheesePrism.png

A simple application for managing a static python package index.  It
borrows heavily from `BasketWeaver
<https://github.com/binarydud/basket-weaver>`_ and `cheese_emporium
<git@github.com:binarydud/cheese_emporium.git>`_.  It leverages `pip
<https://github.com/pypa/pip>`_ and setuptools/`distribute
<http://pypi.python.org/pypi/distribute>`_ for various package
management tasks.


Why?
====

There are probably better options that are more actively maintained (devpi?). 

Cheeseprism mainly excels at turning a folder full of tarballs into
something you can pip install against. And the pip cache syncing is
handy.



Running
=======

Dev
---

Install
~~~~~~~

There are 2 main ways to get your CheesePrism up and running depending
on your particular needs.


 2. Pip install the package from pypi:

    Activate your virtual env. Then either check out the code to your chosen location::

    $ git clone git://github.com/SurveyMonkey/CheesePrism.git

    and install::

    $ cd CheesePrism; pip install -e ./

 3. Pip install the source:

    Use pip to clone and install directly to ``$VIRTUAL_ENV/src``::

     $ pip install git+git://github.com/SurveyMonkey/CheesePrism.git#egg=CheesePrism
     $ cd $VIRTUAL_ENV/src/cheeseprism

Test
~~~~

If you have installed the source, to run the tests, first install the
test requirements::
 
 $ cd CheesePrism
 $ pip install -r tests-reqs.txt
 
Then::

 $ py.test

This will run tests and spit out coverage.


Run
~~~

The following will start the application and a static file server for
`CheesePrism` suitable for testing and development::

 $ pserve development.ini

You will need to install `PasteScript <http://pythonpaste.org/script/>`_
in order to run this command (``easy_install PasteScript``).

**If** you have not installed the source (ie. you installed the
package or from the strap file), you will need to copy the
development.ini to a convient location.  

You will also need to set the ini key ``cheeseprism.file_root`` to the
directory you wish your index files to live in.  

This directory may not exist yet, or could be an empty directory. If
the directory contains well formed archives, it will build the index
from what it finds there.


Production
----------

``CheesePrism`` doesn't pretend that it or python servers in general 
excel at serving flat files.

For a more durable and performantized setup, you will want to split the
serving between a wsgi host for the management application and a
industrial strength file server (say nginx).


Configure Nginx
~~~~~~~~~~~~~~~

See ``doc/sample-nginx.conf`` and replace ``alias CheesePrism/files;`` and
``alias CheesePrism/static`` with your fileroot and static filepath.
 
.. todo::

  have start up announce static and file_root (and document)


Serve management app
~~~~~~~~~~~~~~~~~~~~

Use the prod.ini (edited for your setup) for simplest serving. Be sure
to remove such things as ``pyramid.includes = pyramid_debugtoolbar``
if security is a concern::

 $ pserve prod.ini

Sane people use something like upstart or `supervisord <supervisord.org>`_ to manage this process.

.. todo:
  ini config generation script



How to use
==========


Release into your index
-----------------------

CheesePrism understand the upload interface of pypi. This means for
python2.6 and better you can setup your ``~/.pypirc`` and then upload to
your prism as you would `pypi <http://pypi.python.org/pypi>`_::

 [distutils]
    index-servers =
        pypi
        local


 [pypi]
    username:user
    password:secret

 [local]
    # your prism of fromage
    username:user
    password:secret
    repository:http://mycheese/simple


The you can upload a source ala::

  $  cd /src/MyAwesomePyPkg
  $  python setup.py sdist upload -r local


**Note**: The prism currently has the *most* basic support for pypi's
basic auth scheme.  This mainly exists for the purpose of grabbing the
identity of who puports to be uploading a package, rather than any
actual security.  If you need more, it should provide a starting point
for extension (see `pyramid documentation
<http://docs.pylonsproject.org/en/latest/docs/pyramid.html>`_ for more
information on extending pyramid apps).


Install from your index
-----------------------

**Now** your package is available for install from your prism::

  $ pip install -i http://mycheese/index/ MyAwesomePyPkg

All dependencies of ``MyAwesomePyPkg`` will also come from your prism,
so make sure they are there (coming feature will inspect your release
and do the needful).


Populate your index with your dependencies 
------------------------------------------

There are 3 main ways to load files:  

 1. If you put archives into the file root of your index and restart
    the app, it will generate index entries for them. There are plans
    to make this automagical soon so a restart is not required.

 2. Through the 'Load Requirements' page you may upload a pip
    requirements files that CheesePrism will use to populate your
    index.  Easiest way to create a pip requirements file for a
    virtualenv?::

     $ pip freeze -l > myawesomerequirement.txt

 3. Use the "Find Package" page to search pypi and load packages into
    the index. Currently this utilizes some state change on GET but 
    does remain idempotent (to be fixed soon).

See **Pip cache syncing** below for a final way to populate your
index.


JSON API
--------

There is also rudimentary read only json api::

  $ curl GET http://mycheese/index/index.json

The resulting json is a hash of objects keyed by md5 hashes of each
archive. Let's imagine our index only holds webob::

  {u'1b6795baf23f6c1553186a0a8b1a2621':{u'added': 1325609450.792506,
                                        u'filename': u'WebOb-1.2b2.zip',
                                        u'name': u'WebOb',
                                        u'version': u'1.2b2'}}

There is a per package api also (say mock is in our index)::

  $ curl GET http://mycheese/index/mock/index.json

It returns a list of the available versions for the package::

  [{"version": "1.0.1", 
    "name": "mock", 
    "mtime": 1381377142.0, 
    "atime": 1381377142.0, 
    "ctime": 1381377142.0, 
    "filename": "mock-1.0.1.tar.gz"}]


HTTP API
--------

Files may be added to the index from pypi via a not so RESTful interface 
that will soon go away.  Provided ``name`` and ``version`` exist in PyPi, the 
following will download the file from pypi and register it with the index::

 $ curl GET http://mycheese/package/{name}/{version}


Advance Feature Configuration
=============================

Cheeseprism has a few knobs that might help adapt it to your usecase.


Pip cache syncing
-----------------

Occasionally we find ourself needing to populate a virtualenv and
lacking network access.  Cheeseprism includes an optional that will,
upon starting cheeseprism, copy and index all packages in your
`PIP_DOWNLOAD_CACHE` folder, thus making them available to
install. Add this line to your ini::

  cheeseprism.pipcache_mirror=true


Configure Concurrency for index management
------------------------------------------

Under the hood for highly repetive tasks, Cheeseprism uses `futures`
to speed certain operations.

The executor may be configured like so::

  cheeseprism.futures = [thread|process]


The number of workers may be configured by::

  cheeseprism.futures.workers = 12  


By default, Cheeseprism uses the `ThreadExecutor` w/ 10
threads. Currently the `process` implementation is experimental and
may have unexpected issues depending on what server you are using.


Skip writing index.html
-----------------------

Use directory listing in nginx renderers has some advantages over
using the Cheeseprism generated index (byte counts, see all the files,
etc, faster index updating). This configuration option tells
CheesePrism to skip creating the index.html::

  cheeseprism.write_index_html = false




Future
======

Really, the future is likely an different pypi mirror like devpi.
Some features we thought about implementing:

 * **Multi-index support**:  The general idea is that you can evolve
   indexes rather like requirements files but by explicit limiting of
   membership in a group rather than specification that requires
   talking to an external index. One archive might exist in multiple
   indexes (but always serve from same location to preserve pip
   caching).
 
   This would include a ui for select member archives to compose an new index as
   well as cloning and extending an existing index.

 * **Less crap work**: automatic dependency loading for releases and
   packages loaded via find packages. A file watcher for the repo that
   rebuilds the appropriate parts of the index when files are added
   and removed.

 * **Better readonly api**: versions.json for each package with the data
   in index.json provided in a more easily consumable fashion.
     
 * **Better REST**: Make ``POST /packages/{name}/{version}`` to grab a package from PyPi. Make ``GET /packages/{name}/{version}``
   provide data about the package and indicate whether the package current lives in index or not.

 * **Proper sphinx documentation**: yup.


Contact / Wanna get involved?
=============================

Pull requests welcome! 

I'm on freenode at *#pyramid*, ``whit`` most days if you have
questions or comments.


