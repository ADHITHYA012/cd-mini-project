from flask import Flask, render_template, request
import re

app = Flask(__name__)


def is_number(value):
    return re.fullmatch(r"-?\d+", value) is not None


def allocate_register(var, reg_map, free_regs):
    if var in reg_map:
        return reg_map[var]

    if free_regs:
        reg = free_regs.pop(0)
        reg_map[var] = reg
        return reg

    return None


def get_register(var, reg_map, free_regs):
    if var in reg_map:
        return reg_map[var]

    return allocate_register(
        var,
        reg_map,
        free_regs
    )


def load_value(value, reg_map, free_regs, assembly):

    if is_number(value):
        reg = free_regs.pop(0) if free_regs else "R1"

        assembly.append(
            f"MOV {value}, {reg}"
        )

        return reg

    reg = get_register(
        value,
        reg_map,
        free_regs
    )

    if reg is None:
        reg = "R1"

    assembly.append(
        f"MOV {value}, {reg}"
    )

    return reg


def generate_expression(
    dest,
    op1,
    operator,
    op2,
    reg_map,
    free_regs,
    assembly
):

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

    reg_map[dest] = r1

    assembly.append(
        f"STORE {r1}, {dest}"
    )

    if r2 != r1 and r2 in reg_map.values():

        used_variables = [
            v
            for v, r in reg_map.items()
            if r == r2
        ]

        for variable in used_variables:
            if variable != dest:
                del reg_map[variable]

        if r2 not in free_regs:
            free_regs.append(r2)


def generate_simple_assignment(
    dest,
    value,
    reg_map,
    free_regs,
    assembly
):

    reg = load_value(
        value,
        reg_map,
        free_regs,
        assembly
    )

    reg_map[dest] = reg

    assembly.append(
        f"STORE {reg}, {dest}"
    )


def generate_condition(
    left,
    operator,
    right,
    false_label,
    assembly
):

    assembly.append(
        f"CMP {left}, {right}"
    )

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


def clean_source(source_code):

    source_code = re.sub(
        r"#include\s*<[^>]+>",
        "",
        source_code
    )

    source_code = re.sub(
        r"#include\s*\"[^\"]+\"",
        "",
        source_code
    )

    source_code = re.sub(
        r"//.*",
        "",
        source_code
    )

    source_code = re.sub(
        r"/\*.*?\*/",
        "",
        source_code,
        flags=re.DOTALL
    )

    return source_code


