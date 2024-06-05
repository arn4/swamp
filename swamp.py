#!/usr/bin/env python3

# Luca Arnaboldi - copyrigth 2019 - 2021
# SWAMP - Static Webite Awesome Manager & Producer 

######################## CONFIGUARTION VARIABLES #######################

#Directory where config files are stored. Absolute Path
working_path = './'
#Directory from wich the website is generated. Relative path to working_path
source_path = 'website/'
#Directory where the generated website is stored. Relative path to working_path
public_path = 'public/'
#Directory where static files are stored. Relative path to working_path
static_path = 'static/'

needed_global_conf = ['LOCATION', 'STATIC', 'DEFAULT_LANGUAGE']

# Key to be pressed to stop the program in watch mode
stop_key = 'q'

# Seconds enlapsed between 2 checks of modifications in watch mode
watch_waiting_time = 0.4

# Default Web Server Port
default_webserver_port = 8000
default_webserver_address = 'localhost'

########################### GLOBAL VARIABLES ###########################
# Dictioanry of global configuration.
config = {}

# List of dictionaries of variables. Each element of the list is a dictioanry
# of variables contained in a subpath. It is used as a stack during the
# DFS of directories.
variables = []
# List of dictionaries of files. Each element of the list is a dictioanry
# of HTML files contained in a subpath. It is used as a stack during the
# DFS of directories.
HTML_files = []

# Dictionary of list of dictionary. Each key is a language and its value a list
# used as a stack during DFS of directories. Each element of each list is a dictionary
# of language entries contained in a subpath
locale = {}

# Dictionary of links
links = {}

# Template File
template = ''

# List of alternative languages
alt_languages = []

# Dictionary of alternative languages path name for directory exploring
alt_languages_path = {}

# Boolean to create a subdirectory for the default languages
subdirectory_default_language = False

########################### EXCEPTIONS ################################
class NoLocaleError(Exception):
    pass

################################# CODE #################################

# Every time that a variable is called 'path' it's assumed that it represents
# a path relative to public_path or source_path

import yaml
import shutil
import os
import logging
import argparse
from hashlib import sha256
import getkey
import threading
import signal
import time
import hashlib
from http.server import HTTPServer, SimpleHTTPRequestHandler
import datetime
import re

## Add a '/' charracter at the end of the string path if it is not already
#  there
def makePathEndWithSlash(path):
    if not path.endswith('/'):
        return path + '/'
    else:
        return path

def makePathStartWithoutSlash(path):
    if path.startswith('/'):
        return path[1:]
    else:
        return path

def makePathNormalized(path):
    if path == '/':
        return ''
    return makePathEndWithSlash(makePathStartWithoutSlash(path))

## Return the name of last considered dir in a path.
#  Example: "some/strange/dire" --> "dire"
def getLastDirNameInPath(path):
    # I ensure that there's a final slash, so the last element of the split
    # is the empty string. The second last is what I need to return.
    try:
        return (makePathNormalized(path).split('/'))[-2]
    except IndexError:
        return ''

## Return the name of last considered dir in a path.
#  Example: "some/strange/dire" --> "some/strange/"
def popLastDirNameInPath(path):
    return makePathEndWithSlash(path[:-(len(getLastDirNameInPath(path))+1)])

## Given a path it explores all subdirectories (ignoring files!) and calls
#  pre before scanning actual dir and post after scanning
def exploreSubdirectory(path, pre = None, post = None):
    # Assert that path is correctly formatted
    path = makePathEndWithSlash(path)

    if callable(pre):
        pre(path)

    for entry in os.scandir(path):
        if entry.is_dir():
            exploreSubdirectory(entry.path, pre, post)

    if callable(post):
        post(path)

# Remove all contents of path. path must be a folder
def emptyFolder(path):
    for element in os.listdir(path):
        complete_path = os.path.join(path, element)
        try:
            if os.path.isfile(complete_path):
                os.remove(complete_path)
            elif os.path.isdir(complete_path):
                shutil.rmtree(complete_path)
        except Exception as e:
            logging.error("while empting {0} the following error: {1}".format(path, e))

## Remove all comments from an HTML code
def removeCommentsFromHTML(html_code):
    return re.sub(r"<!--(.|\s|\n)*?-->", "", html_code)

