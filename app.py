from flask import Flask, render_template, request
import ast
import re

app = Flask(__name__)


def remove_comments(source):

    source = re.sub(
        r"#.*",
        "",
        source
    )

    source = re.sub(
        r"//.*",
        "",
        source
    )

    return source


def split_program(source):

    source = remove_comments(source)

    source = source.replace(
        "{",
        "\n{\n"
    )

    source = source.replace(
        "}",
        "\n}\n"
    )

    source = source.replace(
        ";",
        ";\n"
    )

    lines = []

    for line in source.splitlines():

        line = line.strip()

        if line:
            lines.append(line)

    return lines


def get_variables(text):

    return set(
        re.findall(
            r"\b[a-zA-Z_]\w*\b",
            text
        )
    )


def expression_variables(expression):

    try:

        tree = ast.parse(
            expression,
            mode="eval"
        )

        return {
            node.id
            for node in ast.walk(tree)
            if isinstance(
                node,
                ast.Name
            )
        }

    except:

        return get_variables(
            expression
        )


def split_assignment(line):

    line = line.strip()

    line = line.rstrip(";")

    match = re.match(
        r"^([a-zA-Z_]\w*)\s*=\s*(.+)$",
        line
    )

    if not match:
        return None

    return (
        match.group(1),
        match.group(2).strip()
    )


def normalize_increment(line):

    line = line.strip()

    line = line.rstrip(";")

    match = re.match(
        r"^(\w+)\+\+$",
        line
    )

    if match:

        v = match.group(1)

        return f"{v} = {v} + 1"

    match = re.match(
        r"^\+\+(\w+)$",
        line
    )

    if match:

        v = match.group(1)

        return f"{v} = {v} + 1"

    match = re.match(
        r"^(\w+)--$",
        line
    )

    if match:

        v = match.group(1)

        return f"{v} = {v} - 1"

    match = re.match(
        r"^--(\w+)$",
        line
    )

    if match:

        v = match.group(1)

        return f"{v} = {v} - 1"

    match = re.match(
        r"^(\w+)\s*\+=\s*(.+)$",
        line
    )

    if match:

        v = match.group(1)
        value = match.group(2)

        return f"{v} = {v} + {value}"

    match = re.match(
        r"^(\w+)\s*-=\s*(.+)$",
        line
    )

    if match:

        v = match.group(1)
        value = match.group(2)

        return f"{v} = {v} - {value}"

    return line


def analyze_liveness(lines):

    required = set()

    assignments = []

    for index, line in enumerate(lines):

        clean = line.strip()

        if clean in {
            "{",
            "}"
        }:
            continue

        for_match = re.match(
            r"^for\s*\((.*)\)\s*$",
            clean,
            re.IGNORECASE
        )

        if for_match:

            parts = [
                x.strip()
                for x in
                for_match.group(1).split(";")
            ]

            if len(parts) == 3:

                initialization = parts[0]
                condition = parts[1]
                increment = parts[2]

                init = split_assignment(
                    initialization
                )

                if init:

                    assignments.append(
                        (
                            index,
                            init[0],
                            init[1]
                        )
                    )

                required.update(
                    expression_variables(
                        condition
                    )
                )

                increment = normalize_increment(
                    increment
                )

                inc = split_assignment(
                    increment
                )

                if inc:

                    required.add(
                        inc[0]
                    )

                    required.update(
                        expression_variables(
                            inc[1]
                        )
                    )

            continue

        while_match = re.match(
            r"^while\s*\((.*)\)\s*$",
            clean,
            re.IGNORECASE
        )

        if while_match:

            required.update(
                expression_variables(
                    while_match.group(1)
                )
            )

            continue

        if_match = re.match(
            r"^if\s*\((.*)\)\s*$",
            clean,
            re.IGNORECASE
        )

        if if_match:

            required.update(
                expression_variables(
                    if_match.group(1)
                )
            )

            continue

        assignment = split_assignment(
            clean
        )

        if assignment:

            destination = assignment[0]
            expression = assignment[1]

            assignments.append(
                (
                    index,
                    destination,
                    expression
                )
            )

    changed = True

    while changed:

        changed = False

        needed = set(required)

        for index, destination, expression in reversed(
            assignments
        ):

            if destination in needed:

                variables = expression_variables(
                    expression
                )

                before = len(needed)

                needed.update(
                    variables
                )

                if len(needed) != before:

                    changed = True

        if needed != required:

            required = needed
            changed = True

    kept_lines = []

    for index, line in enumerate(lines):

        clean = line.strip()

        assignment = split_assignment(
            clean
        )

        if assignment:

            destination = assignment[0]

            if destination not in required:

                continue

        kept_lines.append(line)

    return kept_lines, required


