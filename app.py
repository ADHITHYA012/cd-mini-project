from flask import Flask, render_template, request
import re

app = Flask(__name__)


def generate_assembly(source_code):

    assembly = []

    registers = ["R1", "R2", "R3", "R4"]

    reg_map = {}

    free_regs = registers.copy()

    label_counter = 1

    lines = source_code.splitlines()

    for line in lines:

        line = line.strip()

        if not line:
            continue

        line = re.sub(r'#.*', '', line).strip()

        if not line:
            continue

        # FOR LOOP
        match = re.match(
            r'for\s+(\w+)\s+in\s+range\s*\(\s*(\d+)\s*\)\s*:?',
            line
        )

        if match:

            variable = match.group(1)
            end_value = match.group(2)

            start_label = f"L{label_counter}"
            end_label = f"L{label_counter + 1}"

            label_counter += 2

            reg = "R1"

            reg_map[variable] = reg

            assembly.append(f"MOV 0, {reg}")
            assembly.append(f"STORE {reg}, {variable}")

            assembly.append(f"{start_label}:")
            assembly.append(
                f"CMP {variable}, {end_value}"
            )
            assembly.append(
                f"JGE {end_label}"
            )

            continue

        # WHILE LOOP
        match = re.match(
            r'while\s+(\w+|\d+)\s*(<|>|<=|>=|==|!=)\s*(\w+|\d+)\s*:?',
            line
        )

        if match:

            left = match.group(1)
            operator = match.group(2)
            right = match.group(3)

            start_label = f"L{label_counter}"
            end_label = f"L{label_counter + 1}"

            label_counter += 2

            assembly.append(
                f"{start_label}:"
            )

            assembly.append(
                f"CMP {left}, {right}"
            )

            if operator == "<":
                assembly.append(
                    f"JGE {end_label}"
                )

            elif operator == ">":
                assembly.append(
                    f"JLE {end_label}"
                )

            elif operator == "<=":
                assembly.append(
                    f"JG {end_label}"
                )

            elif operator == ">=":
                assembly.append(
                    f"JL {end_label}"
                )

            elif operator == "==":
                assembly.append(
                    f"JNE {end_label}"
                )

            elif operator == "!=":
                assembly.append(
                    f"JE {end_label}"
                )

            continue

        # IF
        match = re.match(
            r'if\s+(\w+|\d+)\s*(<|>|<=|>=|==|!=)\s*(\w+|\d+)\s*:?',
            line
        )

        if match:

            left = match.group(1)
            operator = match.group(2)
            right = match.group(3)

            label = f"L{label_counter}"

            label_counter += 1

            assembly.append(
                f"CMP {left}, {right}"
            )

            if operator == "<":
                assembly.append(
                    f"JGE {label}"
                )

            elif operator == ">":
                assembly.append(
                    f"JLE {label}"
                )

            elif operator == "<=":
                assembly.append(
                    f"JG {label}"
                )

            elif operator == ">=":
                assembly.append(
                    f"JL {label}"
                )

            elif operator == "==":
                assembly.append(
                    f"JNE {label}"
                )

            elif operator == "!=":
                assembly.append(
                    f"JE {label}"
                )

            assembly.append(
                f"{label}:"
            )

            continue

        # FOR LOOP INCREMENT
        match = re.match(
            r'(\w+)\s*=\s*\1\s*\+\s*1',
            line
        )

        if match:

            variable = match.group(1)

            reg = reg_map.get(
                variable,
                "R1"
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
                f"JMP L{label_counter - 2}"
            )

            continue

        # NORMAL CALCULATION
        match = re.match(
            r'(\w+)\s*=\s*(\w+|\d+)\s*([\+\-\*/])\s*(\w+|\d+)',
            line
        )

        if match:

            dest = match.group(1)
            op1 = match.group(2)
            operator = match.group(3)
            op2 = match.group(4)

            r1 = "R1"
            r2 = "R2"

            assembly.append(
                f"MOV {op1}, {r1}"
            )

            assembly.append(
                f"MOV {op2}, {r2}"
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

            assembly.append(
                f"STORE {r1}, {dest}"
            )

            reg_map[dest] = r1

            continue

        # SIMPLE ASSIGNMENT
        match = re.match(
            r'(\w+)\s*=\s*(\w+|\d+)',
            line
        )

        if match:

            dest = match.group(1)
            value = match.group(2)

            reg = "R1"

            assembly.append(
                f"MOV {value}, {reg}"
            )

            assembly.append(
                f"STORE {reg}, {dest}"
            )

            reg_map[dest] = reg

    return "\n".join(assembly)


@app.route('/')
def home():

    return render_template(
        'index.html'
    )


@app.route('/optimize', methods=['POST'])
def optimize():

    source_code = request.form['code']

    variables = sorted(
        set(
            re.findall(
                r'[a-zA-Z_]\w*',
                source_code
            )
        )
    )

    keywords = {
        "for",
        "in",
        "range",
        "while",
        "if",
        "else"
    }

    variables = [
        var
        for var in variables
        if var not in keywords
    ]

    register_result = ""

    registers = [
        "R1",
        "R2",
        "R3",
        "R4"
    ]

    for i, var in enumerate(variables):

        if i < len(registers):

            register_result += (
                f"{var} → {registers[i]}\n"
            )

        else:

            register_result += (
                f"{var} → MEMORY\n"
            )

    instruction_result = generate_assembly(
        source_code
    )

    return render_template(
        'index.html',
        code=source_code,
        register=register_result,
        instruction=instruction_result
    )


if __name__ == '__main__':

    app.run(
        debug=True
    )
