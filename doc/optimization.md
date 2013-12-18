# Optimization journal

## Times for optimization (on size 400, 0.665 version/packages)

`notify_package_added` -> `bulk_add_pkgs`

This makes rewrites of packages O(A/P) vs O(A) where A == number of
package versions and P == number of packages. Also tried to limit the
number of times the data file was serialized and written to once per
bulk update, vs. once for every package added.

 0. 76s start
 1. 48s batch leaf rebuild
 2. 43 batch index.json writes
 3. 26.5 turn off index writing
 4. 24.5 turn off pip sync