def create_register_map(variables):

    variables = sorted(
        variables
    )

    registers = {}

    for index, variable in enumerate(
        variables,
        1
    ):

        registers[
            variable
        ] = f"R{index}"

    return registers


class TemporaryManager:

    def __init__(self):

        self.count = 1

    def new(self):

        register = f"T{self.count}"

        self.count += 1

        return register


def generate_expression(
    node,
    registers,
    assembly,
    temporary
):

    if isinstance(
        node,
        ast.Constant
    ):

        reg = temporary.new()

        assembly.append(
            f"MOV {node.value}, {reg}"
        )

        return reg

    if isinstance(
        node,
        ast.Name
    ):

        variable = node.id

        if variable not in registers:

            raise ValueError(
                f"Variable {variable} has no register"
            )

        reg = registers[
            variable
        ]

        assembly.append(
            f"MOV {variable}, {reg}"
        )

        return reg

    if isinstance(
        node,
        ast.BinOp
    ):

        left = generate_expression(
            node.left,
            registers,
            assembly,
            temporary
        )

        right = generate_expression(
            node.right,
            registers,
            assembly,
            temporary
        )

        result = temporary.new()

        assembly.append(
            f"MOV {left}, {result}"
        )

        if isinstance(
            node.op,
            ast.Add
        ):

            assembly.append(
                f"ADD {result}, {right}"
            )

        elif isinstance(
            node.op,
            ast.Sub
        ):

            assembly.append(
                f"SUB {result}, {right}"
            )

        elif isinstance(
            node.op,
            ast.Mult
        ):

            assembly.append(
                f"MUL {result}, {right}"
            )

        elif isinstance(
            node.op,
            ast.Div
        ):

            assembly.append(
                f"DIV {result}, {right}"
            )

        else:

            raise ValueError(
                "Unsupported operator"
            )

        return result

    if isinstance(
        node,
        ast.UnaryOp
    ):

        value = generate_expression(
            node.operand,
            registers,
            assembly,
            temporary
        )

        result = temporary.new()

        assembly.append(
            f"MOV 0, {result}"
        )

        assembly.append(
            f"SUB {result}, {value}"
        )

        return result

    raise ValueError(
        "Unsupported expression"
    )


def generate_assignment(
    line,
    registers,
    assembly,
    temporary
):

    assignment = split_assignment(
        line
    )

    if not assignment:
        return

    destination = assignment[0]
    expression = assignment[1]

    if destination not in registers:

        return

    tree = ast.parse(
        expression,
        mode="eval"
    )

    result = generate_expression(
        tree.body,
        registers,
        assembly,
        temporary
    )

    destination_register = registers[
        destination
    ]

    assembly.append(
        f"MOV {result}, {destination_register}"
    )

    assembly.append(
        f"STORE {destination_register}, {destination}"
    )


def generate_condition(
    condition,
    registers,
    assembly,
    temporary
):

    tree = ast.parse(
        condition,
        mode="eval"
    )

    compare = tree.body

    if not isinstance(
        compare,
        ast.Compare
    ):

        raise ValueError(
            "Invalid condition"
        )

    left = generate_expression(
        compare.left,
        registers,
        assembly,
        temporary
    )

    right = generate_expression(
        compare.comparators[0],
        registers,
        assembly,
        temporary
    )

    assembly.append(
        f"CMP {left}, {right}"
    )

    operator = compare.ops[0]

    if isinstance(
        operator,
        ast.Lt
    ):
        return "<"

    if isinstance(
        operator,
        ast.LtE
    ):
        return "<="

    if isinstance(
        operator,
        ast.Gt
    ):
        return ">"

    if isinstance(
        operator,
        ast.GtE
    ):
        return ">="

    if isinstance(
        operator,
        ast.Eq
    ):
        return "=="

    if isinstance(
        operator,
        ast.NotEq
    ):
        return "!="

    raise ValueError(
        "Unsupported condition"
    )


