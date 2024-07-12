import os
import subprocess


# Specify the project path and output path
project_path = "/Users/adamaissani/PycharmProjects/pynguin/src/pynguin/ga"
output_path = "/Users/adamaissani/PycharmProjects/pynguin/output"

# Find all module names in the project path
module_names = [f[:-3] for f in os.listdir(project_path) if f.endswith(".py")]


os.environ["PYNGUIN_DANGER_AWARE"] = "1"

# Run the pynguin command for each module
for module_name in module_names:
    print("---------------------------------------")
    print(module_name)
    print("---------------------------------------")
    command = [
        "pynguin",
        "--project-path",
        project_path,
        "--output-path",
        output_path,
        "--module-name",
        module_name,
        "--maximum_search_time",
        "15",
    ]
    subprocess.run(command, check=False)
