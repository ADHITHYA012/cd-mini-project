from flask import Flask, render_template, request
import re

app = Flask(__name__)


def allocate_register(var, reg_map, free_regs):
    """
    Assign a register if variable doesn't already have one.
    """
    if var in reg_map:
        return reg_map[var]

    if free_regs:
        reg = free_regs.pop(0)
        reg_map[var] = reg
        return reg

    return None


def generate_assembly(source_code):

    assembly = []

    
    free_regs = ["R1", "R2", "R3", "R4"]

    
    reg_map = {}

    lines = source_code.splitlines()

    for line in lines:

        line = line.strip()

        if not line:
            continue

        match = re.match(
            r'(\w+)\s*=\s*(\w+)\s*([\+\-\*/])\s*(\w+)',
            line
        )

        if not match:
            continue

        dest = match.group(1)
        op1 = match.group(2)
        operator = match.group(3)
        op2 = match.group(4)

        r1 = allocate_register(op1, reg_map, free_regs)

        if r1 is None:
            r1 = "MEMORY"

        r2 = allocate_register(op2, reg_map, free_regs)

        if r2 is None:
            r2 = "MEMORY"
        if r1 != "MEMORY":
            assembly.append(f"MOV {op1}, {r1}")

        if r2 != "MEMORY":
            assembly.append(f"MOV {op2}, {r2}")
        if operator == "+":
            assembly.append(f"ADD {r1}, {r2}")

        elif operator == "-":
            assembly.append(f"SUB {r1}, {r2}")

        elif operator == "*":
            assembly.append(f"MUL {r1}, {r2}")

        elif operator == "/":
            assembly.append(f"DIV {r1}, {r2}")
        reg_map[dest] = r1

        assembly.append(f"STORE {r1}, {dest}")
        if r2 != "MEMORY":

            vars_using_r2 = [
                v for v, r in reg_map.items()
                if r == r2
            ]

            for v in vars_using_r2:
                del reg_map[v]

            if r2 not in free_regs:
                free_regs.append(r2)

        assembly.append("")

    return "\n".join(assembly)
@app.route('/')
def home():
    return render_template('index.html')
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

    register_result = ""

    for i, var in enumerate(variables, start=1):
        register_result += f"{var} → R{i}\n"
    instruction_result = generate_assembly(source_code)

    return render_template(
        'index.html',
        code=source_code,
        register=register_result,
        instruction=instruction_result
    )


if __name__ == '__main__':
    app.run(debug=True)