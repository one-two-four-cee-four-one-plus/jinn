import ast


class NoDefaults(ast.NodeTransformer):
    def visit_FunctionDef(self, node):
        node.args.defaults = []
        for stmt in node.body:
            self.visit(stmt)
        return node

    @classmethod
    def in_(cls, code):
        tree = ast.parse(code)
        cls().visit(tree)
        return ast.unparse(tree)


class ReplaceVariables(ast.NodeTransformer):
    def __init__(self, function_name, constants):
        self.function_name = function_name
        self.constants = constants

    def visit_FunctionDef(self, node):
        if node.name == self.function_name:
            args = []
            for arg in node.args.args:
                if arg.arg not in self.constants:
                    args.append(arg)
            node.args.args = args
        for stmt in node.body:
            self.visit(stmt)
        return node

    def visit_Name(self, node):
        if node.id in self.constants:
            value = ast.literal_eval(self.constants[node.id])
            return ast.copy_location(ast.Constant(value=value), node)
        return node

    @classmethod
    def in_(cls, function_name, code, constants):
        tree = ast.parse(code)
        tree = cls(function_name, constants).visit(tree)
        return ast.unparse(tree)


def unwrap_content(text, prefix):
    text = text.strip('\n').strip('`').replace(f"{prefix}\n", "", 1)
    if '```' in text:
        text, _ = text.split('```', 1)
    return text


def define_function(code):
    ns = {}
    exec(code, ns)
    return next(iter((name, obj) for name, obj in ns.items() if callable(obj)))
