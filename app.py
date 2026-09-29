from flask import Flask, render_template, request
import ast
import re

app = Flask(__name__)


def collect_variables(source_code):
    keywords = {
        "while",
        "for",
        "if",
        "else",
        "int",
        "float",
        "double",
        "char",
        "long",
        "short",
        "to"
    }

    variables = set()

    for line in source_code.splitlines():
        line = re.sub(r"#.*", "", line)

        names = re.findall(
            r"\b[a-zA-Z_]\w*\b",
            line
        )

        for name in names:
            if name not in keywords:
                variables.add(name)

    return sorted(variables)


def create_register_map(source_code):
    variables = collect_variables(source_code)

    return {
        variable: f"R{i}"
        for i, variable in enumerate(variables, 1)
    }


class TempRegisterManager:

    def __init__(self):
        self.count = 1

    def new(self):
        register = f"T{self.count}"
        self.count += 1
        return register


def generate_expression(
    node,
    reg_map,
    assembly,
    temp_manager
):

    if isinstance(node, ast.Constant):

        register = temp_manager.new()

        assembly.append(
            f"MOV {node.value}, {register}"
        )

        return register

    if isinstance(node, ast.Name):

        variable = node.id

        if variable not in reg_map:
            raise ValueError(
                f"Unknown variable: {variable}"
            )

        register = reg_map[variable]

        assembly.append(
            f"MOV {variable}, {register}"
        )

        return register

    if isinstance(node, ast.UnaryOp):

        if isinstance(node.op, ast.USub):

            value_register = generate_expression(
                node.operand,
                reg_map,
                assembly,
                temp_manager
            )

            result_register = temp_manager.new()

            assembly.append(
                f"MOV 0, {result_register}"
            )

            assembly.append(
                f"SUB {result_register}, {value_register}"
            )

            return result_register

        raise ValueError(
            "Unsupported unary operator"
        )

    if isinstance(node, ast.BinOp):

        left_register = generate_expression(
            node.left,
            reg_map,
            assembly,
            temp_manager
        )

        right_register = generate_expression(
            node.right,
            reg_map,
            assembly,
            temp_manager
        )

        result_register = temp_manager.new()

        assembly.append(
            f"MOV {left_register}, {result_register}"
        )

        if isinstance(node.op, ast.Add):

            assembly.append(
                f"ADD {result_register}, {right_register}"
            )

        elif isinstance(node.op, ast.Sub):

            assembly.append(
                f"SUB {result_register}, {right_register}"
            )

        elif isinstance(node.op, ast.Mult):

            assembly.append(
                f"MUL {result_register}, {right_register}"
            )

        elif isinstance(node.op, ast.Div):

            assembly.append(
                f"DIV {result_register}, {right_register}"
            )

        else:

            raise ValueError(
                "Unsupported arithmetic operator"
            )

        return result_register

    raise ValueError(
        "Unsupported expression"
    )


def generate_assignment(
    statement,
    reg_map,
    assembly,
    temp_manager
):

    statement = statement.strip()
    statement = re.sub(
        r"^(int|float|double|char|long|short)\s+",
        "",
        statement
    )

    match = re.match(
        r"^([a-zA-Z_]\w*)\s*=\s*(.+)$",
        statement
    )

    if not match:
        raise ValueError(
            f"Invalid assignment: {statement}"
        )

    destination = match.group(1)
    expression = match.group(2).strip()

    if destination not in reg_map:
        raise ValueError(
            f"Unknown variable: {destination}"
        )

    tree = ast.parse(
        expression,
        mode="eval"
    )

    result_register = generate_expression(
        tree.body,
        reg_map,
        assembly,
        temp_manager
    )

    destination_register = reg_map[destination]

    assembly.append(
        f"MOV {result_register}, {destination_register}"
    )

    assembly.append(
        f"STORE {destination_register}, {destination}"
    )


def generate_condition(
    condition,
    reg_map,
    assembly,
    temp_manager
):

    tree = ast.parse(
        condition,
        mode="eval"
    )

    if not isinstance(
        tree.body,
        ast.Compare
    ):
        raise ValueError(
            f"Invalid condition: {condition}"
        )

    compare = tree.body

    if len(compare.ops) != 1:
        raise ValueError(
            "Only one comparison is supported"
        )

    left_register = generate_expression(
        compare.left,
        reg_map,
        assembly,
        temp_manager
    )

    right_register = generate_expression(
        compare.comparators[0],
        reg_map,
        assembly,
        temp_manager
    )

    operator = compare.ops[0]

    if isinstance(operator, ast.Lt):
        symbol = "<"

    elif isinstance(operator, ast.LtE):
        symbol = "<="

    elif isinstance(operator, ast.Gt):
        symbol = ">"

    elif isinstance(operator, ast.GtE):
        symbol = ">="

    elif isinstance(operator, ast.Eq):
        symbol = "=="

    elif isinstance(operator, ast.NotEq):
        symbol = "!="

    else:
        raise ValueError(
            "Unsupported comparison"
        )

    assembly.append(
        f"CMP {left_register}, {right_register}"
    )

    return symbol


