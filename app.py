from flask import Flask, render_template, request
import ast
import re

app = Flask(__name__)


# ============================================================
# REGISTER ALLOCATION
# ============================================================

def collect_variables(source_code):
    keywords = {
        "while",
        "for",
        "if",
        "else",
        "end",
        "to"
    }

    variables = set()

    for line in source_code.splitlines():

        line = re.sub(r"#.*", "", line).strip()

        if not line:
            continue

        # Remove control keywords
        cleaned = re.sub(
            r"\b(while|for|if|else|end|to)\b",
            " ",
            line
        )

        # Find identifiers
        names = re.findall(
            r"\b[a-zA-Z_]\w*\b",
            cleaned
        )

        for name in names:
            if name not in keywords:
                variables.add(name)

    return sorted(variables)


def create_register_map(source_code):

    variables = collect_variables(source_code)

    reg_map = {}

    for index, variable in enumerate(variables, start=1):
        reg_map[variable] = f"R{index}"

    return reg_map


# ============================================================
# TEMPORARY REGISTERS
# ============================================================

class TempRegisterManager:

    def __init__(self):
        self.counter = 1

    def new(self):
        reg = f"T{self.counter}"
        self.counter += 1
        return reg


# ============================================================
# EXPRESSION GENERATOR
# ============================================================

def generate_expression(node, reg_map, assembly, temp_manager):
    """
    Converts a Python-like arithmetic AST into assembly.

    Example:

        b + c * (d + e)

    becomes instructions using registers.
    """

    # --------------------------------------------------------
    # CONSTANT
    # --------------------------------------------------------

    if isinstance(node, ast.Constant):

        temp = temp_manager.new()

        assembly.append(
            f"MOV {node.value}, {temp}"
        )

        return temp

    # --------------------------------------------------------
    # VARIABLE
    # --------------------------------------------------------

    if isinstance(node, ast.Name):

        return reg_map[node.id]

    # --------------------------------------------------------
    # BINARY OPERATION
    # --------------------------------------------------------

    if isinstance(node, ast.BinOp):

        left_reg = generate_expression(
            node.left,
            reg_map,
            assembly,
            temp_manager
        )

        right_reg = generate_expression(
            node.right,
            reg_map,
            assembly,
            temp_manager
        )

        result_reg = temp_manager.new()

        assembly.append(
            f"MOV {left_reg}, {result_reg}"
        )

        if isinstance(node.op, ast.Add):

            assembly.append(
                f"ADD {result_reg}, {right_reg}"
            )

        elif isinstance(node.op, ast.Sub):

            assembly.append(
                f"SUB {result_reg}, {right_reg}"
            )

        elif isinstance(node.op, ast.Mult):

            assembly.append(
                f"MUL {result_reg}, {right_reg}"
            )

        elif isinstance(node.op, ast.Div):

            assembly.append(
                f"DIV {result_reg}, {right_reg}"
            )

        else:

            raise ValueError(
                "Unsupported arithmetic operator"
            )

        return result_reg

    # --------------------------------------------------------
    # UNARY MINUS
    # --------------------------------------------------------

    if isinstance(node, ast.UnaryOp):

        if isinstance(node.op, ast.USub):

            value_reg = generate_expression(
                node.operand,
                reg_map,
                assembly,
                temp_manager
            )

            result_reg = temp_manager.new()

            assembly.append(
                f"MOV 0, {result_reg}"
            )

            assembly.append(
                f"SUB {result_reg}, {value_reg}"
            )

            return result_reg

    raise ValueError(
        "Unsupported expression"
    )


# ============================================================
# ASSIGNMENT
# ============================================================

def generate_assignment(
    line,
    reg_map,
    assembly,
    temp_manager
):

    match = re.match(
        r"^\s*([a-zA-Z_]\w*)\s*=\s*(.+)$",
        line
    )

    if not match:
        return False

    destination = match.group(1)
    expression = match.group(2)

    if destination not in reg_map:
        raise ValueError(
            f"Unknown variable: {destination}"
        )

    try:

        tree = ast.parse(
            expression,
            mode="eval"
        )

        result_reg = generate_expression(
            tree.body,
            reg_map,
            assembly,
            temp_manager
        )

        destination_reg = reg_map[destination]

        assembly.append(
            f"MOV {result_reg}, {destination_reg}"
        )

        assembly.append(
            f"STORE {destination_reg}, {destination}"
        )

        return True

    except SyntaxError:

        raise ValueError(
            f"Invalid expression: {expression}"
        )


# ============================================================
# CONDITION
# ============================================================

