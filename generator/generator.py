import re
import json
import string
import random
import subprocess

from   os      import path, mkdir, makedirs
from   os.path import normpath, dirname
from   shutil  import copyfile, copytree, rmtree
from   pathlib import Path
from   jinja2  import Environment, FileSystemLoader, Template, StrictUndefined

from   generator.config_feature_keywords import available_features
from   generator.config_feature_keywords import config_feature_keywords, config_feature_keywords_derived
from   generator.config_feature_paths    import config_feature_paths


# Constants to be used elsewhere

VERSION       = 'v0.1.0'

BASE_PATH     = dirname(path.realpath(__file__))
TEMPLATE_PATH = normpath(path.join(BASE_PATH, '..', 'templates'))

ALL_FEATURES  = list(available_features.keys())
ALL_KEYWORDS  = list(config_feature_keywords.keys())
ALL_FILES     = list(config_feature_paths.keys())


# Functions

def randomString(stringLength=10):
    """ Generate a random string of fixed length """

    letters = string.ascii_lowercase + string.digits
    return ''.join(random.choice(letters) for i in range(stringLength))


def run_cmd(cmd, get_lines=False):
    ''' Run a command in the shell and return the output. '''

    result = subprocess.run(cmd, stdout=subprocess.PIPE)
    decoded = result.stdout.decode('utf-8')
    return decoded if not get_lines else decoded.split('\n')


def get_required_keywords(selected_features):
    """ Get the keywords that are to be chosen according to the selected features """

    required_features = ['common'] + selected_features

    required_keywords = []
    for keyword in config_feature_keywords:
        for feature_combination in config_feature_keywords[keyword]['features']:
            if all([item in required_features for item in feature_combination]):
                required_keywords.append(keyword)

    return required_keywords


def get_required_env_vars(selected_features):
    """ Get the keywords that are to be chosen according to the selected features """

    required_keywords = get_required_keywords(selected_features)
    required_env_vars = [var for var in required_keywords if config_feature_keywords[var]['environment']]

    return required_env_vars


def find_invalid_keywords(selected_keywords):
    """ Find whether any of the chosen keywords does not meet the defined regex """

    return [keyword for keyword, value in selected_keywords.items() if not re.match(config_feature_keywords[keyword]['sanitize'], value)]


def check_required_keywords(selected_features, selected_keywords):
    """ Find whether any of the needed keywords has not been chosen """

    required_keywords = get_required_keywords(selected_features)
    return all([item in selected_keywords.keys() for item in required_keywords if not config_feature_keywords[item]['environment']])


def find_missing_keywords(selected_features, selected_keywords):
    """ Find which needed keywords have not been chosen """

    required_keywords = get_required_keywords(selected_features)
    return [item for item in required_keywords if not item in selected_keywords.keys()]


def get_keyword_info(selected_features):
    """ Get info for the user to choose the keywords """

    keyword_info = {}
    for feature in get_required_keywords(selected_features):
        feature_cfg = config_feature_keywords[feature]
        if feature_cfg['secret']:
            continue
        new_keyword_info = {
            'name': feature_cfg['name'],
            'description': feature_cfg['description'],
            'default': feature_cfg['default'],
        }
        if feature_cfg['features'][0][0] in keyword_info:
            keyword_info[feature_cfg['features'][0][0]][feature] = new_keyword_info
        else:
            keyword_info[feature_cfg['features'][0][0]] = {feature: new_keyword_info}

    return keyword_info


def get_required_files(selected_features):
    """ Find which template files are required for the selected features """

    required_features = ['common'] + selected_features

    required_files = []
    for path in config_feature_paths:
        for feature_combination in config_feature_paths[path]['features']:
            if all([item in required_features for item in feature_combination]):
                required_files.append(path)

    return required_files


def get_templated(template, parameters):
    """ Get the given template filled with the chosen keywords """

    template = Template(template)
    return template.render(parameters)


def gen_env_template(selected_features, output_path=None):
    """ Get the given template filled with the chosen keywords """

    required_env_vars = get_required_env_vars(selected_features)
    env_template = ''
    for var in required_env_vars:
        env_template += var[3:] + '=' + (config_feature_keywords[var]['default'] \
            if not config_feature_keywords[var]['secret'] else '') + '\n'
    if output_path:
        with open(output_path, 'w') as output_file:
            output_file.write(env_template)
    else:
        return env_template


def gen_files(required_files, selected_features, selected_keywords, output_path):
    """Generate templated files for selected features.

    Args:
        required_files (list)
        selected_features (list)
        selected_keywords (dict)
            {
                'FS_KEYWORD': SelectedKeyWordValue,
                'FS_KEYWORD': ...,
            }
        output_path (str)
    """

    if not path.exists(output_path):
        makedirs(output_path)

    # Save the config used to generate
    config = {
        'selected_features': selected_features,
        'selected_keywords': selected_keywords,
    }

    config['generator_info'] = {
        'previous': {
            'selected_features': selected_features,
            'selected_keywords': selected_keywords,
            'version': VERSION,
        },
    }

    config_path = path.join(output_path, '.fill-stack_config.json')
    with open(config_path, "w") as config_file:
        config_file.write(json.dumps(config, indent=4, sort_keys=True))

    # Create templated versions of the files that are needed
    file_loader = FileSystemLoader(TEMPLATE_PATH)
    jinja_env = Environment(loader=file_loader, trim_blocks=True, lstrip_blocks=True)
    jinja_env.undefined = StrictUndefined
    selected_keywords.update(
        {k: v(selected_keywords) for k, v in config_feature_keywords_derived.items()}
    )
    template_values = selected_keywords
    template_values['render_features'] = {feature: feature in selected_features for feature in ALL_FEATURES}

    for required_file in required_files:
        required_file_templated_path = get_templated(config_feature_paths[required_file]['template'], template_values)
        new_path = path.join(output_path, required_file_templated_path)
        if (new_path[-1] == '/'):
            if not path.exists(new_path):
                makedirs(new_path)
        elif (config_feature_paths[required_file]['binary']):
            copyfile(path.join(TEMPLATE_PATH, required_file), new_path)
        else:
            with open(new_path, 'w') as output_file:
                template = jinja_env.get_template(required_file)
                templated_file = template.render(template_values)
                output_file.write(templated_file)

    gen_env_template(selected_features, path.join(output_path, '.env'))