def false_jump(operator, label):

    if operator == "<":
        return f"JGE {label}"

    if operator == "<=":
        return f"JG {label}"

    if operator == ">":
        return f"JLE {label}"

    if operator == ">=":
        return f"JL {label}"

    if operator == "==":
        return f"JNE {label}"

    if operator == "!=":
        return f"JE {label}"

    raise ValueError(
        "Unknown comparison operator"
    )


def normalize_increment(statement):

    statement = statement.strip()

    match = re.match(
        r"^(\w+)\s*\+\+$",
        statement
    )

    if match:
        return f"{match.group(1)} = {match.group(1)} + 1"

    match = re.match(
        r"^\+\+(\w+)$",
        statement
    )

    if match:
        return f"{match.group(1)} = {match.group(1)} + 1"

    match = re.match(
        r"^(\w+)\s*--$",
        statement
    )

    if match:
        return f"{match.group(1)} = {match.group(1)} - 1"

    match = re.match(
        r"^--(\w+)$",
        statement
    )

    if match:
        return f"{match.group(1)} = {match.group(1)} - 1"

    match = re.match(
        r"^(\w+)\s*\+=\s*(.+)$",
        statement
    )

    if match:
        return (
            f"{match.group(1)} = "
            f"{match.group(1)} + {match.group(2)}"
        )

    match = re.match(
        r"^(\w+)\s*-=\s*(.+)$",
        statement
    )

    if match:
        return (
            f"{match.group(1)} = "
            f"{match.group(1)} - {match.group(2)}"
        )

    return statement


def tokenize_source(source_code):

    tokens = []
    current = []
    parenthesis_depth = 0

    for char in source_code:

        if char == "(":

            parenthesis_depth += 1
            current.append(char)

        elif char == ")":

            parenthesis_depth -= 1
            current.append(char)

        elif char == "{":

            text = "".join(current).strip()

            if text:
                tokens.append(text)

            current = []
            tokens.append("{")

        elif char == "}":

            text = "".join(current).strip()

            if text:
                tokens.append(text)

            current = []
            tokens.append("}")

        elif char == ";" and parenthesis_depth == 0:

            text = "".join(current).strip()

            if text:
                tokens.append(text)

            current = []

        elif char == "\n" and parenthesis_depth == 0:

            text = "".join(current).strip()

            if text:
                tokens.append(text)

            current = []

        else:

            current.append(char)

    text = "".join(current).strip()

    if text:
        tokens.append(text)

    return tokens