def generate_condition(
    condition,
    reg_map,
    assembly,
    temp_manager
):
    """
    Generates CMP instruction and returns comparison operator.
    """

    try:

        tree = ast.parse(
            condition,
            mode="eval"
        )

    except SyntaxError:

        raise ValueError(
            f"Invalid condition: {condition}"
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

    left_reg = generate_expression(
        compare.left,
        reg_map,
        assembly,
        temp_manager
    )

    right_reg = generate_expression(
        compare.comparators[0],
        reg_map,
        assembly,
        temp_manager
    )

    operator = compare.ops[0]

    if isinstance(operator, ast.Lt):
        op = "<"

    elif isinstance(operator, ast.LtE):
        op = "<="

    elif isinstance(operator, ast.Gt):
        op = ">"

    elif isinstance(operator, ast.GtE):
        op = ">="

    elif isinstance(operator, ast.Eq):
        op = "=="

    elif isinstance(operator, ast.NotEq):
        op = "!="

    else:
        raise ValueError(
            "Unsupported comparison"
        )

    assembly.append(
        f"CMP {left_reg}, {right_reg}"
    )

    return op


# ============================================================
# FALSE-CONDITION JUMP
# ============================================================

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


# ============================================================
# ASSEMBLY GENERATOR
# ============================================================

def generate_assembly(source_code, reg_map):

    assembly = []

    label_counter = 1

    control_stack = []

    temp_manager = TempRegisterManager()

    lines = source_code.splitlines()

    for original_line in lines:

        line = re.sub(
            r"#.*",
            "",
            original_line
        ).strip()

        if not line:
            continue

        # ====================================================
        # WHILE
        # ====================================================

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

            continue

        # ====================================================
        # FOR
        #
        # for i = 0 to 5
        # ====================================================

        for_match = re.match(
            r"^for\s+([a-zA-Z_]\w*)\s*=\s*(.+?)\s+to\s+(.+)$",
            line,
            re.IGNORECASE
        )

        if for_match:

            variable = for_match.group(1)
            start_value = for_match.group(2)
            end_value = for_match.group(3)

            if variable not in reg_map:

                raise ValueError(
                    f"Unknown variable: {variable}"
                )

            variable_reg = reg_map[variable]

            start_label = f"L{label_counter}"
            end_label = f"L{label_counter + 1}"

            label_counter += 2

            control_stack.append({
                "type": "for",
                "variable": variable,
                "start": start_label,
                "end": end_label,
                "end_value": end_value
            })

            start_tree = ast.parse(
                start_value,
                mode="eval"
            )

            start_reg = generate_expression(
                start_tree.body,
                reg_map,
                assembly,
                temp_manager
            )

            assembly.append(
                f"MOV {start_reg}, {variable_reg}"
            )

            assembly.append(
                f"STORE {variable_reg}, {variable}"
            )

            assembly.append(
                f"{start_label}:"
            )

            end_tree = ast.parse(
                end_value,
                mode="eval"
            )

            end_reg = generate_expression(
                end_tree.body,
                reg_map,
                assembly,
                temp_manager
            )

            assembly.append(
                f"CMP {variable_reg}, {end_reg}"
            )

            assembly.append(
                f"JG {end_label}"
            )

            continue

        # ====================================================
        # IF
        # ====================================================

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

            continue

        # ====================================================
        # ELSE
        # ====================================================

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

            continue

        # ====================================================
        # END
        # ====================================================

        if line.lower() == "end":

            if not control_stack:

                raise ValueError(
                    "Unexpected end"
                )

            current = control_stack.pop()

            # WHILE
            if current["type"] == "while":

                assembly.append(
                    f"JMP {current['start']}"
                )

                assembly.append(
                    f"{current['end']}:"
                )

            # FOR
            elif current["type"] == "for":

                variable = current["variable"]

                variable_reg = reg_map[variable]

                assembly.append(
                    f"ADD {variable_reg}, 1"
                )

                assembly.append(
                    f"STORE {variable_reg}, {variable}"
                )

                assembly.append(
                    f"JMP {current['start']}"
                )

                assembly.append(
                    f"{current['end']}:"
                )

            # IF
            elif current["type"] == "if":

                if "end" in current:

                    assembly.append(
                        f"{current['end']}:"
                    )

                else:

                    assembly.append(
                        f"{current['else']}:"
                    )

            continue

        # ====================================================
        # ASSIGNMENT
        # ====================================================

        if "=" in line:

            generate_assignment(
                line,
                reg_map,
                assembly,
                temp_manager
            )

            continue

        raise ValueError(
            f"Unsupported statement: {line}"
        )

    if control_stack:

        raise ValueError(
            "Missing 'end' statement"
        )

    return "\n".join(assembly)


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# ============================================================
# OPTIMIZE
# ============================================================

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

        instruction_result = generate_assembly(
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

        instruction_result = ""

        register_result = ""

        error = str(e)

    return render_template(
        "index.html",
        code=source_code,
        register=register_result,
        instruction=instruction_result,
        error=error
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
