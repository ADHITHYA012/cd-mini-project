from flask import Flask, render_template, request
import re

app = Flask(__name__)


def clean_line(line):
    line = re.sub(r'//.*', '', line)
    line = line.strip()
    return line


def get_variables(source_code):

    keywords = {
        "auto", "break", "case", "char", "const",
        "continue", "default", "do", "double",
        "else", "enum", "extern", "float", "for",
        "goto", "if", "int", "long", "register",
        "return", "short", "signed", "sizeof",
        "static", "struct", "switch", "typedef",
        "union", "unsigned", "void", "volatile",
        "while", "include", "stdio", "h", "main",
        "printf", "scanf"
    }

    variables = set()

    declaration_pattern = re.compile(
        r'\b(?:int|float|double|char|long|short)\s+([^;]+)'
    )

    for match in declaration_pattern.finditer(source_code):

        declaration = match.group(1)

        parts = declaration.split(',')

        for part in parts:

            part = part.strip()

            variable = re.match(
                r'([a-zA-Z_]\w*)',
                part
            )

            if variable:
                name = variable.group(1)

                if name not in keywords:
                    variables.add(name)

    assignment_pattern = re.findall(
        r'\b([a-zA-Z_]\w*)\s*=',
        source_code
    )

    for variable in assignment_pattern:

        if variable not in keywords:
            variables.add(variable)

    for_pattern = re.findall(
        r'\bfor\s*\(\s*([a-zA-Z_]\w*)\s*=',
        source_code
    )

    for variable in for_pattern:

        if variable not in keywords:
            variables.add(variable)

    return sorted(variables)


def get_register(variable, reg_map, free_regs):

    if variable in reg_map:
        return reg_map[variable]

    if free_regs:

        reg = free_regs.pop(0)
        reg_map[variable] = reg

        return reg

    return "MEMORY"


def load_value(value, reg_map, free_regs, assembly):

    value = value.strip()

    if value.isdigit():

        if free_regs:

            reg = free_regs.pop(0)

        else:

            reg = "R1"

        assembly.append(
            f"MOV {value}, {reg}"
        )

        return reg

    reg = get_register(
        value,
        reg_map,
        free_regs
    )

    assembly.append(
        f"MOV {value}, {reg}"
    )

    return reg


def generate_assignment(
    destination,
    expression,
    reg_map,
    free_regs,
    assembly
):

    expression = expression.strip()

    match = re.match(
        r'^([a-zA-Z_]\w*|\d+)\s*([\+\-\*/])\s*([a-zA-Z_]\w*|\d+)$',
        expression
    )

    if match:

        op1 = match.group(1)
        operator = match.group(2)
        op2 = match.group(3)

        r1 = load_value(
            op1,
            reg_map,
            free_regs,
            assembly
        )

        r2 = load_value(
            op2,
            reg_map,
            free_regs,
            assembly
        )

        if operator == "+":
            assembly.append(
                f"ADD {r1}, {r2}"
            )

        elif operator == "-":
            assembly.append(
                f"SUB {r1}, {r2}"
            )

        elif operator == "*":
            assembly.append(
                f"MUL {r1}, {r2}"
            )

        elif operator == "/":
            assembly.append(
                f"DIV {r1}, {r2}"
            )

        reg_map[destination] = r1

        assembly.append(
            f"STORE {r1}, {destination}"
        )

        if r2 != r1 and r2 != "MEMORY":

            used = [
                v
                for v, r in reg_map.items()
                if r == r2
            ]

            for variable in used:

                if variable != destination:
                    del reg_map[variable]

            if r2 not in free_regs:
                free_regs.append(r2)

        return

    if re.match(
        r'^[a-zA-Z_]\w*$',
        expression
    ):

        source_reg = get_register(
            expression,
            reg_map,
            free_regs
        )

        reg_map[destination] = source_reg

        assembly.append(
            f"MOV {expression}, {source_reg}"
        )

        assembly.append(
            f"STORE {source_reg}, {destination}"
        )

        return

    if expression.isdigit():

        reg = get_register(
            destination,
            reg_map,
            free_regs
        )

        assembly.append(
            f"MOV {expression}, {reg}"
        )

        assembly.append(
            f"STORE {reg}, {destination}"
        )

        return


def comparison_jump(
    operator,
    false_label,
    assembly
):

    if operator == "<":
        assembly.append(
            f"JGE {false_label}"
        )

    elif operator == "<=":
        assembly.append(
            f"JG {false_label}"
        )

    elif operator == ">":
        assembly.append(
            f"JLE {false_label}"
        )

    elif operator == ">=":
        assembly.append(
            f"JL {false_label}"
        )

    elif operator == "==":
        assembly.append(
            f"JNE {false_label}"
        )

    elif operator == "!=":
        assembly.append(
            f"JE {false_label}"
        )