def generate_assembly(source_code):

    source_code = clean_source(source_code)

    assembly = []

    reg_map = {}

    free_regs = [
        "R1",
        "R2",
        "R3",
        "R4"
    ]

    label_counter = 1

    control_stack = []

    lines = source_code.splitlines()

    for line in lines:

        line = line.strip()

        if not line:
            continue

        if line in ["{", "}"]:
            continue

        if line.startswith("printf"):
            continue

        if line.startswith("return"):
            continue

        if line == "int main()" or line == "main()":
            continue

        if line.startswith("int main"):
            continue

        line = line.rstrip(";").strip()

        if not line:
            continue

        if line == "else":
            if control_stack:

                current = control_stack[-1]

                if current["type"] == "if":

                    end_label = f"L{label_counter}"
                    label_counter += 1

                    current["end"] = end_label

                    assembly.append(
                        f"JMP {end_label}"
                    )

                    assembly.append(
                        f"{current['else_label']}:"
                    )

            continue

        if line.startswith("if"):

            match = re.match(
                r"if\s*\(\s*"
                r"(\w+|\d+)\s*"
                r"(<=|>=|==|!=|<|>)\s*"
                r"(\w+|\d+)"
                r"\s*\)",
                line
            )

            if match:

                left = match.group(1)
                operator = match.group(2)
                right = match.group(3)

                false_label = f"L{label_counter}"
                label_counter += 1

                control_stack.append({
                    "type": "if",
                    "else_label": false_label
                })

                generate_condition(
                    left,
                    operator,
                    right,
                    false_label,
                    assembly
                )

            continue

        if line.startswith("while"):

            match = re.match(
                r"while\s*\(\s*"
                r"(\w+|\d+)\s*"
                r"(<=|>=|==|!=|<|>)\s*"
                r"(\w+|\d+)"
                r"\s*\)",
                line
            )

            if match:

                left = match.group(1)
                operator = match.group(2)
                right = match.group(3)

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

                generate_condition(
                    left,
                    operator,
                    right,
                    end_label,
                    assembly
                )

            continue

        if line.startswith("for"):

            match = re.match(
                r"for\s*\(\s*"
                r"(\w+)\s*=\s*"
                r"(\d+)\s*;\s*"
                r"(\w+)\s*"
                r"(<=|>=|<|>)\s*"
                r"(\w+|\d+)\s*;\s*"
                r"(\w+)\s*=\s*"
                r"(\w+)\s*"
                r"([\+\-])\s*"
                r"(\d+)"
                r"\s*\)",
                line
            )

            if match:

                variable = match.group(1)
                start_value = match.group(2)

                condition_var = match.group(3)
                condition_op = match.group(4)
                condition_value = match.group(5)

                increment_var = match.group(6)
                increment_base = match.group(7)
                increment_op = match.group(8)
                increment_value = match.group(9)

                start_label = f"L{label_counter}"
                end_label = f"L{label_counter + 1}"

                label_counter += 2

                control_stack.append({
                    "type": "for",
                    "variable": variable,
                    "condition_var": condition_var,
                    "condition_op": condition_op,
                    "condition_value": condition_value,
                    "increment_var": increment_var,
                    "increment_base": increment_base,
                    "increment_op": increment_op,
                    "increment_value": increment_value,
                    "start": start_label,
                    "end": end_label
                })

                generate_simple_assignment(
                    variable,
                    start_value,
                    reg_map,
                    free_regs,
                    assembly
                )

                assembly.append(
                    f"{start_label}:"
                )

                generate_condition(
                    condition_var,
                    condition_op,
                    condition_value,
                    end_label,
                    assembly
                )

            continue

        match = re.match(
            r"(?:int|float|double|char)\s+"
            r"(\w+)\s*=\s*"
            r"(\w+|\d+)\s*"
            r"([\+\-\*/])\s*"
            r"(\w+|\d+)",
            line
        )

        if match:

            dest = match.group(1)
            op1 = match.group(2)
            operator = match.group(3)
            op2 = match.group(4)

            generate_expression(
                dest,
                op1,
                operator,
                op2,
                reg_map,
                free_regs,
                assembly
            )

            continue

        match = re.match(
            r"(?:int|float|double|char)\s+"
            r"(\w+)\s*=\s*"
            r"(\w+|\d+)",
            line
        )

        if match:

            dest = match.group(1)
            value = match.group(2)

            generate_simple_assignment(
                dest,
                value,
                reg_map,
                free_regs,
                assembly
            )

            continue

        match = re.match(
            r"(?:int|float|double|char)\s+"
            r"(\w+)\s*$",
            line
        )

        if match:

            variable = match.group(1)

            get_register(
                variable,
                reg_map,
                free_regs
            )

            continue

        match = re.match(
            r"(\w+)\s*=\s*"
            r"(\w+|\d+)\s*"
            r"([\+\-\*/])\s*"
            r"(\w+|\d+)",
            line
        )

        if match:

            dest = match.group(1)
            op1 = match.group(2)
            operator = match.group(3)
            op2 = match.group(4)

            generate_expression(
                dest,
                op1,
                operator,
                op2,
                reg_map,
                free_regs,
                assembly
            )

            continue

        match = re.match(
            r"(\w+)\s*=\s*"
            r"(\w+|\d+)",
            line
        )

        if match:

            dest = match.group(1)
            value = match.group(2)

            generate_simple_assignment(
                dest,
                value,
                reg_map,
                free_regs,
                assembly
            )

            continue

        if line == "}":

            if control_stack:

                current = control_stack.pop()

                if current["type"] == "while":

                    assembly.append(
                        f"JMP {current['start']}"
                    )

                    assembly.append(
                        f"{current['end']}:"
                    )

                elif current["type"] == "for":

                    variable = current["increment_var"]

                    reg = get_register(
                        variable,
                        reg_map,
                        free_regs
                    )

                    if reg is None:
                        reg = "R1"

                    assembly.append(
                        f"MOV {variable}, {reg}"
                    )

                    if current["increment_op"] == "+":

                        assembly.append(
                            f"ADD {reg}, {current['increment_value']}"
                        )

                    else:

                        assembly.append(
                            f"SUB {reg}, {current['increment_value']}"
                        )

                    assembly.append(
                        f"STORE {reg}, {variable}"
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
                            f"{current['else_label']}:"
                        )

    return "\n".join(assembly)


def get_variables(source_code):

    source_code = clean_source(source_code)

    variables = set()

    declarations = re.findall(
        r"\b(?:int|float|double|char)\s+"
        r"([a-zA-Z_]\w*)",
        source_code
    )

    variables.update(declarations)

    assignments = re.findall(
        r"\b([a-zA-Z_]\w*)\s*=",
        source_code
    )

    variables.update(assignments)

    for_loop = re.findall(
        r"for\s*\(\s*"
        r"(?:int\s+)?([a-zA-Z_]\w*)\s*=",
        source_code
    )

    variables.update(for_loop)

    keywords = {
        "int",
        "float",
        "double",
        "char",
        "void",
        "main",
        "return",
        "for",
        "while",
        "if",
        "else",
        "printf",
        "scanf",
        "include"
    }

    variables = [
        variable
        for variable in variables
        if variable not in keywords
    ]

    return sorted(variables)


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

    for i, variable in enumerate(variables):

        if i < len(registers):

            register_result += (
                f"{variable} → {registers[i]}\n"
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
