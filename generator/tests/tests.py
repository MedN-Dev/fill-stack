import unittest
import sys

from   os        import path, walk
from   os.path   import abspath, join, dirname
from   shutil    import rmtree
from   random    import Random

root_path = abspath(join(dirname(abspath(__file__)), '..'))
sys.path.append(root_path)
from   generator.generator import ( BASE_PATH,
                                    TEMPLATE_PATH,
                                    ALL_FEATURES,
                                    ALL_KEYWORDS,
                                    ALL_FILES,
                                    config_feature_paths,
                                    config_feature_keywords,
                                    find_invalid_keywords,
                                    check_required_keywords,
                                    get_required_files,
                                    get_templated,
                                    gen_files,
                                    run_cmd,
                                  )


# TestCase factory

def create_TestGenerateFiles(seed):
    random = Random(seed)
    gen_seed = random.randint(0, 2^32-1)

    class TCGenerateFiles(unittest.TestCase):
        OUTPUT_PATH = path.normpath(path.join(root_path, '..', '.generated_test'))
        seed = gen_seed

        def setUp(self):
            if path.exists(self.OUTPUT_PATH):
                rmtree(self.OUTPUT_PATH)

        def test_all_features_selected(self):
            selected_keywords = {
                keyword: keyword for keyword in ALL_KEYWORDS
                if not config_feature_keywords[keyword]['environment']
            }

            # Force values
            for invalid_keyword in find_invalid_keywords(selected_keywords):
                selected_keywords[invalid_keyword] = config_feature_keywords[invalid_keyword]['default']

            selected_keywords['FS_DJANGO_SOCIALAUTH_FACEBOOK_APP_ID'] = '0123456789012345'
            selected_keywords['FS_DOMAIN'] = 'fill-stack.com'

            self.assertEqual(find_invalid_keywords(selected_keywords), [])
            self.assertTrue(check_required_keywords(ALL_FEATURES, selected_keywords))

            selected_features = ALL_FEATURES
            required_files = get_required_files(selected_features)
            self.assertEqual(required_files, ALL_FILES)

            templated_paths = {
                item:
                    get_templated(
                        config_feature_paths[item]['template'],
                        selected_keywords
                    )
                for item in required_files
            }
            files_to_generate = list(templated_paths.keys())
            self.assertEqual(files_to_generate, ALL_FILES)

            gen_files(required_files, selected_features, selected_keywords, self.OUTPUT_PATH, True)

            template_tree = []
            for root, dirs, files in walk(TEMPLATE_PATH):
                dirs[:] = [d for d in dirs if d not in ('.git',)]
                template_tree.append(root)
                template_tree.extend([path.join(root, name) for name in files if not name.endswith('.secret')])
            template_tree  = [path.relpath(file_path, TEMPLATE_PATH) if not path.isdir(file_path) else path.relpath(file_path, TEMPLATE_PATH) + '/' for file_path in template_tree][1:]
            for template_path in template_tree:
                path_in_output = path.join(self.OUTPUT_PATH, get_templated(config_feature_paths[template_path]['template'], selected_keywords))
                with self.subTest(path_in_output=path_in_output):
                    self.assertTrue(path.exists(path_in_output))

        def tearDown(self):
            pass

    return TCGenerateFiles


# Test Suite setup
def suite(n_runs):
    random = Random()

    suite = unittest.TestSuite()
    for seed in random.sample(range(2^32-1), k=n_runs):
        suite.addTest(
            unittest.defaultTestLoader.loadTestsFromTestCase(
                create_TestGenerateFiles(seed)
            )
        )

    return suite


def main():
    N_TEST_RUNS = 1

    runner = unittest.TextTestRunner()
    return runner.run(suite(N_TEST_RUNS))


if __name__ == '__main__':
    main()
