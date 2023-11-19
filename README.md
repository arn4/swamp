# Swamp

## Static Website Awesome Manager & Producer

Swamp is a software that allows you to create and manage a static website. It supports multilanguage.

## How Swamp works

Swamp builds the HTML code of a website based on the file `template.html`.

The website has the same structure as the `website/` directory, and for each path, a copy of `template.html` is inserted, where all expressions are replaced with the correct thing.

### Files

* `config.yaml`: contains the basic configuration of the project, and is present only in the main folder. Possible configurations:
  - `LOCATION`(required): which represents the URL of the main page of the website (used to build all links);
  - `STATIC`(required) the name of the directory where all static files will be saved, and which cannot, therefore, be used inside `website/`.
  - `DEFAULT_LANGUAGE` (required): name of default language.
  - `DEFAULT_LANGUAGE_SUBDIRECTORY`: it's a boolean, telling if we would like to have a directory also for the default language.
  - `ALT_LANGUAGES`: list of the alternative languages for the website. The language `meta` is automatically added to the list and just gives the locale description.
* `variables.yaml`: contains variables. It is possible to insert a copy in any website directory: the variables are overwritten for this path and for all those below it.
* `[filename].html`: contains HTML code that is likely to be replaced in the file generation. There can be an arbitrary number of them in any `website/` path.
* `tag.yaml`: is a file that contains the name of the tag to which other pages must refer to link to the current page. It is mandatory if links to this path are required. It must be inserted only in directories inside `website/`.
* `locale.yaml`: contains the specification of in the different languages available.

### Expressions

* `{#filename#}`: is replaced with the file `filename.html`.
* `{$var$}`: is replaced with the variable named `var`. The expression `{$timestamp$}` is present by default and contains a timestamp in milliseconds of when the website was generated.
* `{_tagname_}`: is replaced with the correct link to the page with the tag `tagname`. The expression `{_static_}` is by default a direct link to the directory of static files. The expression `{_self_}` is the direct link to the current page.
It is also possible to specify the language of the link to which you want to refer:

  * `{_homepage[it]_}`: is a link to the homepage in Italian (obviously if present).
  * `{_self[fr]_}`: is a link to the same page but in French (again, only if a language with tag).
* `{%(localetag) localedescription%}`: it is replaced with the corresponding translation of the string. If a translation is not available, the `localedescription` is used.

