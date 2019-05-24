# How to release a new version?

Steps:
1. Change the versions in the files `dse_do_utils.version.py` and in `/docs/source/conf.py` to something like `0.2.0`. (`setup.py` automatically gets it from `version.py`)`
2. Regenerate the documentation with `make-html` (see `docs/doc_readme.md`)
3. Commit and push to GitHub
4. In GitHub, create a new release with a tag like `v0.2.0`

JFrog:
5. Run `setup.py` with the following arguments:
`python setup.py sdist bdist_wheel upload -r local`
(This is in the saved PyCharm run configuration `setup_egg_wheel_artifactory`)

6. In GitGui, make a new branch `v0.2.1b`
7. Change the versions in `dse_do_utils.version.py` and `setup.py` to the next beta version, e.g. `0.2.1b`

