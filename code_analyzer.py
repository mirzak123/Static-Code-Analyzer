import os
import sys
import re
import ast


class Error:

    error_codes = {'S001': 'Too long',
                   'S002': 'Indentation is not a multiple of four',
                   'S003': 'Unnecessary semicolon',
                   'S004': 'At least two spaces required before inline comments',
                   'S005': 'TODO found',
                   'S006': 'More than two blank lines preceding a code line',
                   'S007': 'Too many spaces after construction_name(def or class)',
                   'S008': ["Class name '", "' should be written in CamelCase"],
                   'S009': ["Function name '", "' should be written in snake_case"],
                   'S010': ["Argument name '", "' should be written in snake_case"],
                   'S011': ["Variable '", "' should be written in snake_case"],
                   'S012': 'The default argument value is mutable'}

    def __init__(self, path, line_num, error_code, *args):
        self.path = path
        self.line_num = line_num
        self.error_code = error_code
        self.additional_info = args

    def message(self):
        # In errors S008-S011, name of class/function/variable/argument should be provided in error message
        if self.error_code in {'S008', 'S009', 'S010', 'S011'}:
            message = self.additional_info[0].join(Error.error_codes[self.error_code])
        else:
            message = Error.error_codes[self.error_code]
        return f"{self.path}: Line {self.line_num}: {self.error_code} {message}"


def indentation_check(line):
    return True if (len(line) - len(line.lstrip())) % 4 != 0 else False


def semicolon_check(line):
    if line.endswith(';') and '#' not in line:
        return True
    if ';' in line and '#' in line:
        if line.index(';') < line.index('#'):
            return True
    return False


def preceding_spaces_check(line):
    if '#' in line:
        i = line.index('#')
        if i > 2 and ''.join(line[i-2:i]) != '  ':
            return True
    return False


def todo_check(line):
    line = line.lower()
    if 'todo' in line and '#' in line and line.index('todo') > line.index('#'):
        return True
    return False


def spaces_after_construction_name(line):
    line = line.lstrip()
    if re.match('(class|def) ', line) and not re.match(r'(class|def) \S', line):
        return True
    return False


def camel_case_check(string):
    if not re.match(r'[A-Z]\w+', string):  # possible \w*
        return True
    return False


def snake_case_check(string):
    if not re.fullmatch(r'_*[a-z0-9_]+', string):
        return True
    return False


def file_as_strings_analyzer(file_path, lines):
    """Return list of comment and indent related errors.

    Error codes from S001 to S007:
    S001: Line longer than 79 characters
    S002: Indentation is not a multiple of 4
    S003: Unnecessary semicolon at the end of line
    S004: At least two spaces required before inline comments
    S005: TODO found in inline comment
    S006: More than two blank lines preceding a code line
    S007: More than one space after construction name (def or class)
    """

    errors = []

    for line_num, line in enumerate(lines):
        line = line.strip('\n')
        if len(line.rstrip('\n')) > 79:
            errors.append(Error(file_path, line_num + 1, 'S001'))
        if indentation_check(line):
            errors.append(Error(file_path, line_num + 1, 'S002'))
        if semicolon_check(line):
            errors.append(Error(file_path, line_num + 1, 'S003'))
        if preceding_spaces_check(line):
            errors.append(Error(file_path, line_num + 1, 'S004'))
        if todo_check(line):
            errors.append(Error(file_path, line_num + 1, 'S005'))
        if line_num > 2 and lines[line_num-3:line_num] == [''] * 3:
            errors.append(Error(file_path, line_num + 1, 'S006'))
        if spaces_after_construction_name(line):
            errors.append(Error(file_path, line_num + 1, 'S007'))

    return errors


def file_as_ast_analyzer(file_path, tree):
    """Return a list of function/class/variable naming and function argument related errors.

    Traverse an abstract syntax tree of the file to find the style errors.
    Error codes from S008 to S012:
    S008: Class name should be written in CamelCase
    S009: Function name should be written in snake_case
    S010: Argument name should be written in snake_case
    S011: Variable name should be written in snake_case
    S012: The default argument value is mutable
    """
    errors = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            if camel_case_check(class_name):
                errors.append(Error(file_path, node.lineno, 'S008', class_name))

        if isinstance(node, ast.FunctionDef):
            # check if function name is snake case
            function_name = node.name
            if snake_case_check(function_name):
                errors.append(Error(file_path, node.lineno, 'S009', function_name))

            args = node.args
            # check if arguments are snake_case
            for arg in args.args:
                if snake_case_check(arg.arg):
                    errors.append(Error(file_path, node.lineno, 'S010', function_name))
                    break

            # check if function has a mutable default argument
            for default_arg in args.defaults:
                if isinstance(default_arg, ast.List) or isinstance(default_arg, ast.Set) or \
                        isinstance(default_arg, ast.Dict):
                    errors.append(Error(file_path, node.lineno, 'S012'))

        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            variable_name = node.targets[0].id
            if snake_case_check(variable_name):
                errors.append(Error(file_path, node.lineno, 'S011', variable_name))

    return errors


def static_code_analyzer(file_path):
    """Return style error codes(S001-S012), ordered by line numbers, for a single file.

    Calls file_as_strings_analyzer(file_path, lines) and file_as_ast_analyzer(file_path, tree) to get both types of
    errors. It then sorts them based on line number(1) and error code(2) and returns this list of errors.
    Errors are stored as objects of custom class "Error".
    """

    errors = []
    with open(file_path, 'r') as file:
        code = file.read()

    lines = code.splitlines()
    errors.extend(file_as_strings_analyzer(file_path, lines))

    tree = ast.parse(code)
    errors.extend(file_as_ast_analyzer(file_path, tree))

    return sorted(errors, key=(lambda error: (error.line_num, error.error_code)))


def get_files(path):
    """Return all files contained within the root of a given directory or just a single file depending on the argument.

    Uses os.walk(path) to traverse all files and directories within a root directory.
    """

    if path.endswith('.txt') or path.endswith('.py'):  # .txt is there for personal tests
        return [path]

    path_files = []
    full_path = []
    for root, dirs, files in os.walk(path):
        full_path.append(root)
        if files:
            for file in files:
                path_files.append(os.path.join(*full_path, file))
        full_path.pop()

    return path_files


def main():
    # file/directory path gets passed as a command line argument
    file_path = sys.argv[1]
    files = get_files(file_path)

    errors = []
    for file_path in files:
        errors.extend(static_code_analyzer(file_path))
    for error in errors:
        print(error.message())


if __name__ == '__main__':
    main()

