# How to release a new version?

Steps:
1. Change the version in the files `dse_do_utils.version.py` to something like `0.2.0`. 
(`setup.py` and `/docs/source/conf.py` now automatically gets it from `version.py`)`

2. Regenerate the documentation with `make-html` (see `docs/doc_readme.md`). 
Open Terminal (Alt+F12), `cd docs`, run <br>
`make html` 

3. For PyPI, build the wheel file.
a. Delete all files in `./dist`
b. Open Terminal, from root, run <br>
`python setup.py sdist bdist_wheel`

4. Upload to PyPI (from PyCharm terminal run):<br>
`twine upload dist/*  --verbose`
Enter username and password when prompted.
(For TestPyPI use: `twine upload --repository-url https://test.pypi.org/legacy/ dist/* --verbose`)

5. For JFrog, run `setup.py` with the following arguments:<br>
`python setup.py sdist bdist_wheel upload -r local`<br>
(This is in the saved PyCharm run configuration `setup_egg_wheel_artifactory`)

6. From GitGui, commit and push into git repo.

7. In GitHub, create a new release with a tag like v0.2.0

8. In GitGui, make a new branch `v0.2.1b`

9. Change the versions in `dse_do_utils.version.py` to the next beta version, e.g. `0.2.1b`