## Load a configuaration file given the path (NB: the path DOES NOT
#  include filename, wich is assumed to be 'config.yaml' by default) and
#  stores it in the global variable config.
def loadConfig(path):
    with open(path + 'config.yaml', 'r') as conffile:
        confdata = yaml.safe_load(conffile.read())

        #Assert that all basics configuration are in the file
        for n in needed_global_conf:
            assert(n in confdata)

        global config
        config = confdata
        variables.append(config)

## Load the template file given the path (NB: the path DOES NOT
#  include filename, wich is assumed to be 'template.html' by default)
def loadTemplate(path):
    with open(path + 'template.html', 'r') as templatefile:
        global template
        template = removeCommentsFromHTML(templatefile.read())

## Load the variables of the directory given by path and pushes a dictionary
#  containg them in the list of variables. If the directory does not contain
#  variables it creates an empty dictionary.
def loadVariables(path):
    if not os.path.isfile(path + 'variables.yaml'):
        variables.append({})
        return
    with open(path + 'variables.yaml', 'r') as varfile:
        new_dict = yaml.safe_load(varfile.read())

        if new_dict is None:
            new_dict = {}
        variables.append(new_dict)

## Remove last element of the list variables. Since it is used as a stack
#  it should be called after having done everything needed in a directory.
def unloadVariables():
    del variables[-1]

## Load the HTML files of the directory given by path and pushes a dictionary
#  containg them in the list of HTML files. If the directory does not contain
#  variables it creates an empty dictionary.
def loadHTMLFiles(path):
    tmp_dict = {}

    for entry in os.scandir(path):
        if entry.is_file and entry.name.endswith('.html'):
            with open(path + entry.name, 'r') as filedata:
                filedata = removeCommentsFromHTML(filedata.read())
                tmp_dict[entry.name[:-5]] = filedata

    HTML_files.append(tmp_dict)

## Remove last element of the list HTML_files. Since it is used as a stack
#  it should be called after having done everything needed in a directory.
def unloadHTMLFiles():
    del HTML_files[-1]

def empytLocale():
    for lang in alt_languages+[config['DEFAULT_LANGUAGE']]:
        locale[lang].append({})

def loadLocale(path):
    if not os.path.isfile(path + 'locale.yaml'):
        empytLocale()
        return
    with open(path + 'locale.yaml', 'r') as localefile:
        # Get the locale path names
        locale_data = yaml.safe_load(localefile.read())
        if locale_data is None:
            empytLocale()
            return
        for lang in alt_languages:
            try:
                alt_languages_path[lang] = makePathNormalized(alt_languages_path[lang] + makePathNormalized(locale_data['path_name'][lang]))
            except (KeyError, TypeError):
                alt_languages_path[lang] = makePathNormalized(alt_languages_path[lang] + makePathNormalized(getLastDirNameInPath(path[len(working_path + source_path):])))
        # Remove (if present) path_name to not include it in locale variables
        try:
            del locale_data['path_name']
        except KeyError:
            pass

        # Exploring all languages (alternatives and default)
        for lang in alt_languages+[config['DEFAULT_LANGUAGE']]:
            tmp_dict = {}
            for locale_variable in locale_data:
                try:
                    tmp_dict[locale_variable] = locale_data[locale_variable][lang]
                except KeyError:
                    pass
            locale[lang].append(tmp_dict)

def unloadLocale():
    for lang in alt_languages+[config['DEFAULT_LANGUAGE']]:
        # Removing alt_languages_path
        if lang != config['DEFAULT_LANGUAGE']:
            alt_languages_path[lang] = popLastDirNameInPath(alt_languages_path[lang])
        # Removing the locale variables
        del locale[lang][-1]

def localizedTag(name, lang, self_tag_name = None):
    build_local = sha256(lang.encode('utf-8')).hexdigest()
    build_name = name
    open_square_bracket = name.find('[')
    close_square_bracket = name.find(']')
    if open_square_bracket != -1 and close_square_bracket !=-1:
        build_local = sha256(name[open_square_bracket+1:close_square_bracket].encode('utf-8')).hexdigest()
        build_name = name[:open_square_bracket]
    else:
        build_name = name

    # Special names
    if name == 'static':
        build_local = ''
    elif build_name == 'self' and self_tag_name is not None:
        build_name = self_tag_name

    if build_name == 'self':
        print(name, lang, self_tag_name, build_name, build_local)

    return build_name + build_local