def generate_assembly(
    source_code,
    reg_map
):

    assembly = []

    tokens = tokenize_source(
        source_code
    )

    label_counter = 1

    control_stack = []

    temp_manager = TempRegisterManager()

    i = 0

    while i < len(tokens):

        line = tokens[i].strip()

        if not line:
            i += 1
            continue

        if line == "{":
            i += 1
            continue

        if line == "}":

            if not control_stack:
                raise ValueError(
                    "Unexpected }"
                )

            current = control_stack[-1]

            if (
                current["type"] == "if"
                and i + 1 < len(tokens)
                and tokens[i + 1].strip().lower() == "else"
            ):

                end_label = f"L{label_counter}"
                label_counter += 1

                current["end"] = end_label

                assembly.append(
                    f"JMP {end_label}"
                )

                assembly.append(
                    f"{current['else']}:"
                )

                i += 2

                if (
                    i < len(tokens)
                    and tokens[i].strip() == "{"
                ):
                    i += 1

                continue

            current = control_stack.pop()

            if current["type"] == "while":

                assembly.append(
                    f"JMP {current['start']}"
                )

                assembly.append(
                    f"{current['end']}:"
                )

            elif current["type"] == "for":

                generate_assignment(
                    current["increment"],
                    reg_map,
                    assembly,
                    temp_manager
                )

                assembly.append(
                    f"JMP {current['start']}"
                )

                assembly.append(
                    f"{current['end']}:"
                )

            elif current["type"] == "if":

                if "end" in current:

                    assembly.append(
                        f"{current['end']}:"
                    )

                else:

                    assembly.append(
                        f"{current['else']}:"
                    )

            i += 1
            continue

        if line.lower() == "end":

            if not control_stack:
                raise ValueError(
                    "Unexpected end"
                )

            current = control_stack.pop()

            if current["type"] == "while":

                assembly.append(
                    f"JMP {current['start']}"
                )

                assembly.append(
                    f"{current['end']}:"
                )

            elif current["type"] == "for":

                generate_assignment(
                    current["increment"],
                    reg_map,
                    assembly,
                    temp_manager
                )

                assembly.append(
                    f"JMP {current['start']}"
                )

                assembly.append(
                    f"{current['end']}:"
                )

            elif current["type"] == "if":

                if "end" in current:

                    assembly.append(
                        f"{current['end']}:"
                    )

                else:

                    assembly.append(
                        f"{current['else']}:"
                    )

            i += 1
            continue

        if line.lower() == "else":

            if not control_stack:
                raise ValueError(
                    "Unexpected else"
                )

            current = control_stack[-1]

            if current["type"] != "if":
                raise ValueError(
                    "else without if"
                )

            end_label = f"L{label_counter}"
            label_counter += 1

            current["end"] = end_label

            assembly.append(
                f"JMP {end_label}"
            )

            assembly.append(
                f"{current['else']}:"
            )

            i += 1
            continue

        while_match = re.match(
            r"^while\s*\((.*)\)\s*$",
            line,
            re.IGNORECASE
        )

        if not while_match:

            while_match = re.match(
                r"^while\s+(.+)$",
                line,
                re.IGNORECASE
            )

        if while_match:

            condition = while_match.group(1)

            start_label = f"L{label_counter}"
            end_label = f"L{label_counter + 1}"

            label_counter += 2

            control_stack.append({
                "type": "while",
                "start": start_label,
                "end": end_label
            })

            assembly.append(
                f"{start_label}:"
            )

            operator = generate_condition(
                condition,
                reg_map,
                assembly,
                temp_manager
            )

            assembly.append(
                false_jump(
                    operator,
                    end_label
                )
            )

            i += 1
            continue

        for_match = re.match(
            r"^for\s*\((.*)\)\s*$",
            line,
            re.IGNORECASE
        )

        if for_match:

            header = for_match.group(1)

            parts = [
                part.strip()
                for part in header.split(";")
            ]

            if len(parts) != 3:

                raise ValueError(
                    "For loop must be: "
                    "for(i = 0; i < 5; i++)"
                )

            initialization = parts[0]
            condition = parts[1]
            increment = normalize_increment(
                parts[2]
            )

            initialization = re.sub(
                r"^(int|float|double|char|long|short)\s+",
                "",
                initialization
            )

            start_label = f"L{label_counter}"
            end_label = f"L{label_counter + 1}"

            label_counter += 2

            generate_assignment(
                initialization,
                reg_map,
                assembly,
                temp_manager
            )

            control_stack.append({
                "type": "for",
                "start": start_label,
                "end": end_label,
                "increment": increment
            })

            assembly.append(
                f"{start_label}:"
            )

            operator = generate_condition(
                condition,
                reg_map,
                assembly,
                temp_manager
            )

            assembly.append(
                false_jump(
                    operator,
                    end_label
                )
            )

            i += 1
            continue

        if_match = re.match(
            r"^if\s*\((.*)\)\s*$",
            line,
            re.IGNORECASE
        )

        if not if_match:

            if_match = re.match(
                r"^if\s+(.+)$",
                line,
                re.IGNORECASE
            )

        if if_match:

            condition = if_match.group(1)

            else_label = f"L{label_counter}"
            label_counter += 1

            control_stack.append({
                "type": "if",
                "else": else_label
            })

            operator = generate_condition(
                condition,
                reg_map,
                assembly,
                temp_manager
            )

            assembly.append(
                false_jump(
                    operator,
                    else_label
                )
            )

            i += 1
            continue

        line = line.rstrip(";").strip()

        line = normalize_increment(line)

        if "=" in line:

            generate_assignment(
                line,
                reg_map,
                assembly,
                temp_manager
            )

            i += 1
            continue

        raise ValueError(
            f"Unsupported statement: {line}"
        )

    if control_stack:

        raise ValueError(
            "Missing closing brace or end"
        )

    return "\n".join(assembly)


@app.route("/")
def home():

    return render_template(
        "index.html"
    )


@app.route(
    "/optimize",
    methods=["POST"]
)
def optimize():

    source_code = request.form.get(
        "code",
        ""
    )

    try:

        reg_map = create_register_map(
            source_code
        )

        assembly = generate_assembly(
            source_code,
            reg_map
        )

        register_result = "\n".join(
            f"{variable} → {register}"
            for variable, register
            in reg_map.items()
        )

        error = ""

    except Exception as e:

        register_result = ""

        assembly = ""

        error = str(e)

    return render_template(
        "index.html",
        code=source_code,
        register=register_result,
        instruction=assembly,
        error=error
    )


if __name__ == "__main__":
    app.run(
        debug=True
    )
