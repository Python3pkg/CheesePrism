CHANGES
=======	

0.4.0b4
=======
	
2014-03-03 Whit <whit@surveymonkey.com>	

	* html_free fixes: proper culling of index.json files
	* support for wheel format in requirements files uploads
        * clean up threading in functional testsb

2014-01-13 Whit <whit@surveymonkey.com>	

	* html_free: now possible to run cp totally off of nginx directory
	  view.
	* faster package index.html rebuilds (on slow disks)
	

	
0.4.0b2
=======	

2014-01-27  Whit  <whit@surveymonkey.com>
	* Make it possible to turn off form button for regeneration
          form via configuration. Useful for large indexes with button
          happy users. http endpoint still available.

2014-01-22  Whit  <whit@surveymonkey.com>
	* Refactor md5 calculation to be more memory intensive vs. io intensive
	* Minor improvement to test coverage
        * multiprocessing removed in toto


0.4.0b0
=======	

2014-01-07  Whit  <whit@surveymonkey.com>
	* Add request method to overwrite
	  `webob.request.BaseRequest.request.request_body_tempfile_limit`
	* Add `cheeseprism.temp_file_limit` configuration value to allow
	  `request_body_tempfile_limit` to be determined by config.

	
0.4.0a9
=======	

2013-12-19  Whit  <whit@surveymonkey.com>
	* fix bug with `move_on_error`. Now does move rather than failing
	* fix tests 
	
0.4.0a8
=======	

2013-12-19  Whit  <whit@surveymonkey.com>
	* Chunked updating of index.json for large indexes
	* Better logging
	* Add support for wheels
	* handle errors when extensions are unrecognized
	* fix for error wrt empty archive sets
	* skip registration when `update_data` has already been run
	* More optimizations for bulk loading and updating
	* Skip multiprocessing tests

	
0.4.0a3
=======

2013-12-11  Whit  <whit@surveymonkey.com>
	* update docs
	* deprecate process based concurrency until a better way is found
	* add a way to config different callables for naming an upload

	
0.4.0a2
=======

2013-03-21  Whit  <whit@surveymonkey.com>

	* thread and process concurrency via futures for index building
	* optional pip cache syncing
	* option to not write index.html (for use with servers w/ directory list ala nginx)
	* various performance improvements (thanks @bbinet!)


0.2a1
=====

2012-10-31  whit  <whit@surveymonkey.com>:

 * Filter non-source distribution downloads from pypi
 * Fixed bug with index.json generation for add packages via pypi
 * Index regeneration is now package by package
 * initial work on unified 'datafile' handling via transaction
 * Make 'regenerate_all' rebuild the datafile (albeit inefficiently)

	
0.1a1
=====

Initial alpha release.

Development Log
---------------

2012-01-09  whit  <whit@surveymonkey.com>:
 * Recursive download of requirements files and dependencies
 * Search of pypi and download of files
 * Improved test coverage
 * Initialization of index on start up
 * Basic read-only API for index
 * Broader event support
 * Documentation improvements

2011-12-21  whit  <whit@surveymonkey.com>:
 * Individual leaf update via event on upload
 * Refactor to use pkginfo 

2011-12-01  whit  <whit@surveymonkey.com>:
 * Housekeeping: add static fileserving for index for developments,
   more use of path.py
 * Port over emporium readme.

2011-11-07  whit  <whit@surveymonkey.com>:
 * Get app basically serving

2011-11-07  whit  <whit@surveymonkey.com>:
 * Setup initial package structure  