## Get the tag of the directory (contained in the file 'tag.yaml') and
#  stores it in the links dictionary.
def getPathTags(path):
    # if tag.yaml is not present it returns random tag
    if not os.path.isfile(path + 'tag.yaml'):
        return sha256(path.encode('utf-8')).hexdigest()
    with open(path + 'tag.yaml', 'r') as tagfile:
        tagdata = yaml.safe_load(tagfile.read())
        if path.startswith(working_path):
            links[localizedTag(tagdata['tag'], config['DEFAULT_LANGUAGE'])] = (makePathEndWithSlash(config['DEFAULT_LANGUAGE']) if subdirectory_default_language else '') + path[len(working_path + source_path):]
        for lang in alt_languages:
            links[localizedTag(tagdata['tag'], lang)] = makePathNormalized(lang) + alt_languages_path[lang]
        return tagdata['tag']


## Return the actual value of the variable 'name'. "Actual" means the last
#  inserted occurence of the variable 'name' in variables list.
def getVariablesValue(name):
    for dictionary in reversed(variables):
        if name in dictionary:
            return dictionary[name]
    # TODO: Raise an error if not found!


## Return the actual contenent of the file 'name'. "Actual" means the last
#  inserted occurence of file 'name' in HTML_files list.
def getHTMLFile(name):
    for dictionary in reversed(HTML_files):
        if name in dictionary:
            return dictionary[name]
    # TODO: Raise an error if not found!

## Seek for an expression in the strong code. If found it returns a string
#  containing its name, otherwise it returns None. Expression are in the
#  form: " [code] {'mark' name_of_expression 'mark'}
def expressionGetter(code, mark):
    start_index = code.find('{' + mark)
    if start_index is -1:
        return None

    end_index = code.find(mark + '}')
    if end_index is -1:
        #TODO: Raise something wich will work...
        raise VariableError('Missing end of variable')
    return code[start_index + 2:end_index]

## Replace all expression identifying a file HTML with corrispondent HTML
#  code.
def insertHTMLFiles(code):
    while True:
        name = expressionGetter(code, '#')
        if name is None:
            break
        # It replaces all occurence, not only the first one, but obiouvsly
        # it isn't a problem.
        code = code.replace('{#' + name + '#}', getHTMLFile(name), 1)
    return code

## Replace all expression identifying a variable with corrispondent actual
#  value.
def insertVariables(code):
    while True:
        name = expressionGetter(code, '$')
        if name is None:
            break
        # It replaces all occurence, not only the first one, but obiouvsly
        # it isn't a problem.
        code = code.replace('{$' + name + '$}', str(getVariablesValue(name)), 1)
    return code

## Save the 'code' in a file named 'index.html' stored in the directory
#  'path' relative to the public_path.
def pushPath(path, code):
    filename = working_path + public_path + path + 'index.html'
    os.makedirs(os.path.dirname(filename), exist_ok = True)
    with open(filename, "w+") as destination_file:
        logging.debug('Created {0}'.format(filename))
        destination_file.write(code)

def getLocale(lang, name):
    for dictionary in reversed(locale[lang]):
        if name in dictionary:
            return dictionary[name]

## It substitute the tag names for links with a localized version, to correctly map
#  different language pages
def rebuildLinksWithLocale(code, lang, self_tag_name):
    if lang not in alt_languages + [config['DEFAULT_LANGUAGE']]:
        raise ValueError(f'{lang} not in the list of alternatives languages: {alt_languages}, and not default language.')
    while True:
       name = expressionGetter(code, '_')
       if name is None:
           break
       code = code.replace('{_' + name + '_}', '{-_' + (name if name=='static' else localizedTag(name,lang,self_tag_name)) + '_-}', 1)
    code = code.replace('{-_', '{_')
    code = code.replace('_-}', '_}')
    return code

def insertLocale(code, lang):
    while True:
        content = expressionGetter(code, '%')
        if content is None:
            break
        variable_name = content[content.find('(')+1:content.find(')')]
        variable_value = content[content.find(')')+1:]
        # It replaces all occurence, not only the first one, but obiouvsly
        # it isn't a problem.
        to_insert = getLocale(lang, variable_name)
        if to_insert is None:
            to_insert = variable_value
        code = code.replace('{%('+ variable_name + ')' + variable_value + '%}', to_insert, 1)
    return code