def generate_assembly(source_code):

    assembly = []

    reg_map = {}

    free_regs = [
        "R1",
        "R2",
        "R3",
        "R4"
    ]

    label_counter = 1

    block_stack = []

    lines = source_code.splitlines()

    for original_line in lines:

        line = clean_line(original_line)

        if not line:
            continue

        line = line.replace("{", " { ")
        line = line.replace("}", " } ")

        tokens = line.split()

        if not tokens:
            continue

        line = " ".join(tokens)

        if line.startswith("#include"):
            continue

        if line.startswith("int main"):
            continue

        if line == "{":
            continue

        if line == "return 0;":
            continue

        if line == "}":
            if block_stack:

                block = block_stack.pop()

                if block["type"] == "for":

                    variable = block["variable"]

                    reg = get_register(
                        variable,
                        reg_map,
                        free_regs
                    )

                    assembly.append(
                        f"MOV {variable}, {reg}"
                    )

                    assembly.append(
                        f"ADD {reg}, 1"
                    )

                    assembly.append(
                        f"STORE {reg}, {variable}"
                    )

                    assembly.append(
                        f"JMP {block['start']}"
                    )

                    assembly.append(
                        f"{block['end']}:"
                    )

                elif block["type"] == "while":

                    assembly.append(
                        f"JMP {block['start']}"
                    )

                    assembly.append(
                        f"{block['end']}:"
                    )

                elif block["type"] == "if":

                    assembly.append(
                        f"{block['end']}:"
                    )

            continue

        for_match = re.match(
            r'for\s*\(\s*'
            r'([a-zA-Z_]\w*)\s*=\s*'
            r'(\d+)\s*;\s*'
            r'([a-zA-Z_]\w*)\s*'
            r'(<|<=|>|>=|==|!=)\s*'
            r'(\d+)\s*;\s*'
            r'([a-zA-Z_]\w*)\s*(\+\+|--)\s*'
            r'\)\s*\{?',
            line
        )

        if for_match:

            variable = for_match.group(1)
            start_value = for_match.group(2)
            condition_variable = for_match.group(3)
            operator = for_match.group(4)
            end_value = for_match.group(5)
            increment_variable = for_match.group(6)
            increment_operator = for_match.group(7)

            start_label = f"L{label_counter}"
            end_label = f"L{label_counter + 1}"

            label_counter += 2

            reg = get_register(
                variable,
                reg_map,
                free_regs
            )

            assembly.append(
                f"MOV {start_value}, {reg}"
            )

            assembly.append(
                f"STORE {reg}, {variable}"
            )

            assembly.append(
                f"{start_label}:"
            )

            assembly.append(
                f"CMP {condition_variable}, {end_value}"
            )

            comparison_jump(
                operator,
                end_label,
                assembly
            )

            block_stack.append({
                "type": "for",
                "variable": increment_variable,
                "increment": increment_operator,
                "start": start_label,
                "end": end_label
            })

            continue

        while_match = re.match(
            r'while\s*\(\s*'
            r'([a-zA-Z_]\w*|\d+)\s*'
            r'(<|<=|>|>=|==|!=)\s*'
            r'([a-zA-Z_]\w*|\d+)'
            r'\s*\)\s*\{?',
            line
        )

        if while_match:

            left = while_match.group(1)
            operator = while_match.group(2)
            right = while_match.group(3)

            start_label = f"L{label_counter}"
            end_label = f"L{label_counter + 1}"

            label_counter += 2

            assembly.append(
                f"{start_label}:"
            )

            assembly.append(
                f"CMP {left}, {right}"
            )

            comparison_jump(
                operator,
                end_label,
                assembly
            )

            block_stack.append({
                "type": "while",
                "start": start_label,
                "end": end_label
            })

            continue

        if_match = re.match(
            r'if\s*\(\s*'
            r'([a-zA-Z_]\w*|\d+)\s*'
            r'(<|<=|>|>=|==|!=)\s*'
            r'([a-zA-Z_]\w*|\d+)'
            r'\s*\)\s*\{?',
            line
        )

        if if_match:

            left = if_match.group(1)
            operator = if_match.group(2)
            right = if_match.group(3)

            end_label = f"L{label_counter}"

            label_counter += 1

            assembly.append(
                f"CMP {left}, {right}"
            )

            comparison_jump(
                operator,
                end_label,
                assembly
            )

            block_stack.append({
                "type": "if",
                "end": end_label
            })

            continue

        if line.startswith("else"):

            if block_stack:

                block = block_stack[-1]

                if block["type"] == "if":

                    new_end = f"L{label_counter}"

                    label_counter += 1

                    assembly.append(
                        f"JMP {new_end}"
                    )

                    assembly.append(
                        f"{block['end']}:"
                    )

                    block["end"] = new_end

            continue

        declaration = re.match(
            r'(?:int|float|double|char|long|short)\s+'
            r'([a-zA-Z_]\w*)'
            r'(?:\s*=\s*(.*?))?;?$',
            line
        )

        if declaration:

            destination = declaration.group(1)
            expression = declaration.group(2)

            if expression:

                generate_assignment(
                    destination,
                    expression,
                    reg_map,
                    free_regs,
                    assembly
                )

            continue

        assignment = re.match(
            r'([a-zA-Z_]\w*)\s*=\s*(.*?)\s*;?$',
            line
        )

        if assignment:

            destination = assignment.group(1)
            expression = assignment.group(2)

            generate_assignment(
                destination,
                expression,
                reg_map,
                free_regs,
                assembly
            )

            continue

        if line.startswith("printf"):
            continue

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

    variables = get_variables(
        source_code
    )

    registers = [
        "R1",
        "R2",
        "R3",
        "R4"
    ]

    register_result = ""

    for index, variable in enumerate(variables):

        if index < len(registers):

            register_result += (
                f"{variable} → "
                f"{registers[index]}\n"
            )

        else:

            register_result += (
                f"{variable} → MEMORY\n"
            )

    instruction_result = generate_assembly(
        source_code
    )

    return render_template(
        "index.html",
        code=source_code,
        register=register_result,
        instruction=instruction_result
    )


if __name__ == "__main__":

    app.run(
        debug=True
    )