def false_jump(
    operator,
    label
):

    jumps = {
        "<": f"JGE {label}",
        "<=": f"JG {label}",
        ">": f"JLE {label}",
        ">=": f"JL {label}",
        "==": f"JNE {label}",
        "!=": f"JE {label}"
    }

    return jumps[
        operator
    ]


def generate_assembly(
    lines,
    registers
):

    assembly = []

    temporary = TemporaryManager()

    stack = []

    label = 1

    for line in lines:

        line = line.strip()

        if not line:
            continue

        if line == "{":

            continue

        if line == "}":

            if not stack:
                continue

            current = stack.pop()

            if current["type"] == "for":

                generate_assignment(
                    current["increment"],
                    registers,
                    assembly,
                    temporary
                )

                assembly.append(
                    f"JMP {current['start']}"
                )

                assembly.append(
                    f"{current['end']}:"
                )

            elif current["type"] == "while":

                assembly.append(
                    f"JMP {current['start']}"
                )

                assembly.append(
                    f"{current['end']}:"
                )

            elif current["type"] == "if":

                assembly.append(
                    f"{current['end']}:"
                )

            continue

        for_match = re.match(
            r"^for\s*\((.*)\)\s*$",
            line,
            re.IGNORECASE
        )

        if for_match:

            parts = [
                x.strip()
                for x in
                for_match.group(1).split(";")
            ]

            if len(parts) != 3:

                raise ValueError(
                    "Invalid for loop"
                )

            initialization = parts[0]
            condition = parts[1]
            increment = normalize_increment(
                parts[2]
            )

            generate_assignment(
                initialization,
                registers,
                assembly,
                temporary
            )

            start_label = f"L{label}"
            end_label = f"L{label + 1}"

            label += 2

            assembly.append(
                f"{start_label}:"
            )

            operator = generate_condition(
                condition,
                registers,
                assembly,
                temporary
            )

            assembly.append(
                false_jump(
                    operator,
                    end_label
                )
            )

            stack.append({
                "type": "for",
                "start": start_label,
                "end": end_label,
                "increment": increment
            })

            continue

        while_match = re.match(
            r"^while\s*\((.*)\)\s*$",
            line,
            re.IGNORECASE
        )

        if while_match:

            condition = while_match.group(1)

            start_label = f"L{label}"
            end_label = f"L{label + 1}"

            label += 2

            assembly.append(
                f"{start_label}:"
            )

            operator = generate_condition(
                condition,
                registers,
                assembly,
                temporary
            )

            assembly.append(
                false_jump(
                    operator,
                    end_label
                )
            )

            stack.append({
                "type": "while",
                "start": start_label,
                "end": end_label
            })

            continue

        if_match = re.match(
            r"^if\s*\((.*)\)\s*$",
            line,
            re.IGNORECASE
        )

        if if_match:

            condition = if_match.group(1)

            else_label = f"L{label}"
            end_label = f"L{label + 1}"

            label += 2

            operator = generate_condition(
                condition,
                registers,
                assembly,
                temporary
            )

            assembly.append(
                false_jump(
                    operator,
                    else_label
                )
            )

            stack.append({
                "type": "if",
                "start": else_label,
                "end": end_label
            })

            continue

        if line.lower() == "else":

            if stack:

                current = stack[-1]

                if current["type"] == "if":

                    assembly.append(
                        f"JMP {current['end']}"
                    )

                    assembly.append(
                        f"{current['start']}:"
                    )

            continue

        line = line.rstrip(";")

        line = normalize_increment(
            line
        )

        if "=" in line:

            generate_assignment(
                line,
                registers,
                assembly,
                temporary
            )

    return "\n".join(
        assembly
    )


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

        original_lines = split_program(
            source_code
        )

        optimized_lines, required = analyze_liveness(
            original_lines
        )

        registers = create_register_map(
            required
        )

        assembly = generate_assembly(
            optimized_lines,
            registers
        )

        register_result = "\n".join(
            f"{variable} → {register}"
            for variable, register
            in registers.items()
        )

        optimized_source = "\n".join(
            optimized_lines
        )

        error = ""

    except Exception as e:

        optimized_source = ""

        register_result = ""

        assembly = ""

        error = str(e)

    return render_template(
        "index.html",
        code=source_code,
        optimized=optimized_source,
        register=register_result,
        instruction=assembly,
        error=error
    )


if __name__ == "__main__":

    app.run(
        debug=True
    )
