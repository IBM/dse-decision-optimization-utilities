# How to release a new version?

Steps:
1. Change the version in the files `dse_do_utils.version.py` to something like `0.2.0`. 
(`setup.py` and `/docs/source/conf.py` now automatically gets it from `version.py`)`
Update the CHANGELOG.md (version and release date)

2. Regenerate the documentation with `make html` (see `docs/doc_readme.md`). 
Open Terminal (Alt+F12), `cd docs`, run <br>
`make clean`
`make html`
If Powershell:
`cmd.exe /c make html`
Or first switch to classic cmd using `cmd`.
Note that if you added/removed modules, you first need to re-run the sphinx command:
`sphinx-apidoc -f -o source/ ../dse_do_utils/`

3. For PyPI, build the wheel file.
   a. Delete all files in `./dist`
   b. Open Terminal, from root, run <br>
   `python setup.py sdist bdist_wheel`

5. Upload to PyPI (from PyCharm terminal run):<br>
`twine upload dist/*  --verbose`
Enter username and password when prompted.
NEW_2024-11-26: use API token. UN = `__token__`, PW: <the token>
(For TestPyPI use: `twine upload --repository-url https://test.pypi.org/legacy/ dist/* --verbose`)<br>
Before the twine upload, you can check the distribution with:<br>
`twine check dist/*`

6. For JFrog, run `setup.py` with the following arguments:<br>
`python setup.py sdist bdist_wheel upload -r local`<br>
(This is in the saved PyCharm run configuration `setup_egg_wheel_artifactory`)

7. From GitGui, commit into beta branch and push into git repo.
Then either:
    1. In GitHub do a pull-request from the beta into the master, or
    2. In GitGui, switch to master and merge from beta branch. Then push into GitHub. (In case we need to resolve conflicts.)

8. In GitHub, create a new release with a tag like v0.2.0

9. In GitGui, make a new branch `v0.2.1b`

10. Change the versions in `dse_do_utils.version.py` to the next beta version, e.g. `0.2.1b`

