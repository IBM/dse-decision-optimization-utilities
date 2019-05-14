# How to install and use the Spinx documentation generator.
Victor Terpstra - 23 Feb 2019

# Generate documentation - short version
To update the documentation:
1. Open a command terminal in `./docs`
2. If you have added/removed classes, run:
```
sphinx-apidoc -f -o source/ ../dse_do_utils/
```
3. Run:
```
make clean
make html
```

## Assumptions
You have a Python package of the following directory structure:
```
mypackage
    mypackage
        __init__.py
        myclassa.py
        myclassb.py
    docs
```
# Installation
Some references I used:
* https://gisellezeno.com/tutorials/sphinx-for-python-documentation.html (Good!)
* https://www.patricksoftwareblog.com/python-documentation-using-sphinx/
* https://samnicholls.net/2016/06/15/how-to-sphinx-readthedocs/
* https://media.readthedocs.org/pdf/brandons-sphinx-tutorial/latest/brandons-sphinx-tutorial.pdf

## Install Sphinx
`pip install sphinx`

## Create a docs folder
Create a folder `docs` in the main project folder (see assumptions)

## Run Sphinx Quickstart
Open a terminal in the `docs` folder and run `sphinx-quickstart`.<br>
Use all the default answers, except:
* `autodoc: automatically insert docstrings from modules` = y
* `doctest: automatically test code snippets in doctest blocks` = y

## Update conf.py
### Add to the Python path
Add the following in conf.py:<br>
`sys.path.insert(0, os.path.abspath('../..'))`<br>
This allows for Sphinx to do a `import mypackage` and get access to the source code.

## Generate API doc references
From the terminal in `docs` run:<br>
`sphinx-apidoc -f -o source/ ../mypackage/`<br>
This will generate the file `docs/source/mypackage.rst`.<br>
This file maintains references to the source-code modules.<br>
If you add/remove/rename files in the Python package, you will need to re-run this command.


# Usage
From a command line in the `docs` directory, run<br>
`make html`<br>
Optionally, run<br>
`make clean`.

(If any module in the package has been added/removed/renamed, makesure to re-run `sphinx-apidoc`, see above)


# Additional features

## Google-style Python API documentation
The default Sphinx cannot format Google-style Python documentation. We need to install  'napoleon' (See http://www.sphinx-doc.org/en/master/usage/extensions/napoleon.html)
* Add napoleon to the extensions list in conf.py
extensions = ['sphinx.ext.napoleon']
* Re-run the `sphinx-apidoc -f -o source/ ../mypackage/`

## Nicer HTML theme
The RTD theme is a lot nicer than the default Sphinx theme. (See https://sphinx-rtd-theme.readthedocs.io/en/stable/)<br>
Install the theme:<br>
`pip install sphinx_rtd_theme`<br>
Then in the conf.py file change the html_theme to:<br>
`html_theme = "sphinx_rtd_theme"`

## Sphinx warnings
Sphinx will throw warnings around the formatting of doc strings.
PyCharm doesn't show this type of warning.
Resolve by adjusting doc strings. Requires a bit of trial and error.
The line numbers in the Sphinx warning are relative to the class or method (thus do NOT correspond to the line number of the file).

## Code examples
`Pygments` can be used for code examples. See http://www.sphinx-doc.org/en/1.6/markup/code.html
Examples of Python source code or interactive sessions are represented using standard reST literal blocks.
They are started by a `::` at the end of the preceding paragraph and delimited by indentation.
```
Example::
    Start with indentation
    And another indentation
```
This will create a nice formatting in the Sphinx documentation, in particular in the rtd-theme.
Only downside: Sphinx will create warnings about an unexpected indentation.
Resolve by adding new lines around the indented code block.

You can also do an inline by using ``two quotes``
See also https://pythonhosted.org/an_example_pypi_project/sphinx.html

## Get the GitHub README.md included in the documentation
Get the contents of the GitHub project README.md included in the documentation.
See the 'mdinclude' answer in https://stackoverflow.com/questions/46278683/include-my-markdown-readme-into-sphinx.<br>
You do need to install the package M2R:<br>
https://github.com/miyakogi/m2r#sphinx-integration

Steps:
1. Install M2R: `pip install m2r`
2. Edit the conf.py file to include:
```
extensions = [
    ...,
    'm2r',
]
source_suffix = ['.rst', '.md']
```
3. Add a file called `readme_link.rst` in the `source` folder, with:
```
Readme File
===========

.. mdinclude:: ../../README.md
```
4. In `index.rst`, in the toctree add:
```
.. toctree::
   :maxdepth: 2
   :caption: Contents:

   README <readme_link>
```

Note that I first tried `recommonmark` (see https://www.sphinx-doc.org/en/master/usage/markdown.html). But I had problems installing it. Sphinx could not find the package when it was included in the extensions.


## Issue with dd_scenario:
Sphinx will parse the Python code and run into trouble when it encounters a `import dd_scenario`.
Since dd_scenario only exists in WSL and cannot be installed an your local workstation, this implies Sphinx can generate the docs.
A work-around is to add a dummy dd_scenario module and add it to the Python path.
This is the purpose of the dd_scenario.py module in the docs folder.

## Enable GitHub pages
Allow the generated documentation to be hosted on GitHub Pages.
GitHub allows you to host generated documentation (see https://help.github.com/en/articles/what-is-github-pages).
The option we will use is to place our documentation in the `master branch/docs folder`.
Challenge is that by default, Sphinx generates the docuemntation in the `docs/build` folder and because any `build` folder is ignored by git, the generated documentation is not synced into GitHub.
The work-around is:
* Generate the documentation in a folder not named `build`.
* Add a simple index.html in `docs` that redirects to the actual generated index.html

Steps:
* In `docs` create a folder `doc_build`. This will replace the `build` folder. The problem is that the `build` folder is ignored by .gitignore. So by giving ot a different name, it will be synched with GitHub.
* In the `make.bat` file, change the `BUILDDIR` to `doc_build` 
```
set BUILDDIR=doc_build
```
* Re-run `make html`
This will re-create the html folder within `doc_build`
* Create a file `index.html` in the `docs` folder with contents:
```
<meta http-equiv="refresh" content="0; url=./doc_build/html/index.html" />
```
GitHub Pages is looking for `docs/index.html`. This file redirects to the index.html in the genrated `doc_build/html` folder.
* Add en empty file called `.nojekyll` to `docs`. This will ensure the folders starting with an underscore in `doc_build/html` will not be ignored.
* Commit and push project to GitHub 
* In GitHub, go to settings. Scroll down to the section `GitHub Pages` and select the source to be `master branch/docs folder`. Then select `Save`.
GitHubwill show the link, e.g. https://pages.github.ibm.com/vterpstra/DSE_DO_Utils/

Notes: these steps are not quite the same as others suggested on various internet resources.
But this seems to me by far the simplest.