## Given a directory 'path' loads all the data, insert all the expression
#  and push the new file to public_dir
def processDirectory(path):
    logging.debug('Working on {0}'.format(path))

    # Get info of this dir
    loadVariables(path)
    loadHTMLFiles(path)
    loadLocale(path)
    self_tag_name = getPathTags(path)

    logging.debug(alt_languages_path)

    processed_variables_file = insertVariables(insertHTMLFiles(template))

    localized_default_language = rebuildLinksWithLocale(
        insertLocale(processed_variables_file, config['DEFAULT_LANGUAGE']),
        config['DEFAULT_LANGUAGE'],
        self_tag_name
    )

    # Default language
    pushPath(path.replace(working_path + source_path,
                          makePathEndWithSlash(config['DEFAULT_LANGUAGE']) if subdirectory_default_language else ''),
             localized_default_language)

    # Alternatives
    for alt_lang in alt_languages:
        pushPath(makePathNormalized(alt_lang) + alt_languages_path[alt_lang],
                 rebuildLinksWithLocale(insertLocale(processed_variables_file, alt_lang), alt_lang, self_tag_name))

## Removes variables and HTML files from respective lists.
def releaseDirectory(path):
    unloadHTMLFiles()
    unloadVariables()
    unloadLocale()

## Given a public path replace all link expression with the correct
#  hyperlink (using the location config)
def buildLinks(path):
    with open(path + 'index.html', "r") as codefile:
        code = codefile.read()

    while True:
        tag = expressionGetter(code, '_')
        if tag is None:
            break
        try:
            code = code.replace( '{_' + tag + '_}', config['LOCATION'] + links[tag])
        except KeyError:
            raise KeyError(f'Error while replacing {tag} in {path}')

    with open(path + 'index.html', "w") as codefile:
        codefile.write(code)

def staticFilesFromList(listfilename):
    with open(listfilename) as staticfiles:
        for elementname in staticfiles:
            elementname = elementname[:-1] # remove the ending newline
            if os.path.isdir(working_path + static_path + elementname):
                try:
                    shutil.copytree(working_path + static_path + elementname,
                                    working_path + public_path + config['STATIC'] + elementname)
                except Exception as e:
                    logging.error(f'while copyng dir {elementname} the following error: {e}')
            elif os.path.isfile(working_path + static_path + elementname):
                try:
                    os.makedirs(os.path.dirname(working_path + public_path + config['STATIC'] + elementname),
                                exist_ok = True) # creating missing folders
                    shutil.copyfile(working_path + static_path + elementname,
                                 working_path + public_path + config['STATIC'] + elementname)
                except Exception as e:
                    logging.error(f'while copyng dir {elementname} the following error: {e}')
            else:
                logging.error("Unknown static file or directory: {}".format(elementname))

def generateWebsite(static_file_list = None):
    # Clear the public from old files
    #shutil.rmtree(working_path + public_path, ignore_errors = True)
    try:
        emptyFolder(working_path + public_path)
    except FileNotFoundError:
        pass

    # Load basics
    logging.info('Loading basic config...')
    loadTemplate(working_path)
    loadConfig(working_path)
    loadVariables(working_path)

    # Setting the link for static files
    links['static'] = config['STATIC']

    # Variable timestamp
    variables.append({'timestamp':str(int(datetime.datetime.now().timestamp()*1000))})

    # Setting languages configuaration
    alt_languages = []
    try:
        alt_languages[:] = config['ALT_LANGUAGES']
    except KeyError:
        pass

    alt_languages.append('meta')
    logging.info(f'Loaded alternativies languages: {alt_languages}')

    locale[config['DEFAULT_LANGUAGE']] = []
    for alt_lang in alt_languages:
        locale[alt_lang] = []
        alt_languages_path[alt_lang] = ''

    try:
        subdirectory_default_language = config['DEFAULT_LANGUAGE_SUBDIRECTORY']
    except KeyError:
        pass
    # Load global locale if it is present
    try:
        loadLocale(working_path)
    except FileNotFoundError:
        pass

    # Build all except links
    logging.info('Building pages...')
    exploreSubdirectory(working_path + source_path,
                        processDirectory,
                        releaseDirectory)
    #Build links
    logging.info('Building links...')
    exploreSubdirectory(working_path + public_path, buildLinks)

    # Copy static files to public directory
    logging.info('Copying static files...')
    if static_file_list == None:
        # copy all files
        logging.info('Copy all')
        shutil.copytree(working_path + static_path,
                        working_path + public_path + config['STATIC'])
    else:
        # copy from list
        logging.info('Copy from list {}'.format(static_file_list))
        try:
            staticFilesFromList(static_file_list)
        except FileNotFoundError as e:
            logging.error("{} not found! No static file copied.".format(static_file_list))

