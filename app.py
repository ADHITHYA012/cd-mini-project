from flask import Flask, render_template, request
import re

app = Flask(__name__)


def allocate_register(var, reg_map, free_regs):

    if var in reg_map:
        return reg_map[var]

    if free_regs:
        reg = free_regs.pop(0)
        reg_map[var] = reg
        return reg

    return None


def load_operand(operand, reg_map, free_regs, assembly):

    if operand.isdigit():

        if free_regs:
            reg = free_regs.pop(0)
            assembly.append(f"MOV {operand}, {reg}")
            return reg

    reg = allocate_register(
        operand,
        reg_map,
        free_regs
    )

    if reg is not None:
        assembly.append(f"MOV {operand}, {reg}")
        return reg

    return "MEMORY"


def generate_assignment(
    dest,
    op1,
    operator,
    op2,
    reg_map,
    free_regs,
    assembly
):

    r1 = load_operand(
        op1,
        reg_map,
        free_regs,
        assembly
    )

    r2 = load_operand(
        op2,
        reg_map,
        free_regs,
        assembly
    )

    if r1 == "MEMORY":
        assembly.append(f"LOAD {op1}, R1")
        r1 = "R1"

    if r2 == "MEMORY":
        assembly.append(f"LOAD {op2}, R2")
        r2 = "R2"

    if operator == "+":
        assembly.append(f"ADD {r1}, {r2}")

    elif operator == "-":
        assembly.append(f"SUB {r1}, {r2}")

    elif operator == "*":
        assembly.append(f"MUL {r1}, {r2}")

    elif operator == "/":
        assembly.append(f"DIV {r1}, {r2}")

    reg_map[dest] = r1

    assembly.append(
        f"STORE {r1}, {dest}"
    )

    if r2 != r1 and r2 != "MEMORY":

        used_by = [
            v
            for v, r in reg_map.items()
            if r == r2
        ]

        for v in used_by:
            del reg_map[v]

        if r2 not in free_regs:
            free_regs.append(r2)


def generate_assembly(source_code):

    assembly = []

    free_regs = [
        "R1",
        "R2",
        "R3",
        "R4"
    ]

    reg_map = {}

    lines = source_code.splitlines()

    label_counter = 1

    control_stack = []

    for line in lines:

        line = line.strip()

        if not line:
            continue

        line = re.sub(
            r'#.*',
            '',
            line
        ).strip()

        if not line:
            continue

        match = re.match(
            r'while\s+(\w+|\d+)\s*(<=|>=|==|!=|<|>)\s*(\w+|\d+)',
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

            assembly.append(
                f"CMP {left}, {right}"
            )

            if operator == "<":
                assembly.append(
                    f"JGE {end_label}"
                )

            elif operator == "<=":
                assembly.append(
                    f"JG {end_label}"
                )

            elif operator == ">":
                assembly.append(
                    f"JLE {end_label}"
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

        match = re.match(
            r'for\s+(\w+)\s*=\s*(\d+)\s+to\s+(\d+)',
            line
        )

        if match:

            variable = match.group(1)
            start_value = match.group(2)
            end_value = match.group(3)

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

            assembly.append(
                f"MOV {start_value}, R1"
            )

            reg_map[variable] = "R1"

            assembly.append(
                f"STORE R1, {variable}"
            )

            assembly.append(
                f"{start_label}:"
            )

            assembly.append(
                f"CMP {variable}, {end_value}"
            )

            assembly.append(
                f"JG {end_label}"
            )

            continue

        match = re.match(
            r'if\s+(\w+|\d+)\s*(<=|>=|==|!=|<|>)\s*(\w+|\d+)',
            line
        )

        if match:

            left = match.group(1)
            operator = match.group(2)
            right = match.group(3)

            else_label = f"L{label_counter}"

            label_counter += 1

            control_stack.append({
                "type": "if",
                "else": else_label
            })

            assembly.append(
                f"CMP {left}, {right}"
            )

            if operator == "<":
                assembly.append(
                    f"JGE {else_label}"
                )

            elif operator == "<=":
                assembly.append(
                    f"JG {else_label}"
                )

            elif operator == ">":
                assembly.append(
                    f"JLE {else_label}"
                )

            elif operator == ">=":
                assembly.append(
                    f"JL {else_label}"
                )

            elif operator == "==":
                assembly.append(
                    f"JNE {else_label}"
                )

            elif operator == "!=":
                assembly.append(
                    f"JE {else_label}"
                )

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
                        f"{current['else']}:"
                    )

            continue

        if line == "end":

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

                    variable = current["variable"]

                    reg = allocate_register(
                        variable,
                        reg_map,
                        free_regs
                    )

                    if reg is None:
                        reg = "R1"

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

            continue

        match = re.match(
            r'(\w+)\s*=\s*(\w+|\d+)\s*([\+\-\*/])\s*(\w+|\d+)',
            line
        )

        if match:

            dest = match.group(1)
            op1 = match.group(2)
            operator = match.group(3)
            op2 = match.group(4)

            generate_assignment(
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
            r'(\w+)\s*=\s*(\w+|\d+)',
            line
        )

        if match:

            dest = match.group(1)
            value = match.group(2)

            if value.isdigit():

                if free_regs:
                    reg = free_regs.pop(0)
                else:
                    reg = "R1"

                assembly.append(
                    f"MOV {value}, {reg}"
                )

            else:

                reg = allocate_register(
                    value,
                    reg_map,
                    free_regs
                )

                if reg is None:
                    reg = "R1"

                assembly.append(
                    f"MOV {value}, {reg}"
                )

            reg_map[dest] = reg

            assembly.append(
                f"STORE {reg}, {dest}"
            )

            continue

    return "\n".join(assembly)


@app.route('/')
def home():

    return render_template(
        'index.html'
    )


@app.route(
    '/optimize',
    methods=['POST']
)
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
        "while",
        "for",
        "if",
        "else",
        "end",
        "to"
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