## Checksum of a directory. It can be used to check if a file has changed
# Credits: https://stackoverflow.com/a/7325320
def directoriesChecksum(directories):
    hash = hashlib.md5()
    for directory in directories:
        for dirpath, dirnames, filenames in os.walk(directory, topdown=True):
            dirnames.sort(key=os.path.normcase)
            filenames.sort(key=os.path.normcase)
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)

                f = open(filepath, 'rb')
                for chunk in iter(lambda: f.read(65536), b''):
                    hash.update(chunk)
    return hash.hexdigest()

## Request handler for the web server
class PublicHttpHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=working_path+public_path, **kwargs)



def main(args):
    # Parsing all arguments
    argparser = argparse.ArgumentParser(description='Static Website Generator.')
    argparser.add_argument('-d', '--debug',
                           action = 'store_true',
                           help = "activates the degub output")
    argparser.add_argument('--staticlist',
                           action = 'store',
                           help = """file containg a list of static files to be
                                     included when bulding the website""")

    argparser.add_argument('-w', '--watch',
                           action = 'store_true',
                           help = """Watch Mode. The program keep refreshing the output.\n
                                     To stop press 'Enter' or 'Ctrl-C' and then Enter.""")

    argparser.add_argument('-p', '--port',
                           action = 'store',
                           help = f"""Port on which run the webserver. Default is {default_webserver_port}""")

    argparser.add_argument('-a', '--address',
                           action = 'store',
                           help = f"""Address of the web server. Default is {default_webserver_address}.\n
                                     Works only in WatchMode.""")

    args_dictionary = vars(argparser.parse_args(args[1:])) # devo skippare il main.py come argomento

    # Debug?
    if args_dictionary['debug']:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Start web server
    webserver_address  = default_webserver_address
    if args_dictionary['address'] is not None:
        webserver_address = args_dictionary['address']
    webserver_port = default_webserver_port
    if args_dictionary['port'] is not None:
        webserver_port = int(args_dictionary['port'])

    if args_dictionary['watch']:
        http_server = HTTPServer((webserver_address, webserver_port), PublicHttpHandler)
        server_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
        server_thread.start()
        logging.info(f'Web server started at address {webserver_address}:{webserver_port}.')

    # Watch flag. I'm using list because Thread library likes only iterables...
    keep_going = [args_dictionary['watch']]

    # Implementing the stopping for the --watch option.
    # I would not like to use KeyboardInterupted option since it can stop the generation in the middle,
    # producing undesidered partial output. The solution is a thread that is listening to keyboard input
    # and throw a stop signal when key 'q' is pressed.
    #
    # For some strange reason the argoument of the function must be an iterable.
    def stop_key_listener(keep_going):
        # while keep_going[0]:
        #     key_pressed = getkey.getkey(blocking=True)
        #     if key_pressed.lower() == stop_key:
        #         keep_going[0] = False
        input()
        keep_going[0] = False

    def sigint_handler(sig, frame):
        logging.info('Press Enter to exit the program!')
        
            
    if args_dictionary['watch']:
        # Thread to catch the Enter press
        stop_watching_thread = threading.Thread(target=stop_key_listener, args=(keep_going,), name='key_capture_thread', daemon=False).start()
        # Avoid exiting when Ctrl-C is pressed
        signal.signal(signal.SIGINT, sigint_handler)
    
    checksum_source_directory = 'wrong_checksum'
    
    while True:
        actual_checksum = directoriesChecksum([working_path+source_path, working_path+ static_path, working_path])
        if checksum_source_directory != actual_checksum:
            generateWebsite(static_file_list = args_dictionary['staticlist'])
            checksum_source_directory = actual_checksum
        time.sleep(watch_waiting_time)
        if not keep_going[0]:
            break

    logging.info('Ending...')
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv))
